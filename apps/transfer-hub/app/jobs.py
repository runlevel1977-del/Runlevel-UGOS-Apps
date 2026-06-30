# -*- coding: utf-8 -*-
"""Transfer jobs: rsync (local) or rclone (SMB) with live progress."""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from devices import (
    LOCAL_ID,
    endpoint_label,
    endpoint_uses_smb,
    get_device,
    rclone_remote_url,
    smb_delete_source_tree,
)
from i18n import get_lang, resolve_lang, t
from network_scan import host_smb_reachable
from path_filters import TRANSFER_EXCLUDE_GLOBS, is_hidden_name
from schedule_util import profile_due_now
from store import append_log, load_profiles, save_profiles

_running_lock = threading.Lock()
_running_ids: set[str] = set()
_jobs_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}

_RCLONE_STAT = re.compile(
    r"([\d.,]+\s*(?:Ki|Mi|Gi|Ti|K|M|G|T)?i?B)\s*/\s*"
    r"([\d.,]+\s*(?:Ki|Mi|Gi|Ti|K|M|G|T)?i?B),\s*(\d+)%"
    r"(?:,\s*([^,]+))?,\s*ETA\s*(.+)",
    re.IGNORECASE,
)
_RSYNC_PROGRESS = re.compile(r"^\s*([\d,]+)\s+(\d+)%\s+([\d.,]+\w+/s)?")
_RCLONE_PARTIAL_FAIL = re.compile(r"Failed to copy with (\d+) errors", re.IGNORECASE)
_RCLONE_ERROR_LINE = re.compile(r" ERROR : ", re.IGNORECASE)
_RCLONE_SIZE_OBJECTS = re.compile(r"Total objects:\s*(\d+)", re.IGNORECASE)
_RCLONE_SIZE_BYTES = re.compile(r"Total size:\s*([\d.]+)\s*(\w+)", re.IGNORECASE)
_RSYNC_COMPLETE = re.compile(r"to-chk=0/\d+")


def _rclone_exclude_args() -> list[str]:
    args: list[str] = []
    for pat in TRANSFER_EXCLUDE_GLOBS:
        args.extend(["--exclude", pat])
    return args


def _rsync_exclude_args() -> list[str]:
    args: list[str] = []
    for pat in TRANSFER_EXCLUDE_GLOBS:
        args.extend(["--exclude", pat])
    return args


def _rclone_compat_args(src_ep: dict[str, Any], dst_ep: dict[str, Any]) -> list[str]:
    """Work around rclone SMB multi-thread writes failing on Windows (signing required)."""
    if endpoint_uses_smb(src_ep) or endpoint_uses_smb(dst_ep):
        return ["--disable", "OpenWriterAt,OpenChunkWriter"]
    return []


_RCLONE_JOB_ATTEMPTS = 3
_RCLONE_JOB_RETRY_SLEEP = 90


def _rclone_resilience_args() -> list[str]:
    """Long runs / large files: avoid idle timeout and retry transient SMB drops."""
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


def _rclone_common_args(src_ep: dict[str, Any], dst_ep: dict[str, Any]) -> list[str]:
    smb = endpoint_uses_smb(src_ep) or endpoint_uses_smb(dst_ep)
    return [
        "-v",
        "--stats",
        "1s",
        "--stats-one-line",
        "--transfers",
        "2" if smb else "4",
        "--checkers",
        "4" if smb else "8",
        *_rclone_resilience_args(),
        *_rclone_compat_args(src_ep, dst_ep),
        *_rclone_exclude_args(),
    ]


def _execute_rclone_copy(
    profile_id: str,
    src_url: str,
    dst_url: str,
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    on_progress: Callable[[str], None] | None,
    *,
    log_prefix: str = "",
) -> tuple[bool, str]:
    cmd_base = ["rclone", "copy", src_url, dst_url, *_rclone_common_args(src_ep, dst_ep)]
    last_output = ""
    for attempt in range(1, _RCLONE_JOB_ATTEMPTS + 1):
        if attempt > 1:
            append_log(
                f"{log_prefix}Neuer Versuch {attempt}/{_RCLONE_JOB_ATTEMPTS} "
                f"in {_RCLONE_JOB_RETRY_SLEEP}s …"
            )
            time.sleep(_RCLONE_JOB_RETRY_SLEEP)
        code, output = _run_subprocess(cmd_base, profile_id, on_progress=on_progress)
        last_output = output
        if code == 0 and not _rclone_had_errors(output):
            if attempt > 1:
                append_log(f"{log_prefix}Versuch {attempt} erfolgreich")
            return True, output
        tail = "\n".join(output.strip().splitlines()[-10:])
        append_log(f"{log_prefix}Versuch {attempt}/{_RCLONE_JOB_ATTEMPTS} fehlgeschlagen:\n{tail}")
    return False, last_output


