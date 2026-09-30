# -*- coding: utf-8 -*-
from __future__ import annotations

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
from ugos_auth import init_ugos_auth
from transport_rsa import decrypt_chunked, decrypt_oaep

from i18n import LANG_COOKIE, LANG_LABELS, bundle, lang_from_request, normalize_lang, t
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
init_ugos_auth(app)
APP_VERSION = os.environ.get("LOCK_KEY_VERSION", "0.1.32")
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


def _api_error(exc: Exception, code: int = 400):
    from i18n import I18nError

    if isinstance(exc, I18nError):
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
                "error_key": exc.key,
                "error_params": exc.params,
            }
        ), code
    return jsonify({"ok": False, "error": str(exc)}), code


def _decrypt_secret_field(obj: dict, name: str) -> str:
    if str(obj.get(name) or "").strip():
        raise ValueError("plaintext passwords are not accepted")
    enc = str(obj.get(f"{name}_enc") or "").strip()
    if not enc:
        return ""
    try:
        return decrypt_oaep(DATA_DIR, enc)
    except Exception as exc:
        raise ValueError("encrypted password required") from exc


def _decrypt_key_file_field(obj: dict) -> bytes | None:
    if str(obj.get("key_b64") or "").strip():
        raise ValueError("plaintext key files are not accepted")
    enc = str(obj.get("key_b64_enc") or "").strip()
    if not enc:
        return None
    try:
        return decrypt_chunked(DATA_DIR, enc)
    except Exception as exc:
        raise ValueError("encrypted key file required") from exc


@app.context_processor
def _inject_i18n():
    lng = getattr(g, "lang", "en")

    def _t(key: str, **fmt):
        return t(key, lng, **fmt)

    return {
        "lang": lng,
        "t": _t,
        "i18n": bundle(lng),
        "lang_labels": LANG_LABELS,
        "nas_admin_url": NAS_ADMIN_URL,
        **compliance_context(DATA_DIR),
    }


@app.route("/health")
def health():
    return jsonify({"ok": True})


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
        return _api_error(exc)


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
        key_passphrase = _decrypt_secret_field(body, "key_passphrase")
        job_id, vault, key_bytes = create_seal_job(
            name=(body.get("name") or "").strip(),
            volume_id=(body.get("volume") or "1").strip(),
            subpath=(body.get("path") or "").strip(),
            bind_usb=bool(body.get("bind_usb")),
            usb_volume_id=(body.get("usb_volume") or "").strip(),
            key_passphrase=key_passphrase,
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
        err = str(exc)
        if "plaintext" in err.lower() or "encrypted" in err.lower() or "ciphertext" in err.lower():
            return jsonify({"ok": False, "error": "Encrypted secrets required"}), 400
        return _api_error(exc)


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
        return _api_error(exc)


@app.route("/api/vaults/<vault_id>/unlock", methods=["POST"])
def api_unlock(vault_id: str):
    body = request.get_json(force=True, silent=True) or {}
    try:
        key_bytes = _decrypt_key_file_field(body)
        key_passphrase = _decrypt_secret_field(body, "key_passphrase")
        job_id = create_unlock_job(
            vault_id,
            key_bytes=key_bytes,
            usb_volume_id=(body.get("usb_volume") or "").strip(),
            key_passphrase=key_passphrase,
        )
        return jsonify({"ok": True, "job_id": job_id})
    except ValueError as exc:
        err = str(exc)
        if "plaintext" in err.lower() or "encrypted" in err.lower() or "ciphertext" in err.lower():
            return jsonify({"ok": False, "error": "Encrypted secrets required"}), 400
        return _api_error(exc)


@app.route("/api/vaults/<vault_id>/relock", methods=["POST"])
def api_relock(vault_id: str):
    body = request.get_json(force=True, silent=True) or {}
    try:
        key_bytes = _decrypt_key_file_field(body)
        key_passphrase = _decrypt_secret_field(body, "key_passphrase")
        job_id = create_relock_job(
            vault_id,
            key_bytes=key_bytes,
            usb_volume_id=(body.get("usb_volume") or "").strip(),
            key_passphrase=key_passphrase,
        )
        return jsonify({"ok": True, "job_id": job_id})
    except ValueError as exc:
        err = str(exc)
        if "plaintext" in err.lower() or "encrypted" in err.lower() or "ciphertext" in err.lower():
            return jsonify({"ok": False, "error": "Encrypted secrets required"}), 400
        return _api_error(exc)


@app.route("/api/vaults/<vault_id>", methods=["DELETE"])
def api_delete_vault(vault_id: str):
    body = request.get_json(force=True, silent=True) or {}
    force = bool(body.get("force"))
    try:
        ok = remove_vault_record(vault_id, force=force)
        return jsonify({"ok": ok})
    except ValueError as exc:
        return _api_error(exc)


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
    body = request.get_json(force=True, silent=True) or {}
    accepted = bool(body.get("accepted", True)) and not bool(body.get("declined"))
    row = save_privacy_consent(DATA_DIR, accepted=accepted)
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
