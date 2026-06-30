# -*- coding: utf-8 -*-

from __future__ import annotations



import threading

from datetime import datetime, timezone

from typing import Any



from devices import endpoint_label

from i18n import get_lang, set_thread_lang, t

from notify import notify_job_fail

from progress import clear_progress, set_progress

from schedule_util import clamp_interval, schedule_next_run

from store import append_log, get_job, load_jobs, save_jobs, update_job

from verify import run_verify_endpoints



_running_lock = threading.Lock()

_running_ids: set[str] = set()





def list_active_jobs() -> list[str]:

    with _running_lock:

        return sorted(_running_ids)





def _set_running(job_id: str, on: bool) -> None:

    with _running_lock:

        if on:

            _running_ids.add(job_id)

        else:

            _running_ids.discard(job_id)





def start_job(job_id: str, lang: str | None = None) -> tuple[bool, str]:

    job = get_job(job_id)

    if not job:

        return False, t("err.job_not_found", lang or get_lang())

    with _running_lock:

        if job_id in _running_ids:

            return False, t("err.job_running", lang or get_lang())



    lng = lang or get_lang()



    def worker() -> None:

        set_thread_lang(lng)

        _set_running(job_id, True)

        set_progress(

            job_id,

            phase="start",

            percent=0,

            message=t("progress.starting", lng),

            indeterminate=True,

        )

        now = datetime.now(timezone.utc).isoformat()

        update_job(

            job_id,

            last_run=now,

            last_status="running",

            last_message=t("job.running", lng),

            last_details={},

        )

        src_ep = job.get("source") or {}

        dst_ep = job.get("dest") or {}

        route = f"{endpoint_label(src_ep)} <=> {endpoint_label(dst_ep)}"

        append_log(f"JOB {job.get('name', job_id)} START")

        append_log(f"COMPARE {route}")

        try:

            ok, code, details = run_verify_endpoints(src_ep, dst_ep, job_id=job_id)

            if ok:

                msg = t("job.ok", lng)

                set_progress(

                    job_id,

                    phase="done",

                    percent=100,

                    message=msg,

                    indeterminate=False,

                )

                update_job(

                    job_id,

                    last_status="ok",

                    last_message=msg,

                    last_details=details,

                    last_notified_fail=None,

                )

                append_log(f"JOB {job_id} OK")

            else:

                if code == "differences":

                    missing = int(details.get("missing_on_dst") or 0)

                    differ = int(details.get("differ_count") or 0)

                    if missing or differ:

                        msg = t("job.fail_diff_backup", lng, missing=missing, differ=differ)

                    else:

                        cnt = details.get("change_count", 0)

                        msg = (

                            t("job.fail_diff", lng, count=cnt)

                            if cnt > 0

                            else t("job.fail_diff_unknown", lng)

                        )

                elif code in ("source_missing", "dest_missing", "timeout", "rsync_error"):

                    msg = t(f"job.fail_{code}", lng)

                else:

                    msg = t("job.fail_diff_unknown", lng)

                set_progress(

                    job_id,

                    phase="done",

                    percent=100,

                    message=msg,

                    indeterminate=False,

                )

                fresh = get_job(job_id) or job

                last_notified = fresh.get("last_notified_fail")

                update_job(

                    job_id,

                    last_status="fail",

                    last_message=msg,

                    last_details=details,

                )

                append_log(f"JOB {job_id} FAIL: {msg}")

                if last_notified != now:

                    notify_job_fail(job.get("name", job_id), route, msg, lng)

                    update_job(job_id, last_notified_fail=now)

        except Exception as ex:

            append_log(f"JOB {job_id} ERROR: {ex}")

            err_msg = str(ex)[:400]

            set_progress(

                job_id,

                phase="error",

                percent=100,

                message=str(ex)[:200],

                indeterminate=False,

            )

            update_job(

                job_id,

                last_status="fail",

                last_message=err_msg,

                last_details={},

            )

            fresh = get_job(job_id) or job

            if fresh.get("last_notified_fail") != now:

                notify_job_fail(job.get("name", job_id), route, err_msg, lng)

                update_job(job_id, last_notified_fail=now)

        finally:

            _set_running(job_id, False)

            clear_progress(job_id)

            set_thread_lang(None)

            current = get_job(job_id)

            if current and current.get("auto_verify"):

                schedule_next_run(job_id, clamp_interval(current.get("interval_minutes")))



    threading.Thread(target=worker, daemon=True).start()

    return True, t("job.started", lng)





def update_job_fields(job_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:

    job = get_job(job_id)

    if not job:

        return None

    allowed = {

        "name",

        "auto_verify",

        "interval_minutes",

        "source",

        "dest",

    }

    patch: dict[str, Any] = {}

    for key, val in fields.items():

        if key not in allowed:

            continue

        if key == "name":

            patch[key] = str(val or "").strip() or job.get("name", "")

        elif key == "auto_verify":

            patch[key] = bool(val)

        elif key == "interval_minutes":

            patch[key] = clamp_interval(val)

        else:

            patch[key] = val

    if patch.get("auto_verify") and not job.get("next_run_at"):

        schedule_next_run(
            job_id,
            patch.get("interval_minutes", job.get("interval_minutes", 1440)),
            soon=True,
        )

    if patch.get("auto_verify") is False:

        patch["next_run_at"] = None

    update_job(job_id, **patch)

    return get_job(job_id)





def delete_job(job_id: str) -> bool:

    with _running_lock:

        if job_id in _running_ids:

            return False

    jobs = [j for j in load_jobs() if j.get("id") != job_id]

    if len(jobs) == len(load_jobs()):

        return False

    save_jobs(jobs)

    append_log(f"JOB deleted {job_id}")

    return True