def _rclone_had_errors(output: str) -> bool:
    if _RCLONE_ERROR_LINE.search(output):
        return True
    lowered = output.lower()
    return "failed to copy" in lowered or "failed to move" in lowered or "fatal error" in lowered


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


def _local_path_stats(root: Path) -> tuple[int, int]:
    files, total = 0, 0
    if not root.is_dir():
        return 0, 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_hidden_name(d)]
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                total += fp.stat().st_size
                files += 1
            except OSError:
                pass
    return files, total


def _rclone_path_stats(
    profile_id: str,
    url: str,
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
) -> tuple[int, int]:
    cmd = [
        "rclone",
        "size",
        url,
        *_rclone_compat_args(src_ep, dst_ep),
        *_rclone_exclude_args(),
    ]
    code, output = _run_subprocess(cmd, profile_id)
    if code != 0:
        return -1, -1
    mobj = _RCLONE_SIZE_OBJECTS.search(output)
    sobj = _RCLONE_SIZE_BYTES.search(output)
    files = int(mobj.group(1)) if mobj else 0
    total = 0
    if sobj:
        total = _size_suffix_to_bytes(float(sobj.group(1)), sobj.group(2))
    return files, total


def _verify_rclone_copy(
    profile_id: str,
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    lng: str,
    *,
    src_bytes: int,
) -> tuple[bool, str]:
    if src_bytes <= 0:
        append_log("VERIFY: Quelle leer, nichts zu prüfen")
        return True, ""

    src_url = rclone_remote_url(src_ep)
    dst_url = rclone_remote_url(dst_ep)
    append_log(f"VERIFY: Quelle {src_bytes / (1024 * 1024):.1f} MiB")

    check_cmd = [
        "rclone",
        "check",
        src_url,
        dst_url,
        "--one-way",
        "-v",
        *_rclone_resilience_args(),
        *_rclone_compat_args(src_ep, dst_ep),
        *_rclone_exclude_args(),
    ]
    code, output = _run_subprocess(check_cmd, profile_id)
    if code != 0:
        append_log(f"VERIFY FAIL rclone check (exit {code}):\n{output[-800:]}")
        return False, t("transfer.verify_failed", lng, detail=output[-400:])

    src_objs, src_size = _rclone_path_stats(profile_id, src_url, src_ep, dst_ep)
    dst_objs, dst_bytes = _rclone_path_stats(profile_id, dst_url, src_ep, dst_ep)
    append_log(
        f"VERIFY: Ziel {dst_bytes / (1024 * 1024):.1f} MiB "
        f"(rclone-Objekte Quelle/Ziel: {src_objs}/{dst_objs})"
    )
    # Byte-Vergleich — Objektzahl kann bei SMB vs. lokal abweichen (Ordner vs. Dateien).
    if dst_bytes < max(1, int(src_bytes * 0.98)):
        detail = f"Quelle {src_bytes} B, Ziel {dst_bytes} B"
        append_log(f"VERIFY FAIL Größenvergleich: {detail}")
        return False, t("transfer.verify_failed", lng, detail=detail)

    ls_cmd = [
        "rclone",
        "lsl",
        dst_url,
        "--max-depth",
        "2",
        *_rclone_compat_args(src_ep, dst_ep),
    ]
    _, ls_out = _run_subprocess(ls_cmd, profile_id)
    append_log(f"VERIFY Ziel-Inhalt (Auszug):\n{ls_out[:1500]}")
    append_log("VERIFY OK")
    return True, ""


def _endpoint_is_usb(ep: dict[str, Any]) -> bool:
    return str(ep.get("volume") or "").startswith("usb-")


