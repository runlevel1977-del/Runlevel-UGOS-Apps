# -*- coding: utf-8 -*-
"""In-memory job progress and cancel for running plans."""
from __future__ import annotations

import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

from devices import endpoint_label
from i18n import get_lang, t

_jobs_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_cancel_lock = threading.Lock()
_cancel_ids: set[str] = set()
_proc_lock = threading.Lock()
_procs: dict[str, subprocess.Popen[Any]] = {}

_RCLONE_STAT = re.compile(
    r"([\d.,]+\s*(?:Ki|Mi|Gi|Ti|K|M|G|T)?i?B)\s*/\s*"
    r"([\d.,]+\s*(?:Ki|Mi|Gi|Ti|K|M|G|T)?i?B),\s*(\d+)%"
    r"(?:,\s*([^,]+))?,\s*ETA\s*(.+)",
    re.IGNORECASE,
)
_RCLONE_CHECKS = re.compile(
    r"Checks:\s*(\d+)\s*/\s*(\d+),\s*(\d+)%",
    re.IGNORECASE,
)


def parse_progress_line(line: str) -> dict[str, Any] | None:
    """Parse rclone one-line stats into progress fields."""
    match = _RCLONE_STAT.search(line)
    if match:
        eta = (match.group(5) or "").strip()
        if eta in ("-", "—", ""):
            eta = ""
        speed = (match.group(4) or "").strip()
        if speed in ("-", "—", "0 B/s", "0 B/s,"):
            speed = speed if speed.startswith("0") else speed
        return {
            "percent": min(100, int(match.group(3))),
            "detail": f"{match.group(1)} / {match.group(2)}",
            "speed": speed,
            "eta": eta,
        }
    check = _RCLONE_CHECKS.search(line)
    if check:
        return {
            "percent": min(100, int(check.group(3))),
            "detail": f"Checks {check.group(1)} / {check.group(2)}",
            "speed": "",
            "eta": "",
        }
    if "Building file list" in line or "build file list" in line.lower():
        return {"percent": 0, "detail": "Building file list…", "speed": "", "eta": ""}
    if "100%" in line and "ETA" in line.upper():
        return {"percent": 100, "detail": "", "speed": "", "eta": ""}
    return None


def update_route_progress(
    plan_id: str,
    *,
    route_note: str,
    route_idx: int,
    route_total: int,
) -> None:
    """Set multi-folder route label without clearing transfer stats."""
    set_job(
        plan_id,
        phase="sync",
        route_note=route_note,
        route_idx=route_idx,
        route_total=route_total,
    )


def update_rclone_progress(
    plan_id: str,
    line: str,
    *,
    route_idx: int = 1,
    route_total: int = 1,
) -> None:
    """Merge rclone stats with route progress for the jobs panel."""
    parsed = parse_progress_line(line)
    if not parsed:
        return
    route_pct = int(parsed.get("percent") or 0)
    if route_total > 1:
        overall = int(((route_idx - 1) + route_pct / 100.0) / route_total * 100)
    else:
        overall = route_pct
    eta = parsed.get("eta") or ""
    speed = parsed.get("speed") or ""
    set_job(
        plan_id,
        phase="sync",
        percent=overall,
        detail=parsed.get("detail") or "",
        speed=speed,
        eta=eta,
        route_idx=route_idx,
        route_total=route_total,
    )


def init_job(plan: dict[str, Any], *, lang: str | None = None) -> None:
    """Register a new active job for UI polling."""
    lng = lang or get_lang()
    plan_id = str(plan.get("id") or "")
    src = plan.get("source") or {}
    dst = plan.get("dest") or {}
    with _jobs_lock:
        _jobs[plan_id] = {
            "plan_id": plan_id,
            "name": plan.get("name") or plan_id,
            "source_label": endpoint_label(src),
            "dest_label": endpoint_label(dst),
            "status": "running",
            "phase": "wol",
            "percent": 0,
            "detail": t("jobs.phase.wol", lng),
            "route_note": "",
            "route_idx": 0,
            "route_total": 0,
            "speed": "",
            "eta": "",
            "message": "",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }


def set_job(plan_id: str, **fields: Any) -> None:
    """Update fields on an active job."""
    with _jobs_lock:
        if plan_id in _jobs:
            _jobs[plan_id].update(fields)


def list_active_jobs() -> list[dict[str, Any]]:
    """Return snapshot of active/recent jobs for API."""
    with _jobs_lock:
        return [dict(job) for job in _jobs.values()]


def clear_cancel(plan_id: str) -> None:
    """Clear cancel flag when a run finishes."""
    with _cancel_lock:
        _cancel_ids.discard(plan_id)


def request_cancel(plan_id: str) -> None:
    """Mark plan for cancellation and terminate subprocess if any."""
    with _cancel_lock:
        _cancel_ids.add(plan_id)
    with _proc_lock:
        proc = _procs.get(plan_id)
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
        time.sleep(0.4)
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def is_cancelled(plan_id: str) -> bool:
    """Return True when stop was requested for this plan."""
    with _cancel_lock:
        return plan_id in _cancel_ids


def register_proc(plan_id: str, proc: subprocess.Popen[Any]) -> None:
    """Track rclone subprocess for stop."""
    with _proc_lock:
        _procs[plan_id] = proc


def unregister_proc(plan_id: str) -> None:
    """Drop subprocess handle after run."""
    with _proc_lock:
        _procs.pop(plan_id, None)


def finish_job(plan_id: str, *, status: str, message: str = "", lang: str | None = None) -> None:
    """Mark job complete and remove from panel after delay."""
    lng = lang or get_lang()
    label = {
        "ok": t("jobs.done", lng),
        "error": t("jobs.failed", lng),
        "cancelled": t("jobs.cancelled", lng),
    }.get(status, status)
    set_job(
        plan_id,
        status=status,
        phase="done",
        percent=100 if status == "ok" else 0,
        detail=message or label,
        speed="",
        eta="",
        message=message,
    )
    _remove_job_later(plan_id)


def _remove_job_later(plan_id: str, delay: float = 12.0) -> None:
    def _drop() -> None:
        time.sleep(delay)
        with _jobs_lock:
            _jobs.pop(plan_id, None)

    threading.Thread(target=_drop, daemon=True).start()
