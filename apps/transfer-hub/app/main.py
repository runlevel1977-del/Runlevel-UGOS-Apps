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
from jobs import list_active_jobs, start_profile_run, start_scheduler
from icon_sync import sync_appcenter_icon
from i18n import LANG_COOKIE, bundle, get_lang, lang_from_request, normalize_lang, t
from network_scan import probe_host, scan_config, scan_lan
from schedule_util import normalize_schedule_fields, schedule_label
from volumes import list_volumes
from store import (
    DATA_DIR,
    append_log,
    find_reverse_conflict,
    load_profiles,
    new_profile_id,
    read_log_tail,
    save_profiles,
)

app = Flask(__name__)
NAS_MOUNT = os.environ.get("NAS_MOUNT", "/mnt/nas")
APP_VERSION = os.environ.get("TRANSFER_HUB_VERSION", "0.6.21")
NAS_ADMIN_URL = os.environ.get(
    "NAS_ADMIN_URL",
    "https://github.com/runlevel1977-del/UgreenNASAdmin/releases/latest",
)


@app.before_request
def _set_lang():
    g.lang = lang_from_request(request)


def _lang_cookie_response(resp, lang: str):
    resp.set_cookie(
        LANG_COOKIE,
        lang,
        max_age=365 * 24 * 3600,
        path="/",
        samesite="Lax",
        httponly=False,
    )
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


def _parse_profile_body(
    body: dict,
    profiles: list,
    *,
    exclude_id: str | None = None,
) -> tuple[dict | None, tuple[str, int] | None]:
    """Validate profile JSON; return (fields, None) or (None, (error, status))."""
    lng = get_lang()
    name = (body.get("name") or "").strip() or t("profile.default_name", lng)
    source = body.get("source")
    dest = body.get("dest")
    auto_sync = bool(body.get("auto_sync"))
    delete_source_after = bool(body.get("delete_source_after"))
    if delete_source_after and auto_sync:
        return None, (t("err.move_with_auto", lng), 400)
    if delete_source_after:
        auto_sync = False
    sched = normalize_schedule_fields(body)

    if not isinstance(source, dict) or not isinstance(dest, dict):
        return None, (t("err.pick_via_ui", lng), 400)
    if not source.get("device_id") or not dest.get("device_id"):
        return None, (t("err.pick_devices", lng), 400)

    sk = (
        f"{source.get('device_id')}|{source.get('volume') or ''}|"
        f"{source.get('share')}|{source.get('path')}"
    )
    dk = (
        f"{dest.get('device_id')}|{dest.get('volume') or ''}|"
        f"{dest.get('share')}|{dest.get('path')}"
    )
    if sk == dk:
        return None, (t("err.same_endpoints", lng), 400)

    conflict = find_reverse_conflict(profiles, source, dest, exclude_id=exclude_id)
    if conflict and auto_sync:
        return None, (
            t("err.conflict_auto", lng, name=conflict.get("name", "")),
            400,
        )

    return {
        "name": name,
        "source": source,
        "dest": dest,
        "auto_sync": auto_sync,
        "delete_source_after": delete_source_after,
        **sched,
    }, None


@app.route("/health")
def health():
    return jsonify({"ok": True, "version": APP_VERSION, "lang": get_lang()})


@app.route("/")
def index():
    html = render_template(
        "index.html",
        nas_mount=NAS_MOUNT,
        version=APP_VERSION,
    )
    resp = make_response(html)
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


@app.route("/api/devices", methods=["GET"])
def api_devices():
    devices = load_devices()
    for d in devices:
        if d.get("id") == LOCAL_ID:
            d["name"] = t("device.this_nas", get_lang())
    return jsonify(devices)


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "ok": True,
        "lang": get_lang(),
        **scan_config(),
        "volumes": list_volumes(),
    })


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
    append_log(f"Gerät gespeichert: {name} ({host})")
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