def _rsync_archive_args(src_ep: dict[str, Any], dst_ep: dict[str, Any]) -> list[str]:
    """FAT/exFAT/NTFS (typical USB) cannot store Unix owner/mode/xattrs."""
    if _endpoint_is_usb(src_ep) or _endpoint_is_usb(dst_ep):
        return [
            "-rlt",
            "--modify-window=2",
            "--no-perms",
            "--no-owner",
            "--no-group",
            "--no-xattrs",
            "--no-acls",
            "--no-devices",
            "--copy-links",
        ]
    return ["-a"]


def _rsync_files_complete(output: str) -> bool:
    if "100%" not in output:
        return False
    return bool(_RSYNC_COMPLETE.search(output))


def _evaluate_rsync_result(
    code: int,
    output: str,
    lng: str,
    *,
    move: bool,
    verify_next: bool,
) -> tuple[bool, str]:
    if code == 0:
        key = "transfer.move_done" if move else "transfer.done"
        return True, t(key, lng)
    tail = "\n".join(output.strip().splitlines()[-12:])
    # USB / VFAT: data copied but chmod/chown fails (rsync exit 23) — VERIFY decides.
    if not move and verify_next and code == 23 and _rsync_files_complete(output):
        append_log(
            "rsync exit 23 (Attribute/Rechte) — Dateien scheinen vollständig, VERIFY folgt …"
        )
        return True, ""
    if move or not verify_next:
        return False, tail or f"exit {code}"
    return False, tail or f"exit {code}"


def _evaluate_rclone_result(
    code: int, output: str, lng: str, *, move: bool = False, allow_partial: bool = True
) -> tuple[bool, str]:
    if code == 0:
        key = "transfer.move_done" if move else "transfer.done"
        return True, t(key, lng)
    tail = "\n".join(output.strip().splitlines()[-12:])
    if move or not allow_partial:
        return False, tail or f"exit {code}"
    m = _RCLONE_PARTIAL_FAIL.search(output)
    if m and re.search(r",\s*100%,", output):
        return True, t("transfer.partial_ok", lng, count=int(m.group(1)))
    return False, tail or f"exit {code}"


def _normalize_endpoint(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict) and raw.get("device_id"):
        return {
            "device_id": raw.get("device_id"),
            "volume": raw.get("volume") or "",
            "share": raw.get("share") or "",
            "path": raw.get("path") or "",
        }
    if isinstance(raw, str) and raw.strip():
        return {
            "device_id": "local",
            "share": "",
            "path": raw.strip().removeprefix("/mnt/nas/").lstrip("/"),
        }
    return {"device_id": "local", "volume": "", "share": "", "path": ""}


def _parse_progress_line(line: str) -> dict[str, Any] | None:
    m = _RCLONE_STAT.search(line)
    if m:
        return {
            "percent": min(100, int(m.group(3))),
            "detail": f"{m.group(1)} / {m.group(2)}",
            "speed": (m.group(4) or "").strip(),
            "eta": (m.group(5) or "").strip(),
        }
    m2 = _RSYNC_PROGRESS.search(line)
    if m2:
        speed = (m2.group(3) or "").strip()
        return {
            "percent": min(100, int(m2.group(2))),
            "detail": m2.group(1).replace(",", " ") + " B",
            "speed": speed,
            "eta": "",
        }
    if "100%" in line and "ETA" in line.upper():
        return {"percent": 100, "detail": "", "speed": "", "eta": ""}
    return None


def _set_job(profile_id: str, **fields: Any) -> None:
    with _jobs_lock:
        if profile_id in _jobs:
            _jobs[profile_id].update(fields)


def _remove_job_later(profile_id: str, delay: float = 10.0) -> None:
    def _drop() -> None:
        time.sleep(delay)
        with _jobs_lock:
            _jobs.pop(profile_id, None)

    threading.Thread(target=_drop, daemon=True).start()


def _init_job(profile: dict[str, Any]) -> None:
    src_ep = _normalize_endpoint(profile.get("source"))
    dst_ep = _normalize_endpoint(profile.get("dest"))
    pid = profile.get("id") or ""
    with _jobs_lock:
        _jobs[pid] = {
            "profile_id": pid,
            "name": profile.get("name") or t("profile.default_name", resolve_lang()),
            "source_label": endpoint_label(src_ep),
            "dest_label": endpoint_label(dst_ep),
            "status": "running",
            "percent": 0,
            "detail": "",
            "speed": "",
            "eta": "",
            "message": "",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }


