# -*- coding: utf-8 -*-
"""Auto-sync scheduling: 24/7 interval or time window + interval (cron-like)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

ALLOWED_INTERVALS = (15, 30, 45, 60, 120)


def _local_tz() -> ZoneInfo:
    tz_name = os.environ.get("TZ", "Europe/Berlin")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Europe/Berlin")


def parse_hhmm(raw: str | None) -> tuple[int, int] | None:
    s = (raw or "").strip()
    if not s or ":" not in s:
        return None
    parts = s.split(":", 1)
    try:
        h, m = int(parts[0]), int(parts[1])
    except (TypeError, ValueError):
        return None
    if 0 <= h <= 23 and 0 <= m <= 59:
        return h, m
    return None


def format_hhmm(h: int, m: int) -> str:
    return f"{h:02d}:{m:02d}"


def snap_interval(minutes: Any) -> int:
    try:
        v = int(minutes)
    except (TypeError, ValueError):
        v = 30
    if v in ALLOWED_INTERVALS:
        return v
    return min(ALLOWED_INTERVALS, key=lambda x: abs(x - v))


def _normalize_schedule_type(raw: str | None) -> str:
    st = (raw or "window").strip().lower()
    if st in ("interval", "always"):
        return "always"
    if st in ("daily", "window"):
        return "window"
    return "window"


def _default_window(existing: dict | None) -> tuple[str, str]:
    if not existing:
        return "15:30", "22:00"
    if existing.get("schedule_type") == "daily":
        start = (existing.get("run_at") or "22:00").strip()
        return start, "23:59"
    start = (existing.get("window_start") or existing.get("run_at") or "15:30").strip()
    end = (existing.get("window_end") or "22:00").strip()
    return start, end


def normalize_schedule_fields(body: dict, existing: dict | None = None) -> dict[str, Any]:
    st = _normalize_schedule_type(
        body.get("schedule_type") or (existing or {}).get("schedule_type")
    )
    interval = snap_interval(
        body.get("interval_minutes", (existing or {}).get("interval_minutes", 30))
    )
    win_start, win_end = _default_window(existing)
    window_start = (body.get("window_start") or win_start).strip()
    window_end = (body.get("window_end") or win_end).strip()
    if not parse_hhmm(window_start):
        window_start = "15:30"
    if not parse_hhmm(window_end):
        window_end = "22:00"
    if st == "window":
        sh, sm = parse_hhmm(window_start) or (15, 30)
        eh, em = parse_hhmm(window_end) or (22, 0)
        if sh * 60 + sm >= eh * 60 + em:
            window_end = format_hhmm(min(23, sh + 2), sm)
    return {
        "schedule_type": st,
        "window_start": window_start,
        "window_end": window_end,
        "interval_minutes": interval,
    }


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _minutes_since_midnight(h: int, m: int) -> int:
    return h * 60 + m


def _in_time_window(now: datetime, start: tuple[int, int], end: tuple[int, int]) -> bool:
    now_m = _minutes_since_midnight(now.hour, now.minute)
    start_m = _minutes_since_midnight(start[0], start[1])
    end_m = _minutes_since_midnight(end[0], end[1])
    if start_m <= end_m:
        return start_m <= now_m <= end_m
    return now_m >= start_m or now_m <= end_m


def _interval_due(last_run: str | None, interval_min: int, now_ts: float) -> bool:
    if not last_run:
        return True
    dt = _parse_iso(last_run)
    if not dt:
        return True
    return (now_ts - dt.timestamp()) >= interval_min * 60


def profile_due_now(profile: dict[str, Any], now_ts: float | None = None) -> bool:
    if not profile.get("auto_sync") or profile.get("delete_source_after"):
        return False
    st = _normalize_schedule_type(profile.get("schedule_type"))
    interval = snap_interval(profile.get("interval_minutes") or 30)
    ts = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
    if st == "window":
        start = parse_hhmm(profile.get("window_start") or profile.get("run_at"))
        end = parse_hhmm(profile.get("window_end") or "22:00")
        if not start or not end:
            return False
        now = datetime.now(_local_tz())
        if not _in_time_window(now, start, end):
            return False
    return _interval_due(profile.get("last_run"), interval, ts)


def schedule_label(profile: dict[str, Any], lng: str, t_fn) -> str:
    if not profile.get("auto_sync"):
        return "—"
    interval = snap_interval(profile.get("interval_minutes") or 30)
    st = _normalize_schedule_type(profile.get("schedule_type"))
    if st == "window":
        return t_fn(
            "profile.schedule_window",
            lng,
            start=profile.get("window_start") or "15:30",
            end=profile.get("window_end") or "22:00",
            min=interval,
        )
    return t_fn("profile.schedule_always", lng, min=interval)
