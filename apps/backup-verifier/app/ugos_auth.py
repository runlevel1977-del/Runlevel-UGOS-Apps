# -*- coding: utf-8 -*-
"""Standalone app authentication for UGOS Docker apps.

Auth is a unique 32-character session ID created after login and stored
server-side. Client-supplied headers (Ugreen-User-ID, user_id, user_type, …)
are never treated as authentication.
Passwords on the wire must be RSA-OAEP (SHA-256); plaintext is rejected.
"""
from __future__ import annotations

import functools
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Callable

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    session,
    url_for,
)

from transport_rsa import decrypt_oaep, public_pem

_DEV_BYPASS = os.environ.get("UGOS_AUTH_DEV_BYPASS", "0").strip() == "1"
_HEALTH_PATHS = frozenset({"/health", "/healthz"})
_PUBLIC_PATHS = frozenset({
    "/login",
    "/api/login",
    "/api/auth/status",
    "/api/crypto/public-key",
    "/api/privacy/status",
    "/api/privacy/consent",
    "/static/rsa_http.js",
})
_ADMIN_ONLY = os.environ.get("UGOS_AUTH_ADMIN_ONLY", "1").strip() != "0"
_SESSION_KEY = "ugos_auth_sid"
_AUTH_FILE = "app_auth.json"
_SID_LEN = 32

_LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{{ title }}</title>
  <style>
    body{font-family:system-ui,sans-serif;background:#0f1419;color:#e8eef4;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
    .box{background:#1a2332;border:1px solid #334;border-radius:12px;padding:1.5rem 1.75rem;width:min(420px,92vw)}
    h1{margin:0 0 .5rem;font-size:1.25rem;color:#93c5fd}
    p{color:#8fa3b8;font-size:.9rem;line-height:1.45}
    label{display:block;margin:.85rem 0 .35rem;font-size:.82rem;color:#8fa3b8}
    input{width:100%;box-sizing:border-box;background:#0a0e12;color:#e8eef4;border:1px solid #445;border-radius:8px;padding:.55rem .7rem}
    button{margin-top:1rem;width:100%;background:#2d9f6f;color:#fff;border:none;border-radius:8px;padding:.6rem;font-size:.95rem;cursor:pointer}
    button.secondary{background:#445;margin-top:0}
    .err{color:#f87171;font-size:.85rem;margin-top:.75rem}
    .row{display:flex;gap:.5rem;margin-top:1rem}
    .row button{flex:1;margin-top:0}
    #consent{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:9999;align-items:center;justify-content:center;padding:1rem}
    #consent .box{max-width:520px}
  </style>
</head>
<body>
  <form class="box" id="login-form" style="display: {{ 'none' if needs_consent else 'block' }};">
    <h1>{{ title }}</h1>
    <p>{{ hint }}</p>
    {% if setup %}
    <label>New password</label>
    <input type="password" id="pw" required minlength="8" autocomplete="new-password"/>
    <label>Confirm password</label>
    <input type="password" id="pw2" required minlength="8" autocomplete="new-password"/>
    {% else %}
    <label>Password</label>
    <input type="password" id="pw" required autocomplete="current-password"/>
    {% endif %}
    <p class="err" id="err" {% if not error %}style="display:none"{% endif %}>{{ error }}</p>
    <button type="submit">{{ button }}</button>
  </form>
  <div id="consent" style="display: {{ 'flex' if needs_consent else 'none' }};">
    <div class="box">
      <h1>Privacy notice / 隐私声明</h1>
      <p>Please read the <a href="{{ privacy_url }}" target="_blank" rel="noopener" style="color:#3b82f6">privacy policy</a>
      before continuing. You may agree or decline; declining is as easy as agreeing.
      If you decline, optional credential storage stays disabled.</p>
      <p>请先阅读<a href="{{ privacy_url }}" target="_blank" rel="noopener" style="color:#3b82f6">隐私政策</a>。
      同意与拒绝同样方便。若拒绝，则不会保存可选凭据。</p>
      <div class="row">
        <button type="button" id="consent-yes">I agree / 同意</button>
        <button type="button" class="secondary" id="consent-no">Decline / 拒绝</button>
      </div>
    </div>
  </div>
  <script src="/static/rsa_http.js"></script>
  <script>
  (function () {
    const setup = {{ 'true' if setup else 'false' }};
    const overlay = document.getElementById('consent');

    async function encryptSecret(plain) {
      if (typeof window.rlEncryptSecret !== 'function') {
        throw new Error('encryption unavailable');
      }
      return window.rlEncryptSecret(plain);
    }
    async function sendConsent(accepted) {
      const r = await fetch('/api/privacy/consent', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: JSON.stringify({accepted: !!accepted, declined: !accepted})
      });
      if (!r.ok) throw new Error('consent failed');
      if (overlay) overlay.style.display = 'none';
      const form = document.getElementById('login-form');
      if (form) form.style.display = 'block';
    }
    document.getElementById('consent-yes')?.addEventListener('click', function () {
      sendConsent(true).catch(function (e) { alert(e.message || e); });
    });
    document.getElementById('consent-no')?.addEventListener('click', function () {
      sendConsent(false).catch(function (e) { alert(e.message || e); });
    });

    document.getElementById('login-form').addEventListener('submit', async function (ev) {
      ev.preventDefault();
      const err = document.getElementById('err');
      err.style.display = 'none';
      try {
        const pw = document.getElementById('pw').value;
        const body = {password_enc: await encryptSecret(pw)};
        if (setup) {
          const pw2 = document.getElementById('pw2').value;
          body.password2_enc = await encryptSecret(pw2);
        }
        const r = await fetch('/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
          body: JSON.stringify(body)
        });
        const j = await r.json().catch(function () { return {}; });
        if (!r.ok || !j.ok) {
          err.textContent = j.error || 'Sign-in failed';
          err.style.display = 'block';
          return;
        }
        location.href = {{ next_path|tojson }};
      } catch (e) {
        err.textContent = e.message || 'Sign-in failed';
        err.style.display = 'block';
      }
    });
  })();
  </script>
</body>
</html>
"""


def _data_dir() -> Path:
    for key in (
        "STATS_HUB_DATA",
        "WAKE_SYNC_DATA",
        "TRANSFER_HUB_DATA",
        "BACKUP_VERIFIER_DATA",
        "SECURITY_HUB_DATA",
        "LOCK_KEY_DATA",
        "DATA_DIR",
        "APP_DATA",
        "RUNLEVEL_DATA",
    ):
        raw = os.environ.get(key, "").strip()
        if raw:
            return Path(raw)
    return Path("/data")


def _auth_path() -> Path:
    return _data_dir() / _AUTH_FILE


def _load_auth() -> dict:
    path = _auth_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_auth(data: dict) -> None:
    path = _auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    ).hex()


def password_is_set() -> bool:
    data = _load_auth()
    return bool(data.get("salt") and data.get("hash"))


def set_password(password: str) -> None:
    salt = secrets.token_hex(16)
    data = _load_auth()
    data["salt"] = salt
    data["hash"] = _hash_password(password, salt)
    _save_auth(data)


def verify_password(password: str) -> bool:
    data = _load_auth()
    salt = data.get("salt") or ""
    expected = data.get("hash") or ""
    if not salt or not expected:
        return False
    got = _hash_password(password, salt)
    return hmac.compare_digest(got, expected)


def _new_session_id() -> str:
    return secrets.token_hex(_SID_LEN // 2)


def _issue_session() -> str:
    sid = _new_session_id()
    data = _load_auth()
    data["session_id"] = sid
    _save_auth(data)
    session.clear()
    session[_SESSION_KEY] = sid
    session.permanent = True
    return sid


def _clear_session() -> None:
    data = _load_auth()
    data.pop("session_id", None)
    if data:
        _save_auth(data)
    session.clear()


def _session_ok() -> bool:
    sid = str(session.get(_SESSION_KEY) or "")
    expected = str(_load_auth().get("session_id") or "")
    if len(sid) != _SID_LEN or len(expected) != _SID_LEN:
        return False
    return hmac.compare_digest(sid, expected)


def _check_user() -> tuple[bool, str]:
    if _DEV_BYPASS:
        return True, ""
    if _session_ok():
        return True, ""
    return False, "Authentication required"


def _check_admin() -> tuple[bool, str]:
    return _check_user()


def _unauthorized_response(reason: str, code: int):
    want_json = (
        request.path.startswith("/api/")
        or "application/json" in (request.headers.get("Accept") or "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    if want_json:
        return jsonify({"ok": False, "error": reason}), code
    return redirect(url_for("ugos_login", next=request.path))


def _passwords_from_body() -> tuple[str, str]:
    data = request.get_json(silent=True)
    if data is None:
        data = request.form.to_dict() if request.form else {}
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    if str(data.get("password") or "").strip() or str(data.get("password2") or "").strip():
        raise ValueError("Plaintext passwords are not accepted")
    enc = str(data.get("password_enc") or "").strip()
    enc2 = str(data.get("password2_enc") or "").strip()
    if not enc:
        raise ValueError("Encrypted password required")
    pw = decrypt_oaep(_data_dir(), enc)
    pw2 = decrypt_oaep(_data_dir(), enc2) if enc2 else ""
    return pw, pw2


def require_ugos_admin(f: Callable) -> Callable:
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        ok, reason = _check_admin()
        if not ok:
            return _unauthorized_response(reason, 401)
        return f(*args, **kwargs)

    return wrapper


def require_ugos_user(f: Callable) -> Callable:
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        ok, reason = _check_user()
        if not ok:
            return _unauthorized_response(reason, 401)
        return f(*args, **kwargs)

    return wrapper


def _ensure_secret_key(app: Flask) -> None:
    if app.secret_key:
        return
    path = _data_dir() / ".flask_secret"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        key = path.read_text(encoding="utf-8").strip()
    else:
        key = secrets.token_hex(32)
        path.write_text(key, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    app.secret_key = key


def _privacy_url() -> str:
    try:
        from compliance import public_links
        return public_links()["privacy"]
    except Exception:
        return "https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/privacy/statshub.md"


def _needs_consent() -> bool:
    try:
        from compliance import has_privacy_decision
        return not has_privacy_decision(_data_dir())
    except Exception:
        return True


def init_ugos_auth(app: Flask, *, admin_only: bool | None = None) -> None:
    """Protect every route except health/login/crypto/privacy. Idempotent."""
    if getattr(app, "_ugos_auth_inited", False):
        return
    app._ugos_auth_inited = True
    _ensure_secret_key(app)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_NAME"] = "ugos_app_sid"
    use_admin = _ADMIN_ONLY if admin_only is None else admin_only

    @app.route("/static/rsa_http.js")
    def ugos_rsa_js():
        path = Path(__file__).resolve().parent / "rsa_http.js"
        return send_file(path, mimetype="application/javascript; charset=utf-8")

    @app.route("/login", methods=["GET"])
    def ugos_login():
        setup = not password_is_set()
        nxt = request.args.get("next") or "/"
        if not nxt.startswith("/") or nxt.startswith("//"):
            nxt = "/"
        return render_template_string(
            _LOGIN_HTML,
            setup=setup,
            error="",
            title="Set app password" if setup else "Sign in",
            hint=(
                "First launch: choose a password for this app (stored only on this NAS)."
                if setup
                else "Enter the app password. Direct access without login is not allowed."
            ),
            button="Save password" if setup else "Sign in",
            privacy_url=_privacy_url(),
            needs_consent=_needs_consent(),
            next_path=nxt,
        )

    @app.route("/logout", methods=["POST", "GET"])
    def ugos_logout():
        _clear_session()
        return redirect(url_for("ugos_login"))

    @app.route("/api/crypto/public-key")
    def ugos_crypto_public_key():
        return jsonify({
            "ok": True,
            "alg": "RSA-OAEP-SHA256",
            "pem": public_pem(_data_dir()),
        })

    @app.route("/api/auth/status")
    def ugos_auth_status():
        ok, _reason = _check_admin() if use_admin else _check_user()
        return jsonify({
            "ok": True,
            "authenticated": ok,
            "password_set": password_is_set(),
            "auth_id_len": _SID_LEN if ok else 0,
        })

    @app.route("/api/login", methods=["POST"])
    def ugos_api_login():
        if _needs_consent():
            return jsonify({"ok": False, "error": "privacy_consent_required"}), 403
        try:
            pw, pw2 = _passwords_from_body()
        except Exception as ex:
            return jsonify({"ok": False, "error": str(ex)}), 400
        setup = not password_is_set()
        if setup:
            if len(pw) < 8:
                return jsonify({"ok": False, "error": "Password too short"}), 400
            if pw2 and pw != pw2:
                return jsonify({"ok": False, "error": "Passwords do not match"}), 400
            if not pw2:
                return jsonify({"ok": False, "error": "Confirm password required"}), 400
            set_password(pw)
            sid = _issue_session()
            return jsonify({"ok": True, "setup": True, "auth_id_len": len(sid)})
        if not verify_password(pw):
            return jsonify({"ok": False, "error": "Invalid password"}), 401
        sid = _issue_session()
        return jsonify({"ok": True, "auth_id_len": len(sid)})

    @app.before_request
    def _ugos_auth_gate():
        if request.path in _HEALTH_PATHS or request.path in _PUBLIC_PATHS:
            return None
        ok, reason = _check_admin() if use_admin else _check_user()
        if ok:
            return None
        return _unauthorized_response(reason, 401)

    @app.after_request
    def _ugos_utf8_charset(resp):
        ct = resp.headers.get("Content-Type") or ""
        lower = ct.lower()
        if "charset=" in lower:
            return resp
        if lower.startswith("text/html"):
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
        elif lower.startswith("application/json"):
            resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp
