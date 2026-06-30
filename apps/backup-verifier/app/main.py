# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from compliance import (
    compliance_context,
    consent_required_response,
    has_privacy_consent,
    save_privacy_consent,
)
from flask import Flask, g, jsonify, make_response, render_template, request

from devices import (
    LOCAL_ID,
    add_smb_device,
    browse,
    delete_device,
    endpoint_label,
    get_device,
    load_devices,
    test_smb,
)
from i18n import LANG_COOKIE, bundle, get_lang, lang_from_request, normalize_lang, t
from icon_sync import sync_appcenter_icon
from jobs import delete_job, list_active_jobs, start_job, update_job_fields
from notify import public_settings, save_notify_settings, send_test_notifications
from progress import snapshot as progress_snapshot
from schedule_util import clamp_interval, schedule_next_run
from scheduler import start_scheduler
from network_scan import probe_host, scan_config, scan_lan
from store import DATA_DIR, append_log, load_jobs, new_job_id, read_log_tail, save_jobs
from volumes import list_volumes, normalize_volume_id

app = Flask(__name__)
APP_VERSION = os.environ.get("BACKUP_VERIFIER_VERSION", "0.3.14")
NAS_ADMIN_URL = os.environ.get(
    "NAS_ADMIN_URL",
    "https://github.com/runlevel1977-del/UgreenNASAdmin/releases/latest",
)


@app.before_request
def _set_lang():
    g.lang = lang_from_request(request)


def _lang_cookie_response(resp, lang: str):
    resp.set_cookie(LANG_COOKIE, lang, max_age=365 * 24 * 3600, path="/", samesite="Lax")
    return resp


@app.context_processor
def _inject_i18n():
    lng = getattr(g, "lang", "en")

    def _t(key: str, **fmt):
        return t(key, lng, **fmt)

    return {
        "lang": lng,
        "t": _t,
        "i18n": bundle(lng),
        "nas_admin_url": NAS_ADMIN_URL,
        **compliance_context(DATA_DIR),
    }


def _ep_key(ep: dict) -> str:
    return (
        f"{ep.get('device_id')}|{ep.get('volume') or ''}|"
        f"{ep.get('share')}|{ep.get('path')}"
    )


def _normalize_endpoint(ep: dict) -> dict:
    device_id = (ep.get("device_id") or LOCAL_ID).strip() or LOCAL_ID
    dev = get_device(device_id)
    out = {
        "device_id": device_id,
        "path": (ep.get("path") or "").strip().strip("/"),
    }
    if dev and dev.get("type") == "smb":
        out["share"] = (ep.get("share") or "").strip()
    else:
        out["volume"] = normalize_volume_id(ep.get("volume"))
    return out


def _validate_endpoint(ep: dict, lng: str) -> str | None:
    device_id = ep.get("device_id") or LOCAL_ID
    dev = get_device(device_id)
    if not dev:
        return t("err.device_not_found", lng)
    if dev.get("type") == "smb":
        if not ep.get("share"):
            return t("err.smb_share_missing", lng)
    elif dev.get("type") == "local":
        if not ep.get("volume"):
            return t("err.pick_volume_first", lng)
    return None


@app.route("/health")
def health():
    return jsonify({"ok": True, "version": APP_VERSION, "lang": get_lang()})


@app.route("/")
def index():
    resp = make_response(render_template("index.html", version=APP_VERSION))
    picked = normalize_lang(request.args.get("lang"))
    if picked:
        _lang_cookie_response(resp, picked)
    return resp


@app.route("/api/lang", methods=["POST"])
def api_set_lang():
    body = request.get_json(force=True, silent=True) or {}
    picked = normalize_lang(body.get("lang"))
    if not picked:
        return jsonify({"ok": False, "error": "lang must be de or en"}), 400
    resp = jsonify({"ok": True, "lang": picked, "i18n": bundle(picked)})
    return _lang_cookie_response(resp, picked)


@app.route("/api/config")
def api_config():
    return jsonify({
        "ok": True,
        "lang": get_lang(),
        "volumes": list_volumes(),
        **scan_config(),
    })


@app.route("/api/devices", methods=["GET"])
def api_devices():
    devices = load_devices()
    for d in devices:
        if d.get("id") == LOCAL_ID:
            d["name"] = t("device.this_nas", get_lang())
    return jsonify(devices)


@app.route("/api/devices/scan", methods=["GET"])
def api_scan():
    found, message, cfg = scan_lan()
    return jsonify({"ok": True, "hosts": found, "message": message, "config": cfg})


@app.route("/api/devices/probe", methods=["GET"])
def api_probe_host():
    host = (request.args.get("host") or "").strip()
    if not host:
        return jsonify({"ok": False, "error": t("err.host_missing", get_lang())}), 400
    row = probe_host(host)
    if not row:
        return jsonify({
            "ok": True,
            "host": host,
            "reachable": False,
            "message": t("probe.no_services", get_lang()),
        })
    return jsonify({"ok": True, "reachable": True, **row})


@app.route("/api/devices", methods=["POST"])
def api_add_device():

    if not has_privacy_consent(DATA_DIR):
        body, code = consent_required_response()
        return jsonify(body), code
    body = request.get_json(force=True, silent=True) or {}
    host = (body.get("host") or "").strip()
    name = (body.get("name") or host).strip()
    user = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not host:
        return jsonify({"ok": False, "error": t("err.host_missing", get_lang())}), 400
    ok, msg = test_smb(host, user, password)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    dev = add_smb_device(name, host, user, password)
    append_log(f"Device saved: {name} ({host})")
    return jsonify({"ok": True, "device": {**dev, "password": "***"}})