def list_active_jobs() -> list[dict[str, Any]]:
    with _jobs_lock:
        return [dict(j) for j in _jobs.values()]


def _run_subprocess(
    cmd: list[str],
    profile_id: str,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        errors="replace",
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        lines.append(line.rstrip("\n"))
        if on_progress:
            on_progress(line)
    proc.wait()
    tail = "\n".join(lines[-20:])
    return proc.returncode, tail


def _on_progress_line(profile_id: str, line: str) -> None:
    parsed = _parse_progress_line(line)
    if parsed:
        _set_job(profile_id, **parsed)


def _remove_empty_dirs(root: Path) -> None:
    if not root.is_dir():
        return
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        p = Path(dirpath)
        if p == root:
            continue
        try:
            next(p.iterdir())
        except StopIteration:
            try:
                p.rmdir()
            except OSError:
                pass
        except OSError:
            pass


def _cleanup_local_move_source(src_ep: dict[str, Any], lng: str) -> tuple[bool, str]:
    """Remove transferred files on local NAS paths (no rclone needed)."""
    src = Path(rclone_remote_url(src_ep)).resolve()
    if not src.is_dir():
        return True, ""
    errors: list[str] = []

    def _purge_dir(base: Path) -> None:
        try:
            entries = list(base.iterdir())
        except OSError as e:
            errors.append(f"{base}: {e}")
            return
        for entry in entries:
            if entry.is_dir():
                if is_hidden_name(entry.name):
                    continue
                _purge_dir(entry)
                try:
                    entry.rmdir()
                except OSError:
                    pass
            else:
                try:
                    entry.unlink()
                except OSError as e:
                    errors.append(f"{entry}: {e}")

    _purge_dir(src)
    _remove_empty_dirs(src)
    if errors:
        detail = "\n".join(errors[:8])
        return False, t("transfer.move_cleanup_failed", lng, detail=detail)
    append_log("CLEANUP Quelle: lokales Löschen OK")
    return True, ""


def _cleanup_move_source(
    profile_id: str, src_ep: dict[str, Any], lng: str
) -> tuple[bool, str]:
    append_log(f"CLEANUP Quelle: {endpoint_label(src_ep)}")
    if not endpoint_uses_smb(src_ep):
        return _cleanup_local_move_source(src_ep, lng)

    src_url = rclone_remote_url(src_ep)
    cmd = [
        "rclone",
        "delete",
        src_url,
        "-v",
        "--rmdirs",
        *_rclone_compat_args(src_ep, src_ep),
        *_rclone_exclude_args(),
    ]
    code, output = _run_subprocess(cmd, profile_id)
    if code == 0:
        append_log("CLEANUP Quelle: rclone delete OK")
        return True, ""

    append_log(f"CLEANUP rclone delete fehlgeschlagen (exit {code}):\n{output[-600:]}")
    device = get_device(src_ep.get("device_id", ""))
    share = (src_ep.get("share") or "").strip()
    if device and share:
        ok, msg = smb_delete_source_tree(device, share, src_ep.get("path") or "")
        if ok:
            append_log("CLEANUP Quelle: smbclient fallback OK")
            return True, ""
        append_log(f"CLEANUP smbclient fallback fehlgeschlagen: {msg[:400]}")
        return False, t("transfer.move_cleanup_failed", lng, detail=msg[:400])
    return False, t("transfer.move_cleanup_failed", lng, detail=output[-400:])


def _run_rsync_between_paths(
    profile_id: str,
    src: Path,
    dst: Path,
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    *,
    move: bool = False,
) -> tuple[bool, str]:
    lng = resolve_lang()
    if not src.is_dir():
        return False, t("err.source_not_found", lng, path=str(src))
    dst.mkdir(parents=True, exist_ok=True)
    verify_next = not move
    cmd = [
        "rsync",
        *_rsync_archive_args(src_ep, dst_ep),
        "--mkpath",
        "--info=progress2",
        *_rsync_exclude_args(),
    ]
    if move:
        cmd.append("--remove-source-files")
    cmd.extend([str(src) + "/", str(dst) + "/"])

    def _progress(line: str) -> None:
        _on_progress_line(profile_id, line)

    code, output = _run_subprocess(cmd, profile_id, on_progress=_progress)
    ok, msg = _evaluate_rsync_result(
        code, output, lng, move=move, verify_next=verify_next
    )
    if ok and move:
        _remove_empty_dirs(src)
    return ok, msg


def _run_local_rsync(
    profile_id: str,
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    *,
    move: bool = False,
) -> tuple[bool, str]:
    lng = resolve_lang()
    src = Path(rclone_remote_url(src_ep)).resolve()
    dst = Path(rclone_remote_url(dst_ep)).resolve()
    if not move:
        append_log(f"COPY Phase 1/2: rsync -> {endpoint_label(dst_ep)}")
    ok, msg = _run_rsync_between_paths(profile_id, src, dst, src_ep, dst_ep, move=move)
    if not ok or move:
        return ok, msg
    append_log("COPY Phase 2/2: Ziel gegen Quelle prüfen")
    verify_ok, verify_msg = _verify_rclone_copy(
        profile_id,
        src_ep,
        dst_ep,
        lng,
        src_bytes=_local_path_stats(src)[1],
    )
    if not verify_ok:
        return False, verify_msg
    return True, t("transfer.done", lng)


def _run_rclone_transfer(
    profile_id: str,
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    *,
    move: bool = False,
) -> tuple[bool, str]:
    lng = resolve_lang()
    src_url = rclone_remote_url(src_ep)
    dst_url = rclone_remote_url(dst_ep)
    if not endpoint_uses_smb(dst_ep):
        Path(dst_url).mkdir(parents=True, exist_ok=True)

    def _progress(line: str) -> None:
        _on_progress_line(profile_id, line)

    _src_objs, src_bytes = _rclone_path_stats(
        profile_id, src_url, src_ep, dst_ep
    )
    if move:
        append_log(f"MOVE Phase 1/3: rclone copy -> {endpoint_label(dst_ep)}")
        log_prefix = "MOVE "
        verify_label = "MOVE Phase 2/3: Ziel gegen Quelle prüfen"
    else:
        append_log(f"COPY Phase 1/2: rclone copy -> {endpoint_label(dst_ep)}")
        log_prefix = ""
        verify_label = "COPY Phase 2/2: Ziel gegen Quelle prüfen"

    copy_ok, output = _execute_rclone_copy(
        profile_id,
        src_url,
        dst_url,
        src_ep,
        dst_ep,
        _progress,
        log_prefix=log_prefix,
    )
    if not copy_ok:
        tail = "\n".join(output.strip().splitlines()[-12:])
        return False, tail or t("transfer.verify_failed", lng, detail="rclone copy")

    append_log(verify_label)
    verify_ok, verify_msg = _verify_rclone_copy(
        profile_id,
        src_ep,
        dst_ep,
        lng,
        src_bytes=src_bytes,
    )
    if not verify_ok:
        return False, verify_msg

    if move:
        append_log("MOVE Phase 3/3: Quelle leeren")
        clean_ok, clean_msg = _cleanup_move_source(profile_id, src_ep, lng)
        if not clean_ok:
            return False, clean_msg
        return True, t("transfer.move_done", lng)

    return True, t("transfer.done", lng)


def run_rsync_profile(profile: dict[str, Any]) -> tuple[bool, str]:
    pid = profile.get("id") or ""
    with _running_lock:
        if pid in _running_ids:
            return False, t("jobs.already_running", get_lang())
        _running_ids.add(pid)

    _init_job(profile)
    src_ep = _normalize_endpoint(profile.get("source"))
    dst_ep = _normalize_endpoint(profile.get("dest"))
    use_rclone = endpoint_uses_smb(src_ep) or endpoint_uses_smb(dst_ep)
    move = bool(profile.get("delete_source_after"))
    mode = "MOVE" if move else "COPY"

    try:
        if use_rclone:
            append_log(
                f"START {profile.get('name')} | rclone {mode} "
                f"{endpoint_label(src_ep)} -> {endpoint_label(dst_ep)}"
            )
            ok, msg = _run_rclone_transfer(pid, src_ep, dst_ep, move=move)
        else:
            append_log(
                f"START {profile.get('name')} | rsync {mode} "
                f"{endpoint_label(src_ep)} -> {endpoint_label(dst_ep)}"
            )
            ok, msg = _run_local_rsync(pid, src_ep, dst_ep, move=move)
        if ok:
            _set_job(pid, status="ok", percent=100, message=msg)
            append_log(f"OK {profile.get('name')}\n{msg}")
        else:
            _set_job(pid, status="error", message=msg[:500])
            append_log(f"FAIL {profile.get('name')}\n{msg}")
        return ok, msg
    except Exception as e:
        _set_job(pid, status="error", message=str(e)[:500])
        append_log(f"FAIL {profile.get('name')} {e}")
        return False, str(e)
    finally:
        with _running_lock:
            _running_ids.discard(pid)
        _remove_job_later(pid)


def _smb_hosts_for_profile(profile: dict[str, Any]) -> list[str]:
    hosts: list[str] = []
    for ep in (profile.get("source"), profile.get("dest")):
        if not ep or not endpoint_uses_smb(ep):
            continue
        dev = get_device(ep.get("device_id", LOCAL_ID))
        if dev and dev.get("type") == "smb":
            host = (dev.get("host") or "").strip()
            if host:
                hosts.append(host)
    return list(dict.fromkeys(hosts))


def _offline_smb_host(profile: dict[str, Any]) -> str | None:
    for host in _smb_hosts_for_profile(profile):
        if not host_smb_reachable(host):
            return host
    return None


def _update_profile_after_run(
    profile_id: str,
    ok: bool,
    message: str,
    *,
    skipped_offline: bool = False,
) -> None:
    profiles = load_profiles()
    now = datetime.now(timezone.utc).isoformat()
    for p in profiles:
        if p.get("id") == profile_id:
            p["last_run"] = now
            if skipped_offline:
                p["last_status"] = "skipped"
            else:
                p["last_status"] = "ok" if ok else "error"
            p["last_message"] = (message or "")[:2000]
            break
    save_profiles(profiles)


def _execute_profile(profile_id: str, *, scheduled: bool = False) -> None:
    profiles = load_profiles()
    profile = next((p for p in profiles if p.get("id") == profile_id), None)
    if not profile:
        return
    if scheduled:
        offline = _offline_smb_host(profile)
        if offline:
            lng = get_lang()
            msg = t("jobs.skip_offline", lng, host=offline)
            append_log(f"SKIP {profile.get('name', profile_id)} — {offline} offline (SMB 445)")
            _update_profile_after_run(profile_id, ok=True, message=msg, skipped_offline=True)
            return
    ok, msg = run_rsync_profile(profile)
    _update_profile_after_run(profile_id, ok, msg)


def start_profile_run(profile_id: str) -> tuple[bool, str]:
    profiles = load_profiles()
    profile = next((p for p in profiles if p.get("id") == profile_id), None)
    if not profile:
        return False, t("err.profile_not_found", get_lang())
    with _running_lock:
        if profile_id in _running_ids:
            return False, t("jobs.already_running", get_lang())
    threading.Thread(
        target=_execute_profile, args=(profile_id,), kwargs={"scheduled": False}, daemon=True
    ).start()
    return True, t("jobs.started", get_lang())


def run_profile_by_id(profile_id: str) -> tuple[bool, str]:
    """Blocking run (legacy); prefer start_profile_run for API."""
    profiles = load_profiles()
    profile = next((p for p in profiles if p.get("id") == profile_id), None)
    if not profile:
        return False, t("err.profile_not_found", get_lang())
    ok, msg = run_rsync_profile(profile)
    _update_profile_after_run(profile_id, ok, msg)
    return ok, msg


def _scheduler_loop(stop_event: threading.Event) -> None:
    append_log("Scheduler gestartet (rsync/rclone)")
    while not stop_event.is_set():
        try:
            profiles = load_profiles()
            now = time.time()
            for p in profiles:
                pid = p.get("id")
                if not pid or pid in _running_ids:
                    continue
                if profile_due_now(p, now):
                    threading.Thread(
                        target=_execute_profile,
                        args=(pid,),
                        kwargs={"scheduled": True},
                        daemon=True,
                    ).start()
        except Exception as e:
            append_log(f"Scheduler error: {e}")
        stop_event.wait(45)


def start_scheduler() -> threading.Event:
    stop = threading.Event()
    t = threading.Thread(target=_scheduler_loop, args=(stop,), daemon=True)
    t.start()
    return stop
