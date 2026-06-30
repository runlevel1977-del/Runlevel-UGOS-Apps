# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading

from compliance import (
    compliance_context,
    consent_required_response,
    has_privacy_consent,
    save_privacy_consent,
)
from flask import Flask, g, jsonify, make_response, render_template, request

from devices import (
    LOCAL_ID,
    _list_smb_dirs_live,
    _list_smb_shares_live,
    add_smb_device,
    browse,
    delete_device,
    device_public_row,
    endpoint_label,
    get_device,
    load_devices,
    refresh_device_folder_cache,
    test_smb,
    update_smb_device,
)
from smb_cache import cache_summary, get_build_status, start_smb_cache_build
from i18n import LANG_COOKIE, bundle, get_lang, lang_from_request, normalize_lang, t
from icon_sync import sync_appcenter_icon
from notify import public_settings, save_notify_settings, send_test_notifications
from plans import delete_plan, list_active_plans, normalize_schedule_fields, schedule_label, start_plan
from scheduler import start_scheduler
from store import DATA_DIR, append_log, get_plan, load_plans, new_plan_id, read_log_tail, save_plans
from volumes import list_volumes, normalize_volume_id
from wol import broadcast_for_ip, send_wol, wol_broadcast, wol_source_ips

app = Flask(__name__)
APP_VERSION = os.environ.get("WAKE_SYNC_VERSION", "0.1.26")
APP_PORT = int(os.environ.get("WAKE_SYNC_PORT", "29120"))
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

    return {"lang": lng, "t": _t, "i18n": bundle(lng), "nas_admin_url": NAS_ADMIN_URL}


def _normalize_endpoint(ep: dict) -> dict:
    device_id = (ep.get("device_id") or LOCAL_ID).strip() or LOCAL_ID
    dev = get_device(device_id)
    out = {"device_id": device_id, "path": (ep.get("path") or "").strip().strip("/")}
    if dev and dev.get("type") == "smb":
        out["share"] = (ep.get("share") or "").strip()
    else:
        out["volume"] = normalize_volume_id(ep.get("volume"))
    return out


def _wol_target_from_dest(dest: dict, mac: str, ip: str) -> tuple[str, str]:
    device_id = (dest.get("device_id") or "").strip()
    if not device_id or device_id == LOCAL_ID:
        return mac, ip
    dev = get_device(device_id)
    if not dev or dev.get("type") != "smb":
        return mac, ip
    if not ip:
        ip = (dev.get("host") or "").strip()
    if not mac:
        mac = (dev.get("mac") or "").strip()
    return mac, ip


def _plan_fields_from_body(body: dict, lng: str, existing: dict | None = None) -> tuple[str | None, dict]:
    name = (body.get("name") or "").strip() or (existing or {}).get("name") or "Plan"
    source = body.get("source")
    dest = body.get("dest")
    if not isinstance(source, dict) or not isinstance(dest, dict):
        return t("err.pick_both", lng), {}
    source = _normalize_endpoint(source)
    dest = _normalize_endpoint(dest)
    mac = (body.get("target_mac") or "").strip()
    ip = (body.get("target_ip") or "").strip()
    mac, ip = _wol_target_from_dest(dest, mac, ip)
    if not ip:
        return t("err.ip_missing", lng), {}
    if not mac:
        return t("err.mac_on_device", lng), {}
    dest_dev = get_device(dest.get("device_id", ""))
    if dest_dev and dest_dev.get("type") == "smb" and not dest.get("share"):
        return t("err.smb_share_missing", lng), {}
    wake_bc = (body.get("wake_broadcast") or "").strip() or broadcast_for_ip(ip) or ""
    sched = normalize_schedule_fields(body, existing=existing)
    enabled_default = existing.get("enabled", True) if existing else True
    return None, {
        "name": name,
        "enabled": bool(body.get("enabled", enabled_default)),
        "run_at": (body.get("run_at") or (existing or {}).get("run_at") or "12:30").strip(),
        "schedule_type": sched["schedule_type"],
        "weekday": sched["weekday"],
        "monthly_week": sched["monthly_week"],
        "schedule_anchor": sched["schedule_anchor"],
        "target_mac": mac,
        "target_ip": ip,
        "wake_broadcast": wake_bc,
        "ready_wait_minutes": max(1, min(120, int(body.get("ready_wait_minutes") or (existing or {}).get("ready_wait_minutes") or 20))),
        "ready_port": int(body.get("ready_port") or (existing or {}).get("ready_port") or 445),
        "source": source,
        "dest": dest,
    }


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
    env_bc = wol_broadcast()
    hint = ""
    if env_bc:
        hint = broadcast_for_ip(env_bc) or env_bc
    return jsonify({
        "ok": True,
        "wol_broadcast": env_bc,
        "wol_broadcast_hint": hint,
        "wol_source_ips": wol_source_ips(),
        "volumes": list_volumes(),
    })


