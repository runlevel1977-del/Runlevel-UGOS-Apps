# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from devices import endpoint_label
from i18n import get_lang, set_thread_lang, t
from notify import notify_event
from store import append_log, get_plan, load_plans, save_plans, update_plan
from sync import run_sync
from wol import send_wol, wait_for_host

_running_lock = threading.Lock()
_running_ids: set[str] = set()

SCHEDULE_TYPES = ("daily", "weekly", "biweekly", "monthly")


def list_active_plans() -> list[str]:
    with _running_lock:
        return sorted(_running_ids)


def _set_running(plan_id: str, on: bool) -> None:
    with _running_lock:
        if on:
            _running_ids.add(plan_id)
        else:
            _running_ids.discard(plan_id)


def _local_tz() -> ZoneInfo:
    import os

    tz_name = os.environ.get("TZ", "Europe/Berlin")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Europe/Berlin")


def _today_key() -> str:
    return datetime.now(_local_tz()).strftime("%Y-%m-%d")


def _parse_hhmm(raw: str) -> tuple[int, int] | None:
    s = (raw or "").strip()
    if not s or ":" not in s:
        return None
    parts = s.split(":", 1)
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except ValueError:
        pass
    return None


def _clamp_weekday(raw: Any) -> int:
    try:
        wd = int(raw)
    except (TypeError, ValueError):
        wd = 0
    return max(0, min(6, wd))


def _clamp_monthly_week(raw: Any) -> int:
    try:
        mw = int(raw)
    except (TypeError, ValueError):
        mw = 1
    return mw if mw in (1, 2, 3, 4, -1) else 1


