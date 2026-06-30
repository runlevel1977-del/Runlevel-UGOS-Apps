# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from store import update_job


def clamp_interval(minutes: Any) -> int:
    try:
        v = int(minutes)
    except (TypeError, ValueError):
        v = 1440
    return max(5, min(10080, v))


def parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def schedule_next_run(job_id: str, interval_minutes: int, *, soon: bool = False) -> None:
    if soon:
        nxt = datetime.now(timezone.utc)
    else:
        mins = clamp_interval(interval_minutes)
        nxt = datetime.now(timezone.utc) + timedelta(minutes=mins)
    update_job(job_id, next_run_at=nxt.isoformat())


def ensure_next_run(job: dict) -> None:
    if not job.get("auto_verify"):
        return
    if parse_iso(job.get("next_run_at")):
        return
    schedule_next_run(job["id"], int(job.get("interval_minutes") or 1440), soon=True)
