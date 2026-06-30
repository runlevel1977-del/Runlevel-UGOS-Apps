# -*- coding: utf-8 -*-
"""Read-only compare: local rsync dry-run or rclone check (SMB / mixed)."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from devices import endpoint_uses_smb, rclone_remote_url
from path_filters import TRANSFER_EXCLUDE_GLOBS, is_hidden_name, rsync_exclude_args
from i18n import get_lang, t
from progress import set_progress
from store import append_log

_ITEMIZE_CHANGE = re.compile(r"^[<>ch.*][f.][.s.+][.s.+][.p.][.o.][.g.][.u.][.a.][.x.]")
_USB_FS = frozenset({"vfat", "msdos", "exfat", "ntfs", "fuseblk"})
_RCLONE_SIZE_OBJECTS = re.compile(r"Total objects:\s*(\d+)", re.IGNORECASE)
_RCLONE_SIZE_BYTES = re.compile(r"Total size:\s*([\d.]+)\s*(\w+)", re.IGNORECASE)


def _rclone_exclude_args() -> list[str]:
    args: list[str] = []
    for pat in TRANSFER_EXCLUDE_GLOBS:
        args.extend(["--exclude", pat])
    return args


def _rclone_compat_args(uses_smb: bool) -> list[str]:
    if uses_smb:
        return ["--disable", "OpenWriterAt,OpenChunkWriter"]
    return []


def _rclone_resilience_args() -> list[str]:
    return [
        "--timeout",
        "12h",
        "--contimeout",
        "5m",
        "--retries",
        "10",
        "--low-level-retries",
        "20",
        "--retries-sleep",
        "30s",
    ]


def _run_subprocess(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=86400,
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def _path_stats(
    root: Path,
    job_id: str | None = None,
    *,
    phase: str,
    pct_start: int,
    pct_end: int,
    label_key: str,
) -> tuple[int, int]:
    lng = get_lang()
    files, total = 0, 0
    if not root.is_dir():
        return 0, 0
    span = max(1, pct_end - pct_start)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_hidden_name(d)]
        for name in filenames:
            if is_hidden_name(name):
                continue
            fp = Path(dirpath) / name
            try:
                total += fp.stat().st_size
                files += 1
            except OSError:
                pass
            if job_id and files % 250 == 0:
                pct = pct_start + min(span - 1, files // 250)
                set_progress(
                    job_id,
                    phase=phase,
                    percent=pct,
                    message=t(label_key, lng, count=files),
                    indeterminate=False,
                )
    if job_id:
        set_progress(
            job_id,
            phase=phase,
            percent=pct_end,
            message=t(label_key, lng, count=files),
            indeterminate=False,
        )
    return files, total


def _size_suffix_to_bytes(value: float, unit: str) -> int:
    u = unit.strip().upper()
    mult = {
        "B": 1,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
    }
    return int(value * mult.get(u, 1))


def _stats_count_mismatch(src_objs: int, dst_objs: int) -> str | None:
    if src_objs >= 0 and dst_objs >= 0 and src_objs != dst_objs:
        return f"object count: source {src_objs}, dest {dst_objs}"
    return None


def _stats_size_drift(src_bytes: int, dst_bytes: int) -> str | None:
    """Size hint only — SMB/rclone size can drift slightly; real compare is rclone check."""
    if src_bytes < 0 or dst_bytes < 0:
        return None
    hi = max(src_bytes, dst_bytes)
    lo = min(src_bytes, dst_bytes)
    if hi > 0 and lo / hi < 0.98:
        return f"size: source {src_bytes} B, dest {dst_bytes} B"
    return None


def _log_stats_warnings(
    src_objs: int,
    src_bytes: int,
    dst_objs: int,
    dst_bytes: int,
) -> None:
    count_diff = _stats_count_mismatch(src_objs, dst_objs)
    size_diff = _stats_size_drift(src_bytes, dst_bytes)
    if count_diff:
        append_log(f"STATS WARN count drift (detailed compare follows): {count_diff}")
    if size_diff:
        append_log(f"STATS WARN size drift (detailed compare follows): {size_diff}")


_RCLONE_DIFF_COUNT = re.compile(r"(\d+)\s+differences?\s+found", re.IGNORECASE)


def _read_report_lines(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except OSError:
        return []


def _summarize_rclone_diffs(
    missing_dst: list[str],
    missing_src: list[str],
    differ: list[str],
) -> None:
    if missing_src:
        sample = ", ".join(missing_src[:8])
        extra = "…" if len(missing_src) > 8 else ""
        append_log(
            f"INFO {len(missing_src)} only on dest (ignored for backup check): {sample}{extra}"
        )
    if missing_dst:
        append_log(f"MISSING on dest ({len(missing_dst)}):\n" + "\n".join(missing_dst[:30]))
    if differ:
        append_log(f"DIFFER ({len(differ)}):\n" + "\n".join(differ[:30]))


def _rclone_path_stats(url: str, uses_smb: bool) -> tuple[int, int]:
    cmd = [
        "rclone",
        "size",
        url,
        *_rclone_compat_args(uses_smb),
        *_rclone_exclude_args(),
    ]
    code, output = _run_subprocess(cmd)
    if code != 0:
        return -1, -1
    mobj = _RCLONE_SIZE_OBJECTS.search(output)
    sobj = _RCLONE_SIZE_BYTES.search(output)
    files = int(mobj.group(1)) if mobj else 0
    total = 0
    if sobj:
        total = _size_suffix_to_bytes(float(sobj.group(1)), sobj.group(2))
    return files, total


def _detect_fstype(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["df", "-T", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            lines = (proc.stdout or "").strip().splitlines()
            if len(lines) >= 2:
                parts = lines[-1].split()
                if len(parts) >= 2:
                    return parts[1].lower()
    except OSError:
        pass
    return ""


def _rsync_compare_args(src: Path, dst: Path) -> list[str]:
    fstypes = {_detect_fstype(src), _detect_fstype(dst)}
    if fstypes & _USB_FS:
        return [
            "-rln",
            "--checksum",
            "--modify-window=2",
            "--no-perms",
            "--no-owner",
            "--no-group",
            "--no-xattrs",
            "--no-acls",
        ]
    return ["-rln", "--checksum"]


def _verify_local_paths(
    src: Path, dst: Path, job_id: str | None = None
) -> tuple[bool, str, dict]:
    src = src.resolve()
    dst = dst.resolve()
    if not src.is_dir():
        return False, "source_missing", {"source": str(src)}
    if not dst.is_dir():
        return False, "dest_missing", {"dest": str(dst)}

    if job_id:
        set_progress(
            job_id,
            phase="stats",
            percent=2,
            message=t("progress.stats_source", get_lang()),
            indeterminate=True,
        )
    src_files, src_bytes = _path_stats(
        src,
        job_id,
        phase="stats",
        pct_start=5,
        pct_end=18,
        label_key="progress.stats_source_count",
    )
    if job_id:
        set_progress(
            job_id,
            phase="stats",
            percent=20,
            message=t("progress.stats_dest", get_lang()),
            indeterminate=True,
        )
    dst_files, dst_bytes = _path_stats(
        dst,
        job_id,
        phase="stats",
        pct_start=22,
        pct_end=35,
        label_key="progress.stats_dest_count",
    )
    append_log(
        f"STATS source: {src_files} files, {src_bytes / (1024 * 1024):.1f} MiB | "
        f"dest: {dst_files} files, {dst_bytes / (1024 * 1024):.1f} MiB"
    )

    _log_stats_warnings(src_files, src_bytes, dst_files, dst_bytes)

    cmd = [
        "rsync",
        *_rsync_compare_args(src, dst),
        "-n",
        "--itemize-changes",
        *rsync_exclude_args(),
        str(src) + "/",
        str(dst) + "/",
    ]
    append_log(f"CMD {' '.join(cmd)}")
    if job_id:
        set_progress(
            job_id,
            phase="compare",
            percent=40,
            message=t("progress.compare_rsync", get_lang()),
            indeterminate=True,
        )
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=86400,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, "timeout", {}

    output = (proc.stdout or "") + (proc.stderr or "")
    changes: list[str] = []
    for line in output.splitlines():
        line = line.rstrip()
        if not line or line.startswith("sending incremental"):
            continue
        if _ITEMIZE_CHANGE.match(line):
            changes.append(line)

    tail = "\n".join(output.strip().splitlines()[-15:])
    if changes:
        sample = changes[:40]
        append_log(f"DIFF {len(changes)} item(s)\n" + "\n".join(sample[:15]))
        return (
            False,
            "differences",
            {
                "change_count": len(changes),
                "sample": sample,
                "tail": tail,
                "src_files": src_files,
                "src_bytes": src_bytes,
                "dst_files": dst_files,
                "dst_bytes": dst_bytes,
            },
        )

    if proc.returncode not in (0, 23, 24):
        append_log(f"RSYNC error exit {proc.returncode}:\n{tail}")
        return False, "rsync_error", {"exit_code": proc.returncode, "tail": tail}

    append_log("VERIFY OK — reference complete on target (rsync, one-way)")
    return (
        True,
        "ok",
        {
            "src_files": src_files,
            "src_bytes": src_bytes,
            "dst_files": dst_files,
            "dst_bytes": dst_bytes,
        },
    )


def _verify_rclone(
    src_ep: dict[str, Any], dst_ep: dict[str, Any], job_id: str | None = None
) -> tuple[bool, str, dict]:
    uses_smb = endpoint_uses_smb(src_ep) or endpoint_uses_smb(dst_ep)
    try:
        src_url = rclone_remote_url(src_ep)
        dst_url = rclone_remote_url(dst_ep)
    except ValueError as ex:
        return False, "rsync_error", {"tail": str(ex)}

    append_log(
        f"RCLONE check (one-way, reference → target): {src_url[:120]}… <=> {dst_url[:120]}…"
    )

    if job_id:
        set_progress(
            job_id,
            phase="stats",
            percent=10,
            message=t("progress.stats_source", get_lang()),
            indeterminate=True,
        )
    src_objs, src_bytes = _rclone_path_stats(src_url, uses_smb)
    if job_id:
        set_progress(
            job_id,
            phase="stats",
            percent=25,
            message=t("progress.stats_dest", get_lang()),
            indeterminate=True,
        )
    dst_objs, dst_bytes = _rclone_path_stats(dst_url, uses_smb)
    if src_bytes >= 0:
        append_log(
            f"STATS source: ~{src_objs} obj, {src_bytes / (1024 * 1024):.1f} MiB | "
            f"dest: ~{dst_objs} obj, {dst_bytes / (1024 * 1024):.1f} MiB"
        )

    _log_stats_warnings(src_objs, src_bytes, dst_objs, dst_bytes)

    if job_id:
        set_progress(
            job_id,
            phase="compare",
            percent=45,
            message=t("progress.compare_rclone", get_lang()),
            indeterminate=True,
        )
    with tempfile.TemporaryDirectory(prefix="bv_check_") as tmp:
        missing_dst_path = os.path.join(tmp, "missing_on_dst.txt")
        missing_src_path = os.path.join(tmp, "missing_on_src.txt")
        differ_path = os.path.join(tmp, "differ.txt")
        check_cmd = [
            "rclone",
            "check",
            src_url,
            dst_url,
            "--one-way",
            "-v",
            f"--missing-on-dst={missing_dst_path}",
            f"--missing-on-src={missing_src_path}",
            f"--differ={differ_path}",
            *_rclone_resilience_args(),
            *_rclone_compat_args(uses_smb),
            *_rclone_exclude_args(),
        ]
        code, output = _run_subprocess(check_cmd)
        missing_dst = _read_report_lines(missing_dst_path)
        missing_src = _read_report_lines(missing_src_path)
        differ = _read_report_lines(differ_path)
        _summarize_rclone_diffs(missing_dst, missing_src, differ)

    fail_count = len(missing_dst) + len(differ)
    if code != 0 or fail_count:
        tail = "\n".join(output.strip().splitlines()[-25:])
        append_log(f"VERIFY FAIL rclone check (exit {code}):\n{tail}")
        return (
            False,
            "differences",
            {
                "change_count": fail_count if fail_count > 0 else -1,
                "missing_on_dst": len(missing_dst),
                "differ_count": len(differ),
                "extra_on_dest": len(missing_src),
                "sample": (missing_dst + differ)[:40],
                "tail": tail,
                "src_bytes": src_bytes,
                "dst_bytes": dst_bytes,
                "exit_code": code,
            },
        )

    append_log("VERIFY OK — reference complete on target (rclone, one-way)")
    return (
        True,
        "ok",
        {
            "src_bytes": src_bytes,
            "dst_bytes": dst_bytes,
            "src_objects": src_objs,
            "dst_objects": dst_objs,
        },
    )


def run_verify_endpoints(
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    job_id: str | None = None,
) -> tuple[bool, str, dict]:
    """Compare reference (source) to target (dest); read-only."""
    if endpoint_uses_smb(src_ep) or endpoint_uses_smb(dst_ep):
        return _verify_rclone(src_ep, dst_ep, job_id=job_id)
    try:
        src = Path(rclone_remote_url(src_ep))
        dst = Path(rclone_remote_url(dst_ep))
    except ValueError as ex:
        return False, "source_missing", {"tail": str(ex)}
    return _verify_local_paths(src, dst, job_id=job_id)
