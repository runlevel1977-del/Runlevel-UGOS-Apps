# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time

from i18n import env_lang, set_thread_lang
from plans import list_active_plans, plan_due_now, start_plan
from store import append_log, load_plans

_started = False
_lock = threading.Lock()
_TICK_SEC = 30


def _scheduler_loop() -> None:
    lng = env_lang()
    set_thread_lang(lng)
    append_log("Wake & Sync scheduler started")
    while True:
        try:
            active = set(list_active_plans())
            for plan in load_plans():
                pid = plan.get("id")
                if not pid or pid in active:
                    continue
                if plan_due_now(plan):
                    ok, msg = start_plan(pid, lang=lng, manual=False)
                    if ok:
                        append_log(f"SCHEDULER triggered {plan.get('name', pid)}")
                    else:
                        append_log(f"SCHEDULER skip {pid}: {msg}")
        except Exception as ex:
            append_log(f"SCHEDULER error: {ex}")
        time.sleep(_TICK_SEC)


def start_scheduler() -> None:
    global _started
    with _lock:
        if _started:
            return
        threading.Thread(target=_scheduler_loop, daemon=True, name="ws-scheduler").start()
        _started = True
