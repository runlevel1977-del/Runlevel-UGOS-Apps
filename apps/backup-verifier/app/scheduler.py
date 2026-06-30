# -*- coding: utf-8 -*-
"""Background scheduler for auto-verify jobs."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from i18n import env_lang, set_thread_lang
from jobs import list_active_jobs, start_job
from schedule_util import ensure_next_run, parse_iso, schedule_next_run
from store import append_log, load_jobs

_started = False
_lock = threading.Lock()
_TICK_SEC = 60


def _scheduler_loop() -> None:
    lng = env_lang()
    set_thread_lang(lng)
    append_log("Scheduler started")
    while True:
        try:
            now = datetime.now(timezone.utc)
            active = set(list_active_jobs())
            for job in load_jobs():
                jid = job.get("id")
                if not jid or not job.get("auto_verify"):
                    continue
                if jid in active:
                    continue
                ensure_next_run(job)
                nxt = parse_iso(job.get("next_run_at"))
                if nxt and now < nxt:
                    continue
                ok, msg = start_job(jid, lang=lng)
                if ok:
                    schedule_next_run(jid, int(job.get("interval_minutes") or 1440))
                    append_log(f"SCHEDULER started job {job.get('name', jid)}")
                else:
                    append_log(f"SCHEDULER skip {jid}: {msg}")
        except Exception as ex:
            append_log(f"SCHEDULER error: {ex}")
        time.sleep(_TICK_SEC)


def start_scheduler() -> None:
    global _started
    with _lock:
        if _started:
            return
        threading.Thread(target=_scheduler_loop, daemon=True, name="bv-scheduler").start()
        _started = True
