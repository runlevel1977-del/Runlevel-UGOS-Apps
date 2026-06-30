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

from i18n import LANG_COOKIE, bundle, get_lang, lang_from_request, normalize_lang, t
from icon_sync import sync_appcenter_icon
from monitor import get_monitor
from store import DATA_DIR, append_log, read_log_tail

app = Flask(__name__)
APP_VERSION = os.environ.get("SECURITY_HUB_VERSION", "0.1.11")
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
    mon = get_monitor()
    snap = mon.snapshot()
    return jsonify({
        "ok": True,
        "lang": get_lang(),
        "version": APP_VERSION,
        "live_enabled": snap["live_enabled"],
        "hide_pings": snap["hide_pings"],
        "days": snap["days"],
        "sort_by": snap["sort_by"],
        "sort_desc": snap["sort_desc"],
    })


@app.route("/api/events")
def api_events():
    return jsonify({"ok": True, **get_monitor().snapshot()})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    mon = get_monitor()
    lng = get_lang()
    if mon.is_busy():
        return jsonify({"ok": False, "error": t("status.busy", lng), **mon.snapshot()}), 409
    ok = mon.refresh(start_watch_after=True)
    snap = mon.snapshot()
    if not ok:
        err = snap.get("error") or t("status.collect_empty", lng)
        return jsonify({"ok": False, "error": err, **snap}), 500
    return jsonify({"ok": True, **snap})


@app.route("/api/prefs", methods=["POST"])
def api_prefs():
    body = request.get_json(force=True, silent=True) or {}
    mon = get_monitor()
    if "live_enabled" in body:
        mon.set_live(bool(body["live_enabled"]))
    if "hide_pings" in body:
        mon.set_hide_pings(bool(body["hide_pings"]))
    if "days" in body:
        mon.set_days(int(body["days"]))
    if "sort_by" in body or "sort_desc" in body:
        snap = mon.snapshot()
        mon.set_sort(
            str(body.get("sort_by", snap["sort_by"])),
            bool(body.get("sort_desc", snap["sort_desc"])),
        )
    return jsonify({"ok": True, **mon.snapshot()})


@app.route("/api/log")
def api_log():
    return jsonify({"ok": True, "text": read_log_tail()})


def _start_monitor():
    get_monitor().start()



@app.route("/api/privacy/status")
def api_privacy_status():
    return jsonify({"ok": True, **compliance_context(DATA_DIR)})


@app.route("/api/privacy/consent", methods=["POST"])
def api_privacy_consent():
    row = save_privacy_consent(DATA_DIR)
    return jsonify({"ok": True, "consent": row})

if __name__ == "__main__":
    append_log("Security Hub Web-UI started")
    sync_appcenter_icon("com.runlevel.securityhub")
    threading.Thread(target=_start_monitor, name="monitor-boot", daemon=True).start()
    app.run(host="0.0.0.0", port=8080, threaded=True)