@app.route("/api/wol/test", methods=["POST"])
def api_test_wol():
    body = request.get_json(force=True, silent=True) or {}
    mac = (body.get("mac") or "").strip()
    ip = (body.get("target_ip") or body.get("ip") or "").strip()
    if not mac:
        dev = get_device((body.get("device_id") or "").strip())
        if dev:
            mac = (dev.get("mac") or "").strip()
            ip = ip or (dev.get("host") or "").strip()
    if not mac:
        return jsonify({"ok": False, "error": t("err.mac_on_device", get_lang())}), 400
    ok, msg = send_wol(mac, target_ip=ip or None)
    append_log(f"WOL test: {msg}")
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/devices", methods=["GET"])
def api_devices():
    devices = load_devices()
    out = []
    for d in devices:
        row = device_public_row(d.copy())
        if d.get("id") == LOCAL_ID:
            row["name"] = t("device.this_nas", get_lang())
        out.append(row)
    return jsonify(out)


@app.route("/api/devices", methods=["POST"])
def api_add_device():

    if not has_privacy_consent(DATA_DIR):
        body, code = consent_required_response()
        return jsonify(body), code
    body = request.get_json(force=True, silent=True) or {}
    lng = get_lang()
    host = (body.get("host") or "").strip()
    name = (body.get("name") or host).strip()
    user = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not host:
        return jsonify({"ok": False, "error": "host missing"}), 400
    ok, msg = test_smb(host, user, password)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    mac = (body.get("mac") or "").strip()
    dev = add_smb_device(name, host, user, password, mac=mac)
    start_smb_cache_build(dev, _list_smb_shares_live, _list_smb_dirs_live)
    append_log(f"Target saved: {name} ({host}) — folder scan started")
    row = device_public_row(dev)
    row["folder_cache"] = cache_summary(dev["id"])
    return jsonify({"ok": True, "device": row, "cache_building": True})


@app.route("/api/devices/<device_id>", methods=["PATCH"])
def api_patch_device(device_id: str):
    body = request.get_json(force=True, silent=True) or {}
    fields = {}
    if "name" in body:
        fields["name"] = body.get("name")
    if "mac" in body:
        fields["mac"] = body.get("mac")
    dev = update_smb_device(device_id, **fields)
    if not dev:
        return jsonify({"ok": False, "error": "device not found"}), 404
    return jsonify({"ok": True, "device": {**dev, "password": "***", "folder_cache": cache_summary(device_id)}})


@app.route("/api/devices/<device_id>/cache-status", methods=["GET"])
def api_device_cache_status(device_id: str):
    dev = get_device(device_id)
    if not dev or dev.get("type") != "smb":
        return jsonify({"ok": False, "error": "device not found"}), 404
    st = get_build_status(device_id)
    summary = cache_summary(device_id)
    return jsonify({"ok": True, **summary, **st})


@app.route("/api/devices/<device_id>/refresh-cache", methods=["POST"])
def api_refresh_device_cache(device_id: str):
    lng = get_lang()
    ok, msg = refresh_device_folder_cache(device_id)
    if not ok:
        if msg == "already building":
            return jsonify({"ok": True, "cache_building": True, "message": t("devices.cache_building", lng)})
        return jsonify({"ok": False, "error": t("err.device_not_found", lng)}), 404
    return jsonify({"ok": True, "cache_building": True})