@app.route("/api/profiles", methods=["GET"])
def api_list_profiles():
    out = []
    for p in load_profiles():
        q = p.copy()
        if isinstance(q.get("source"), dict):
            q["source_label"] = endpoint_label(q["source"])
        if isinstance(q.get("dest"), dict):
            q["dest_label"] = endpoint_label(q["dest"])
        lng = get_lang()
        q["schedule_label"] = schedule_label(q, lng, t)
        out.append(q)
    return jsonify(out)


@app.route("/api/profiles/<profile_id>", methods=["GET"])
def api_get_profile(profile_id: str):
    profile = next((p for p in load_profiles() if p.get("id") == profile_id), None)
    if not profile:
        return jsonify({"ok": False, "error": t("err.profile_not_found", get_lang())}), 404
    q = profile.copy()
    if isinstance(q.get("source"), dict):
        q["source_label"] = endpoint_label(q["source"])
    if isinstance(q.get("dest"), dict):
        q["dest_label"] = endpoint_label(q["dest"])
    return jsonify({"ok": True, "profile": q, "lang": get_lang()})


@app.route("/api/profiles", methods=["POST"])
def api_create_profile():
    body = request.get_json(force=True, silent=True) or {}
    profiles = load_profiles()
    fields, err = _parse_profile_body(body, profiles)
    if err:
        return jsonify({"ok": False, "error": err[0]}), err[1]

    profile = {
        "id": new_profile_id(),
        **fields,
        "last_run": None,
        "last_status": None,
        "last_message": "",
    }
    profiles.append(profile)
    save_profiles(profiles)
    append_log(
        f"Profil: {fields['name']} | "
        f"{endpoint_label(fields['source'])} -> {endpoint_label(fields['dest'])}"
    )
    return jsonify({"ok": True, "profile": profile})


@app.route("/api/profiles/<profile_id>", methods=["PUT"])
def api_update_profile(profile_id: str):
    body = request.get_json(force=True, silent=True) or {}
    profiles = load_profiles()
    idx = next((i for i, p in enumerate(profiles) if p.get("id") == profile_id), None)
    if idx is None:
        return jsonify({"ok": False, "error": t("err.profile_not_found", get_lang())}), 404

    fields, err = _parse_profile_body(body, profiles, exclude_id=profile_id)
    if err:
        return jsonify({"ok": False, "error": err[0]}), err[1]

    existing = profiles[idx]
    profiles[idx] = {
        **existing,
        **fields,
    }
    save_profiles(profiles)
    append_log(
        f"Profil geändert: {fields['name']} | "
        f"{endpoint_label(fields['source'])} -> {endpoint_label(fields['dest'])}"
    )
    return jsonify({"ok": True, "profile": profiles[idx]})


@app.route("/api/profiles/<profile_id>", methods=["DELETE"])
def api_delete_profile(profile_id: str):
    profiles = load_profiles()
    filtered = [p for p in profiles if p.get("id") != profile_id]
    if len(filtered) == len(profiles):
        return jsonify({"ok": False, "error": t("err.profile_not_found", get_lang())}), 404
    save_profiles(filtered)
    return jsonify({"ok": True})


@app.route("/api/profiles/<profile_id>/run", methods=["POST"])
def api_run_profile(profile_id: str):
    ok, msg = start_profile_run(profile_id)
    return jsonify({"ok": ok, "message": msg, "started": ok})


@app.route("/api/jobs/active", methods=["GET"])
def api_active_jobs():
    return jsonify({"ok": True, "jobs": list_active_jobs()})


@app.route("/api/logs", methods=["GET"])
def api_logs():
    return jsonify({"log": read_log_tail()})



@app.route("/api/privacy/status")
def api_privacy_status():
    return jsonify({"ok": True, **compliance_context(DATA_DIR)})


@app.route("/api/privacy/consent", methods=["POST"])
def api_privacy_consent():
    row = save_privacy_consent(DATA_DIR)
    return jsonify({"ok": True, "consent": row})

if __name__ == "__main__":
    append_log("Transfer Hub Web-UI gestartet")
    sync_appcenter_icon("com.runlevel.transferhub")
    start_scheduler()
    app.run(host="0.0.0.0", port=8080, threaded=True)
