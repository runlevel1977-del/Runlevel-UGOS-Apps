# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from devices import endpoint_path_list, endpoint_uses_smb, rclone_remote_url
from job_progress import (
    is_cancelled,
    register_proc,
    set_job,
    unregister_proc,
    update_rclone_progress,
    update_route_progress,
)
from path_filters import TRANSFER_EXCLUDE_GLOBS
from store import append_log

_RCLONE_ERROR_LINE = re.compile(r" ERROR : ", re.IGNORECASE)


def _rclone_exclude_args() -> list[str]:
    args: list[str] = []
    for pat in TRANSFER_EXCLUDE_GLOBS:
        args.extend(["--exclude", pat])
    return args


def _rclone_compat_args(
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    *,
    smb_performance: bool = False,
) -> list[str]:
    """Stable SMB: disable multi-thread writes (Windows signing). Performance: leave enabled."""
    if smb_performance:
        return []
    if endpoint_uses_smb(src_ep) or endpoint_uses_smb(dst_ep):
        return ["--disable", "OpenWriterAt,OpenChunkWriter"]
    return []


def _rclone_resilience_args() -> list[str]:
    return [
        "--timeout",
        "12h",
        "--contimeout",
        "5m",
        "--retries",
        "5",
        "--low-level-retries",
        "10",
    ]


def _rclone_sync_args(
    src_ep: dict[str, Any],
    dst_ep: dict[str, Any],
    *,
    smb_performance: bool = False,
) -> list[str]:
    """Shared rclone sync flags (Transfer Hub SMB performance pattern)."""
    smb = endpoint_uses_smb(src_ep) or endpoint_uses_smb(dst_ep)
    args = [
        "--create-empty-src-dirs",
        "-v",
        "--stats-one-line",
        "--stats",
        "1s",
        "--transfers",
        "4" if smb_performance and smb else ("2" if smb else "4"),
        "--checkers",
        "4" if smb else "8",
        *_rclone_resilience_args(),
        *_rclone_compat_args(src_ep, dst_ep, smb_performance=smb_performance),
        *_rclone_exclude_args(),
    ]
    if smb_performance and smb:
        args.extend(["--buffer-size", "64M"])
    return args


def _rclone_had_errors(output: str) -> bool:
    if _RCLONE_ERROR_LINE.search(output):
        return True
    lowered = output.lower()
    return (
        "failed to copy" in lowered
        or "failed to move" in lowered
        or "failed to sync" in lowered
        or "fatal error" in lowered
    )


def _dest_path_for_source(dest_ep: dict[str, Any], source_path: str) -> str:
    """Map one source folder under the destination base (preserves folder name)."""
    base = (dest_ep.get("path") or "").strip().strip("/")
    src = (source_path or "").strip().strip("/")
    if not src:
        return base
    leaf = src.split("/")[-1]
    return f"{base}/{leaf}".strip("/") if base else leaf


def _endpoint_with_path(ep: dict[str, Any], path: str) -> dict[str, Any]:
    out = {k: v for k, v in ep.items() if k != "paths"}
    out["path"] = (path or "").strip().strip("/")
    return out