@app.route("/api/devices/<device_id>", methods=["DELETE"])
def api_del_device(device_id: str):
    if not delete_device(device_id):
        return jsonify({"ok": False}), 400
    return jsonify({"ok": True})


@app.route("/api/browse")
def api_browse():
    return jsonify(
        browse(
            request.args.get("device_id", LOCAL_ID),
            request.args.get("path", ""),
            request.args.get("share", ""),
            request.args.get("volume", ""),
        )
    )


@app.route("/api/plans", methods=["GET"])
def api_list_plans():
    active = set(list_active_plans())
    out = []
    for p in load_plans():
        row = p.copy()
        row["source_label"] = endpoint_label(row.get("source") or {})
        row["dest_label"] = endpoint_label(row.get("dest") or {})
        row["schedule_label"] = schedule_label(row, get_lang())
        row["running"] = row.get("id") in active
        out.append(row)
    return jsonify(out)


@app.route("/api/plans", methods=["POST"])
def api_create_plan():
    body = request.get_json(force=True, silent=True) or {}
    lng = get_lang()
    err, fields = _plan_fields_from_body(body, lng)
    if err:
        return jsonify({"ok": False, "error": err}), 400

    plan = {
        "id": new_plan_id(),
        **fields,
        "last_run": None,
        "last_run_date": None,
        "last_status": None,
        "last_message": "",
        "last_details": {},
    }
    plans = load_plans()
    plans.append(plan)
    save_plans(plans)
    append_log(f"PLAN saved: {plan['name']}")
    return jsonify({"ok": True, "plan": plan})


@app.route("/api/plans/<plan_id>", methods=["PATCH"])
def api_update_plan(plan_id: str):
    lng = get_lang()
    if plan_id in set(list_active_plans()):
        return jsonify({"ok": False, "error": t("err.plan_running", lng)}), 400
    existing = get_plan(plan_id)
    if not existing:
        return jsonify({"ok": False, "error": t("err.plan_not_found", lng)}), 404
    body = request.get_json(force=True, silent=True) or {}
    err, fields = _plan_fields_from_body(body, lng, existing=existing)
    if err:
        return jsonify({"ok": False, "error": err}), 400

    updated = {**existing, **fields}
    plans = load_plans()
    for i, p in enumerate(plans):
        if p.get("id") == plan_id:
            plans[i] = updated
            break
    save_plans(plans)
    append_log(f"PLAN updated: {updated.get('name', plan_id)}")
    return jsonify({"ok": True, "plan": updated})


@app.route("/api/plans/<plan_id>/run", methods=["POST"])
def api_run_plan(plan_id: str):
    ok, msg = start_plan(plan_id, manual=True)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@app.route("/api/plans/<plan_id>", methods=["DELETE"])
def api_delete_plan(plan_id: str):
    if not delete_plan(plan_id):
        return jsonify({"ok": False, "error": t("err.plan_running", get_lang())}), 400
    return jsonify({"ok": True})


@app.route("/api/notifications", methods=["GET"])
def api_get_notifications():
    return jsonify({"ok": True, "settings": public_settings()})


@app.route("/api/notifications", methods=["POST"])
def api_save_notifications():

    if not has_privacy_consent(DATA_DIR):
        body, code = consent_required_response()
        return jsonify(body), code
    body = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": True, "settings": save_notify_settings(body)})


@app.route("/api/notifications/test", methods=["POST"])
def api_test_notifications():
    results = send_test_notifications(get_lang())
    return jsonify({"ok": any(r.get("ok") for r in results), "results": results})


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
    append_log(f"Wake & Sync Web-UI starting on port {APP_PORT}")

    def _background_boot() -> None:
        try:
            sync_appcenter_icon("com.runlevel.wakesync")
        except Exception as ex:
            append_log(f"ICON sync error: {ex}")
        try:
            start_scheduler()
        except Exception as ex:
            append_log(f"Scheduler error: {ex}")

    threading.Thread(target=_background_boot, daemon=True, name="ws-boot").start()
    app.run(host="0.0.0.0", port=APP_PORT, threaded=True)