def normalize_schedule_fields(
    body: dict[str, Any], *, today: date | None = None, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    st = (body.get("schedule_type") or (existing or {}).get("schedule_type") or "daily").strip().lower()
    if st not in SCHEDULE_TYPES:
        st = "daily"
    weekday = _clamp_weekday(body.get("weekday", (existing or {}).get("weekday", 0)))
    monthly_week = _clamp_monthly_week(body.get("monthly_week", (existing or {}).get("monthly_week", 1)))
    anchor = (body.get("schedule_anchor") or "").strip()
    if st == "biweekly":
        old_st = (existing or {}).get("schedule_type") or "daily"
        old_anchor = (existing or {}).get("schedule_anchor") or ""
        old_wd = _clamp_weekday((existing or {}).get("weekday", 0))
        if not anchor:
            if old_st == "biweekly" and old_anchor and old_wd == weekday:
                anchor = old_anchor
            else:
                anchor = _next_weekday_date(weekday, today).isoformat()
    else:
        anchor = ""
    return {
        "schedule_type": st,
        "weekday": weekday,
        "monthly_week": monthly_week,
        "schedule_anchor": anchor,
    }


def _next_weekday_date(weekday: int, from_date: date | None = None) -> date:
    d = from_date or datetime.now(_local_tz()).date()
    days_ahead = (weekday - d.weekday()) % 7
    return d if days_ahead == 0 else d + timedelta(days=days_ahead)


def _monthly_weekday_match(d: date, weekday: int, nth: int) -> bool:
    if d.weekday() != weekday:
        return False
    if nth == -1:
        return (d + timedelta(days=7)).month != d.month
    first = d.replace(day=1)
    days_ahead = (weekday - first.weekday()) % 7
    first_occ = first + timedelta(days=days_ahead)
    target = first_occ + timedelta(weeks=nth - 1)
    return d == target


def _schedule_date_matches(plan: dict[str, Any], today: date) -> bool:
    st = plan.get("schedule_type") or "daily"
    if st == "daily":
        return True
    weekday = _clamp_weekday(plan.get("weekday", 0))
    if today.weekday() != weekday:
        return False
    if st == "weekly":
        return True
    if st == "biweekly":
        anchor_s = (plan.get("schedule_anchor") or "").strip()
        try:
            anchor = date.fromisoformat(anchor_s)
        except ValueError:
            anchor = _next_weekday_date(weekday, today)
        weeks = (today - anchor).days // 7
        return weeks >= 0 and weeks % 2 == 0
    if st == "monthly":
        return _monthly_weekday_match(today, weekday, _clamp_monthly_week(plan.get("monthly_week", 1)))
    return False


def schedule_label(plan: dict[str, Any], lang: str | None = None) -> str:
    lng = lang or get_lang()
    hm = _parse_hhmm(plan.get("run_at") or "")
    time_s = plan.get("run_at") or "?" if not hm else f"{hm[0]:02d}:{hm[1]:02d}"
    st = plan.get("schedule_type") or "daily"
    if st == "daily":
        return t("schedule.daily", lng, time=time_s)
    wd = t(f"weekday.{_clamp_weekday(plan.get('weekday', 0))}", lng)
    if st == "weekly":
        return t("schedule.weekly", lng, weekday=wd, time=time_s)
    if st == "biweekly":
        return t("schedule.biweekly", lng, weekday=wd, time=time_s)
    if st == "monthly":
        mw = _clamp_monthly_week(plan.get("monthly_week", 1))
        nth = t("schedule.monthly_last", lng) if mw == -1 else t(f"schedule.monthly_nth.{mw}", lng)
        return t("schedule.monthly", lng, nth=nth, weekday=wd, time=time_s)
    return time_s


def plan_due_now(plan: dict) -> bool:
    if not plan.get("enabled"):
        return False
    hm = _parse_hhmm(plan.get("run_at"))
    if not hm:
        return False
    now = datetime.now(_local_tz())
    if now.hour != hm[0] or now.minute != hm[1]:
        return False
    if plan.get("last_run_date") == _today_key():
        return False
    return _schedule_date_matches(plan, now.date())


def start_plan(plan_id: str, lang: str | None = None, *, manual: bool = False) -> tuple[bool, str]:
    plan = get_plan(plan_id)
    if not plan:
        return False, t("err.plan_not_found", lang or get_lang())
    with _running_lock:
        if plan_id in _running_ids:
            return False, t("err.plan_running", lang or get_lang())

    lng = lang or get_lang()

    def worker() -> None:
        set_thread_lang(lng)
        _set_running(plan_id, True)
        today = _today_key()
        now_iso = datetime.now(timezone.utc).isoformat()
        update_plan(
            plan_id,
            last_run=now_iso,
            last_run_date=today,
            last_status="running",
            last_message=t("plan.running", lng),
        )
        name = plan.get("name", plan_id)
        route = f"{endpoint_label(plan.get('source') or {})} → {endpoint_label(plan.get('dest') or {})}"
        append_log(f"PLAN {name} START ({'manual' if manual else 'scheduled'})")
        append_log(f"ROUTE {route}")

        try:
            wake_ok, wake_msg = send_wol(
                plan.get("target_mac", ""),
                plan.get("wake_broadcast") or None,
                target_ip=plan.get("target_ip", ""),
            )
            append_log(f"WOL {'OK' if wake_ok else 'FAIL'}: {wake_msg}")
            if not wake_ok:
                msg = t("plan.fail_wol", lng, detail=wake_msg[:200])
                update_plan(plan_id, last_status="fail", last_message=msg)
                notify_event(name, route, msg, lng, success=False)
                return

            wait_min = max(1, min(120, int(plan.get("ready_wait_minutes") or 20)))
            ready_ok, ready_msg = wait_for_host(
                plan.get("target_ip", ""),
                int(plan.get("ready_port") or 445),
                timeout_sec=wait_min * 60,
            )
            append_log(f"READY {'OK' if ready_ok else 'FAIL'}: {ready_msg}")
            if not ready_ok:
                msg = t("plan.fail_wait", lng, detail=ready_msg[:200])
                update_plan(plan_id, last_status="fail", last_message=msg)
                notify_event(name, route, msg, lng, success=False)
                return

            ok, code, details = run_sync(plan.get("source") or {}, plan.get("dest") or {})
            if ok:
                msg = t("plan.ok", lng)
                update_plan(plan_id, last_status="ok", last_message=msg, last_details=details)
                append_log(f"PLAN {plan_id} OK")
                notify_event(name, route, msg, lng, success=True)
            else:
                tail = (details.get("tail") or code)[:300]
                msg = t("plan.fail_sync", lng, detail=tail)
                update_plan(plan_id, last_status="fail", last_message=msg, last_details=details)
                append_log(f"PLAN {plan_id} FAIL: {msg}")
                notify_event(name, route, msg, lng, success=False)
        except Exception as ex:
            err = str(ex)[:400]
            append_log(f"PLAN {plan_id} ERROR: {ex}")
            update_plan(plan_id, last_status="fail", last_message=err)
            notify_event(name, route, err, lng, success=False)
        finally:
            _set_running(plan_id, False)
            set_thread_lang(None)

    threading.Thread(target=worker, daemon=True).start()
    return True, t("plan.started", lng)


def delete_plan(plan_id: str) -> bool:
    with _running_lock:
        if plan_id in _running_ids:
            return False
    plans = [p for p in load_plans() if p.get("id") != plan_id]
    if len(plans) == len(load_plans()):
        return False
    save_plans(plans)
    append_log(f"PLAN deleted {plan_id}")
    return True