def expand_sync_routes(
    source_ep: dict[str, Any],
    dest_ep: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Expand multi-folder source into one (src, dst) pair per folder."""
    paths = endpoint_path_list(source_ep)
    if not paths:
        paths = [""]
    routes: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for src_path in paths:
        src = _endpoint_with_path(source_ep, src_path)
        dst_path = _dest_path_for_source(dest_ep, src_path)
        dst = _endpoint_with_path(dest_ep, dst_path)
        routes.append((src, dst))
    return routes


def run_sync_plan(
    source_ep: dict[str, Any],
    dest_ep: dict[str, Any],
    *,
    plan_id: str = "",
    phase_label: str = "",
    smb_performance: bool = False,
) -> tuple[bool, str, dict]:
    """Run incremental rclone sync for each selected source folder."""
    routes = expand_sync_routes(source_ep, dest_ep)
    route_results: list[dict[str, Any]] = []
    total = len(routes)
    for idx, (src, dst) in enumerate(routes, start=1):
        if plan_id and is_cancelled(plan_id):
            return False, "cancelled", {"routes": route_results, "tail": "cancelled"}
        route_detail = f"{phase_label} ({idx}/{total})" if phase_label else f"{idx}/{total}"
        if plan_id:
            update_route_progress(
                plan_id,
                route_note=route_detail,
                route_idx=idx,
                route_total=total,
            )
        append_log(f"SYNC route {idx}/{total}: {src.get('path') or '/'} → {dst.get('path') or '/'}")
        ok, code, details = run_sync(
            src,
            dst,
            plan_id=plan_id,
            smb_performance=smb_performance,
            route_idx=idx,
            route_total=total,
        )
        route_results.append(
            {
                "index": idx,
                "ok": ok,
                "code": code,
                "source_path": src.get("path") or "",
                "dest_path": dst.get("path") or "",
                "tail": (details.get("tail") or "")[-400:],
            }
        )
        if not ok:
            return False, code, {"routes": route_results, "tail": details.get("tail") or ""}
    tail = "\n".join(r.get("tail") or "" for r in route_results if r.get("tail")).strip()
    return True, "ok", {"routes": route_results, "tail": tail[-1200:]}


def _run_rclone_sync_once(
    cmd: list[str],
    *,
    plan_id: str = "",
    route_idx: int = 1,
    route_total: int = 1,
) -> tuple[int, list[str], bool]:
    """Run one rclone sync process; return exit code, lines, cancelled."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            errors="replace",
        )
    except OSError as ex:
        return 1, [str(ex)], False

    if plan_id:
        register_proc(plan_id, proc)

    lines: list[str] = []
    cancelled = False
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
            if plan_id and is_cancelled(plan_id):
                cancelled = True
                try:
                    proc.terminate()
                except OSError:
                    pass
                break
            if plan_id:
                update_rclone_progress(
                    plan_id,
                    line,
                    route_idx=route_idx,
                    route_total=route_total,
                )
        if not cancelled:
            proc.wait()
        else:
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
                proc.wait()
    finally:
        if plan_id:
            unregister_proc(plan_id)

    code = proc.returncode if proc.returncode is not None else 1
    return code, lines, cancelled


def run_sync(
    source_ep: dict[str, Any],
    dest_ep: dict[str, Any],
    *,
    plan_id: str = "",
    smb_performance: bool = False,
    route_idx: int = 1,
    route_total: int = 1,
) -> tuple[bool, str, dict]:
    """One-way incremental sync: local NAS → SMB target (e.g. QNAP)."""
    try:
        src_url = rclone_remote_url(source_ep)
        dst_url = rclone_remote_url(dest_ep)
    except ValueError as ex:
        return False, "path_error", {"tail": str(ex)}

    src = Path(src_url)
    if not src.is_dir():
        return False, "source_missing", {"source": src_url}

    uses_smb = endpoint_uses_smb(source_ep) or endpoint_uses_smb(dest_ep)
    perf_modes = [True, False] if smb_performance and uses_smb else [False]
    last_lines: list[str] = []

    for perf_idx, perf in enumerate(perf_modes):
        if perf_idx > 0:
            append_log("Performance-Modus fehlgeschlagen — Fallback auf stabilen SMB-Modus …")
        mode_note = " | SMB Performance" if perf else ""
        cmd = [
            "rclone",
            "sync",
            src_url,
            dst_url,
            *_rclone_sync_args(source_ep, dest_ep, smb_performance=perf),
        ]
        append_log(f"SYNC{mode_note} {' '.join(cmd[:6])}… → {dst_url[:100]}…")
        code, lines, cancelled = _run_rclone_sync_once(
            cmd,
            plan_id=plan_id,
            route_idx=route_idx,
            route_total=route_total,
        )
        last_lines = lines
        if cancelled or (plan_id and is_cancelled(plan_id)):
            tail = "\n".join(lines[-25:])
            append_log("SYNC cancelled")
            return False, "cancelled", {"tail": tail}

        output = "\n".join(lines)
        tail = "\n".join(output.strip().splitlines()[-25:])
        if code == 0 and not _rclone_had_errors(output):
            if perf and smb_performance:
                append_log("SMB Performance-Modus erfolgreich")
            append_log("SYNC OK")
            return True, "ok", {"tail": tail[-1200:]}

        append_log(f"SYNC FAIL exit {code}\n{tail[-800:]}")
        if not perf:
            return False, "sync_error", {"exit_code": code, "tail": tail}

    tail = "\n".join(last_lines[-25:])
    return False, "sync_error", {"tail": tail}
