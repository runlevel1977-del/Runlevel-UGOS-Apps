# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import os
from io import BytesIO
from pathlib import Path
from compliance import (
    compliance_context,
    consent_required_response,
    has_privacy_consent,
    save_privacy_consent,
)
from flask import Flask, g, jsonify, make_response, render_template, request, send_file

from i18n import LANG_COOKIE, bundle, lang_from_request, normalize_lang, t
from icon_sync import sync_appcenter_icon
from store import DATA_DIR, append_log, get_job, load_vaults, read_log_tail
from usb_bind import usb_rows_enriched
from vaults import (
    browse_dirs,
    create_relock_job,
    create_seal_job,
    create_unlock_job,
    list_public_vaults,
    public_vault_row,
    remove_vault_record,
    sync_orphan_vaults,
    write_key_to_usb,
)
from volumes import list_volumes

app = Flask(__name__)
APP_VERSION = os.environ.get("LOCK_KEY_VERSION", "0.1.25")
APP_PORT = int(os.environ.get("LOCK_KEY_PORT", "8080"))
NAS_ADMIN_URL = os.environ.get(
    "NAS_ADMIN_URL",
    "https://github.com/runlevel1977-del/UgreenNASAdmin/releases/latest",
)
_pending_keys: dict[str, bytes] = {}


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


@app.route("/api/volumes")
def api_volumes():
    return jsonify({"ok": True, "volumes": list_volumes()})


@app.route("/api/browse")
def api_browse():
    volume = (request.args.get("volume") or "1").strip()
    path = (request.args.get("path") or "").strip()
    try:
        data = browse_dirs(volume, path)
        return jsonify({"ok": True, **data})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/usb")
def api_usb():
    from volumes import usb_volume_id as vol_usb_id

    rows = []
    for row in usb_rows_enriched():
        mp = row.get("mount") or ""
        rows.append({**row, "volume_id": vol_usb_id(Path(mp)) if mp else ""})
    return jsonify({"ok": True, "devices": rows})


@app.route("/api/vaults")
def api_vaults():
    return jsonify({"ok": True, "vaults": list_public_vaults()})


@app.route("/api/vaults/rescan", methods=["POST"])
def api_vaults_rescan():
    try:
        recovered = sync_orphan_vaults()
        vaults = [public_vault_row(v) for v in load_vaults()]
        return jsonify({"ok": True, "recovered": recovered, "vaults": vaults})
    except Exception as exc:
        append_log(f"rescan failed: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/vaults/seal", methods=["POST"])
def api_seal():
    body = request.get_json(force=True, silent=True) or {}
    try:
        job_id, vault, key_bytes = create_seal_job(
            name=(body.get("name") or "").strip(),
            volume_id=(body.get("volume") or "1").strip(),
            subpath=(body.get("path") or "").strip(),
            bind_usb=bool(body.get("bind_usb")),
            usb_volume_id=(body.get("usb_volume") or "").strip(),
            key_passphrase=(body.get("key_passphrase") or "").strip(),
        )
        _pending_keys[vault["id"]] = key_bytes
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "vault": vault,
                "download_url": f"/api/vaults/{vault['id']}/keyfile",
            }
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/vaults/<vault_id>/keyfile")
def api_keyfile(vault_id: str):
    data = _pending_keys.get(vault_id)
    if not data:
        return jsonify({"ok": False, "error": "key not available"}), 404
    bio = BytesIO(data)
    bio.seek(0)
    return send_file(
        bio,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"lockkey_{vault_id}.lk",
    )


@app.route("/api/vaults/<vault_id>/keyfile/usb", methods=["POST"])
def api_keyfile_usb(vault_id: str):
    body = request.get_json(force=True, silent=True) or {}
    data = _pending_keys.get(vault_id)
    if not data:
        return jsonify({"ok": False, "error": "key not available"}), 404
    try:
        path = write_key_to_usb((body.get("usb_volume") or "").strip(), vault_id, data)
        return jsonify({"ok": True, "path": path})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/vaults/<vault_id>/unlock", methods=["POST"])
def api_unlock(vault_id: str):
    body = request.get_json(force=True, silent=True) or {}
    key_bytes = None
    if body.get("key_b64"):
        try:
            key_bytes = base64.b64decode(body.get("key_b64") or "")
        except Exception:
            return jsonify({"ok": False, "error": "invalid key_b64"}), 400
    key_passphrase = (body.get("key_passphrase") or "").strip()
    try:
        job_id = create_unlock_job(
            vault_id,
            key_bytes=key_bytes,
            usb_volume_id=(body.get("usb_volume") or "").strip(),
            key_passphrase=key_passphrase,
        )
        return jsonify({"ok": True, "job_id": job_id})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/vaults/<vault_id>/relock", methods=["POST"])
def api_relock(vault_id: str):
    body = request.get_json(force=True, silent=True) or {}
    key_bytes = None
    if body.get("key_b64"):
        try:
            key_bytes = base64.b64decode(body.get("key_b64") or "")
        except Exception:
            return jsonify({"ok": False, "error": "invalid key_b64"}), 400
    key_passphrase = (body.get("key_passphrase") or "").strip()
    try:
        job_id = create_relock_job(
            vault_id,
            key_bytes=key_bytes,
            usb_volume_id=(body.get("usb_volume") or "").strip(),
            key_passphrase=key_passphrase,
        )
        return jsonify({"ok": True, "job_id": job_id})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/vaults/<vault_id>", methods=["DELETE"])
def api_delete_vault(vault_id: str):
    body = request.get_json(force=True, silent=True) or {}
    force = bool(body.get("force"))
    try:
        ok = remove_vault_record(vault_id, force=force)
        return jsonify({"ok": ok})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/jobs/<job_id>")
def api_job(job_id: str):
    job = get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "job": job})


@app.route("/api/log")
def api_log():
    return jsonify({"ok": True, "log": read_log_tail()})



@app.route("/api/privacy/status")
def api_privacy_status():
    return jsonify({"ok": True, **compliance_context(DATA_DIR)})


@app.route("/api/privacy/consent", methods=["POST"])
def api_privacy_consent():
    row = save_privacy_consent(DATA_DIR)
    return jsonify({"ok": True, "consent": row})

if __name__ == "__main__":
    sync_appcenter_icon("com.runlevel.lockandkey")
    append_log(f"Lock & Key {APP_VERSION} starting on :{APP_PORT}")
    try:
        recovered = sync_orphan_vaults()
        if recovered:
            append_log(f"startup: recovered {recovered} vault(s)")
    except Exception as exc:
        append_log(f"startup sync failed: {exc}")
    app.run(host="0.0.0.0", port=APP_PORT, threaded=True)