@app.route("/api/devices/<device_id>", methods=["DELETE"])
def api_del_device(device_id: str):
    if not delete_device(device_id):
        return jsonify({"ok": False, "error": t("err.cannot_delete", get_lang())}), 400
    return jsonify({"ok": True})


@app.route("/api/browse", methods=["GET"])
def api_browse():
    device_id = request.args.get("device_id", LOCAL_ID)
    path = request.args.get("path", "")
    share = request.args.get("share", "")
    volume = request.args.get("volume", "")
    return jsonify(browse(device_id, path, share, volume))


@app.route("/api/jobs", methods=["GET"])
def api_list_jobs():
    active = set(list_active_jobs())
    prog = progress_snapshot()
    out = []
    for j in load_jobs():
        row = j.copy()
        if isinstance(row.get("source"), dict):
            row["source_label"] = endpoint_label(row["source"])
        if isinstance(row.get("dest"), dict):
            row["dest_label"] = endpoint_label(row["dest"])
        jid = row.get("id")
        row["running"] = jid in active
        if jid in prog:
            row["progress"] = prog[jid]
        out.append(row)
    return jsonify(out)


@app.route("/api/jobs", methods=["POST"])
def api_create_job():
    body = request.get_json(force=True, silent=True) or {}
    lng = get_lang()
    name = (body.get("name") or "").strip() or t("job.default_name", lng)
    source = body.get("source")
    dest = body.get("dest")
    if not isinstance(source, dict) or not isinstance(dest, dict):
        return jsonify({"ok": False, "error": t("err.pick_both", lng)}), 400

    source = _normalize_endpoint(source)
    dest = _normalize_endpoint(dest)
    err = _validate_endpoint(source, lng) or _validate_endpoint(dest, lng)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    if _ep_key(source) == _ep_key(dest):
        return jsonify({"ok": False, "error": t("err.same_path", lng)}), 400

    auto_verify = bool(body.get("auto_verify"))
    interval_minutes = clamp_interval(body.get("interval_minutes", 1440))
    job = {
        "id": new_job_id(),
        "name": name,
        "source": source,
        "dest": dest,
        "auto_verify": auto_verify,
        "interval_minutes": interval_minutes,
        "next_run_at": None,
        "last_run": None,
        "last_status": None,
        "last_message": "",
        "last_details": {},
        "last_notified_fail": None,
    }
    jobs = load_jobs()
    jobs.append(job)
    save_jobs(jobs)
    if auto_verify:
        schedule_next_run(job["id"], interval_minutes, soon=True)
        job = next((j for j in load_jobs() if j["id"] == job["id"]), job)
    append_log(
        f"JOB saved: {name} | {endpoint_label(source)} <=> {endpoint_label(dest)}"
    )
    return jsonify({"ok": True, "job": job})


@app.route("/api/jobs/<job_id>", methods=["PATCH"])
def api_update_job(job_id: str):
    body = request.get_json(force=True, silent=True) or {}
    lng = get_lang()
    if "source" in body or "dest" in body:
        source = body.get("source")
        dest = body.get("dest")
        if isinstance(source, dict):
            body["source"] = _normalize_endpoint(source)
            err = _validate_endpoint(body["source"], lng)
            if err:
                return jsonify({"ok": False, "error": err}), 400
        if isinstance(dest, dict):
            body["dest"] = _normalize_endpoint(dest)
            err = _validate_endpoint(body["dest"], lng)
            if err:
                return jsonify({"ok": False, "error": err}), 400
    updated = update_job_fields(job_id, body)
    if not updated:
        return jsonify({"ok": False, "error": t("err.job_not_found", lng)}), 404
    row = updated.copy()
    row["source_label"] = endpoint_label(row.get("source") or {})
    row["dest_label"] = endpoint_label(row.get("dest") or {})
    return jsonify({"ok": True, "job": row})


@app.route("/api/notifications", methods=["GET"])
def api_get_notifications():
    return jsonify({"ok": True, "settings": public_settings()})


@app.route("/api/notifications", methods=["POST"])
def api_save_notifications():

    if not has_privacy_consent(DATA_DIR):
        body, code = consent_required_response()
        return jsonify(body), code
    body = request.get_json(force=True, silent=True) or {}
    settings = save_notify_settings(body)
    append_log("Notification settings saved")
    return jsonify({"ok": True, "settings": settings})


@app.route("/api/notifications/test", methods=["POST"])
def api_test_notifications():
    results = send_test_notifications(get_lang())
    ok = any(r.get("ok") for r in results)
    return jsonify({"ok": ok, "results": results})


@app.route("/api/jobs/<job_id>/run", methods=["POST"])
def api_run_job(job_id: str):
    ok, msg = start_job(job_id)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_delete_job(job_id: str):
    if not delete_job(job_id):
        return jsonify({"ok": False, "error": t("err.cannot_delete", get_lang())}), 400
    return jsonify({"ok": True})


@app.route("/api/log")
def api_log():
    return jsonify({"ok": True, "text": read_log_tail()})



@app.route("/api/privacy/status")
def api_privacy_status():
    return jsonify({"ok": True, **compliance_context(DATA_DIR)})


@app.route("/api/privacy/consent", methods=["POST"])
def api_privacy_consent():
    row = save_privacy_consent(DATA_DIR)
    return jsonify({"ok": True, "consent": row})

if __name__ == "__main__":
    append_log("Backup Verifier Web-UI started")
    sync_appcenter_icon("com.runlevel.backupverifier")
    start_scheduler()
    app.run(host="0.0.0.0", port=8080, threaded=True)
