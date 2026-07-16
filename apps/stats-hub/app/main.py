# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import os
import threading

from compliance import (
    compliance_context,
    consent_required_response,
    has_privacy_consent,
    save_privacy_consent,
)
from flask import Flask, g, jsonify, make_response, render_template, request

from collect import probe_disk_temps, scan_top_folders
from icon_sync import sync_appcenter_icon
from i18n import LANG_COOKIE, bundle, get_lang, lang_from_request, normalize_lang, t
from monitor import set_top_folders, snapshot, start_monitor, touch_client_activity
from settings import INTERVAL_CHOICES, load_settings, save_settings, settings_for_api
from ugos_poll import reset_ugos_client, test_ugos_connection
from store import DATA_DIR, append_log, read_log_tail

app = Flask(__name__)
APP_VERSION = os.environ.get("STATS_HUB_VERSION", "0.2.32")
NAS_ADMIN_URL = os.environ.get(
    "NAS_ADMIN_URL",
    "https://github.com/runlevel1977-del/UgreenNASAdmin/releases/latest",
)
_top_lock = threading.Lock()
_top_busy = False


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


@app.route("/health")
def health():
    return jsonify({"ok": True, "version": APP_VERSION})


@app.route("/")
def index():
    touch_client_activity()
    resp = make_response(render_template("index.html", version=APP_VERSION))
    picked = normalize_lang(request.args.get("lang"))
    if picked:
        _lang_cookie_response(resp, picked)
    return resp


@app.route("/api/lang", methods=["POST"])
def api_lang():
    body = request.get_json(force=True, silent=True) or {}
    picked = normalize_lang(body.get("lang"))
    if not picked:
        return jsonify({"ok": False}), 400
    resp = jsonify({"ok": True, "lang": picked, "i18n": bundle(picked)})
    return _lang_cookie_response(resp, picked)


@app.route("/api/snapshot")
def api_snapshot():
    touch_client_activity()
    snap = copy.deepcopy(snapshot())
    return jsonify({"ok": True, "snapshot": snap, "version": APP_VERSION})


@app.route("/api/top/scan", methods=["POST"])
def api_top_scan():
    global _top_busy
    with _top_lock:
        if _top_busy:
            return jsonify({"ok": False, "error": "busy"}), 409
        _top_busy = True
    set_top_folders([], scanning=True)

    def worker():
        global _top_busy
        try:
            append_log("TOP scan start (volume1+2, depth 2)")
            rows = scan_top_folders()
            set_top_folders(rows, scanning=False)
            append_log(f"TOP scan done: {len(rows)} rows")
        except Exception as ex:
            append_log(f"TOP scan error: {ex}")
            set_top_folders([], scanning=False)
        finally:
            with _top_lock:
                _top_busy = False

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/log")
def api_log():
    return jsonify({"ok": True, "log": read_log_tail()})


@app.route("/api/settings")
def api_settings_get():
    return jsonify({
        "ok": True,
        "settings": settings_for_api(),
        "interval_choices": list(INTERVAL_CHOICES),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    body = request.get_json(force=True, silent=True) or {}
    if not body:
        return jsonify({"ok": False, "error": "empty"}), 400
    try:
        saved = save_settings(body)
    except (TypeError, ValueError) as ex:
        return jsonify({"ok": False, "error": str(ex)}), 400
    if "ugos_api" in body:
        reset_ugos_client()
    return jsonify({"ok": True, "settings": saved})


@app.route("/api/ugos/test", methods=["POST"])
def api_ugos_test():
    """Test UGOS API login with posted or saved credentials (any port)."""
    body = request.get_json(force=True, silent=True) or {}
    cur = load_settings().get("ugos_api") or {}
    patch = body.get("ugos_api") if isinstance(body.get("ugos_api"), dict) else body
    cfg = dict(cur)
    if isinstance(patch, dict):
        for key in ("host", "port", "username", "use_https", "verify_ssl", "enabled"):
            if key in patch:
                cfg[key] = patch[key]
        if str(patch.get("password") or "").strip():
            cfg["password"] = str(patch["password"])
    ok, err = test_ugos_connection(cfg)
    if ok:
        reset_ugos_client()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": err or "unknown"})


@app.route("/api/disk-probe")
def api_disk_probe():
    """SATA/NVMe diagnostic — open in browser if SSH/docker is awkward."""
    return jsonify({"ok": True, "version": APP_VERSION, **probe_disk_temps()})


def _boot_top_scan() -> None:
    import time
    time.sleep(45)
    global _top_busy
    with _top_lock:
        if _top_busy:
            return
        _top_busy = True
    set_top_folders([], scanning=True)
    try:
        rows = scan_top_folders()
        set_top_folders(rows, scanning=False)
        append_log(f"TOP boot scan: {len(rows)} rows")
    except Exception as ex:
        append_log(f"TOP boot scan error: {ex}")
        set_top_folders([], scanning=False)
    finally:
        with _top_lock:
            _top_busy = False



@app.route("/api/privacy/status")
def api_privacy_status():
    return jsonify({"ok": True, **compliance_context(DATA_DIR)})


@app.route("/api/privacy/consent", methods=["POST"])
def api_privacy_consent():
    row = save_privacy_consent(DATA_DIR)
    return jsonify({"ok": True, "consent": row})

if __name__ == "__main__":
    port = int(os.environ.get("STATS_HUB_PORT", "29125"))
    append_log(f"Stats Hub {APP_VERSION} starting on :{port}")
    start_monitor()
    threading.Thread(
        target=lambda: sync_appcenter_icon("com.runlevel.statshub"),
        daemon=True,
        name="sh-icon",
    ).start()
    threading.Thread(target=_boot_top_scan, daemon=True).start()
    app.run(host="0.0.0.0", port=port, threaded=True)
