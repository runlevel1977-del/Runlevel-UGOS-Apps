# -*- coding: utf-8 -*-
"""Email and Telegram notifications on verification failure."""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

from i18n import get_lang, t
from store import append_log, load_settings, save_settings

_MASK = "***"


def _env_default(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()


def default_settings() -> dict[str, Any]:
    return {
        "notify_on_fail": True,
        "telegram_enabled": bool(_env_default("TELEGRAM_BOT_TOKEN")),
        "telegram_bot_token": _env_default("TELEGRAM_BOT_TOKEN"),
        "telegram_chat_id": _env_default("TELEGRAM_CHAT_ID"),
        "email_enabled": bool(_env_default("SMTP_HOST") and _env_default("EMAIL_TO")),
        "smtp_host": _env_default("SMTP_HOST"),
        "smtp_port": int(_env_default("SMTP_PORT", "587") or "587"),
        "smtp_tls": _env_default("SMTP_TLS", "true").lower() not in ("0", "false", "no"),
        "smtp_user": _env_default("SMTP_USER"),
        "smtp_password": _env_default("SMTP_PASSWORD"),
        "email_from": _env_default("EMAIL_FROM"),
        "email_to": _env_default("EMAIL_TO"),
    }


def _merge_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = default_settings()
    if not raw:
        return out
    for k in out:
        if k in raw and raw[k] is not None:
            out[k] = raw[k]
    if isinstance(out.get("smtp_port"), str):
        try:
            out["smtp_port"] = int(out["smtp_port"])
        except ValueError:
            out["smtp_port"] = 587
    return out


def get_notify_settings() -> dict[str, Any]:
    return _merge_settings(load_settings())


def _field_from_app(stored: dict[str, Any], key: str) -> bool:
    env_val = default_settings().get(key)
    if not env_val:
        return False
    return key not in stored or not (stored.get(key) or "")


def public_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    stored = load_settings() or {}
    s = _merge_settings(stored if settings is None else settings)
    pub = dict(s)
    if pub.get("telegram_bot_token"):
        pub["telegram_bot_token"] = _MASK
        pub["telegram_token_set"] = True
    else:
        pub["telegram_token_set"] = False
    if pub.get("smtp_password"):
        pub["smtp_password"] = _MASK
        pub["smtp_password_set"] = True
    else:
        pub["smtp_password_set"] = False
    pub["telegram_from_app"] = _field_from_app(stored, "telegram_bot_token")
    pub["telegram_chat_from_app"] = _field_from_app(stored, "telegram_chat_id")
    pub["smtp_from_app"] = _field_from_app(stored, "smtp_host")
    pub["smtp_password_from_app"] = _field_from_app(stored, "smtp_password")
    pub["email_to_from_app"] = _field_from_app(stored, "email_to")
    pub["has_ui_overrides"] = bool(stored)
    return pub


def save_notify_settings(body: dict[str, Any]) -> dict[str, Any]:
    cur = _merge_settings(load_settings())
    fields = (
        "notify_on_fail",
        "telegram_enabled",
        "telegram_bot_token",
        "telegram_chat_id",
        "email_enabled",
        "smtp_host",
        "smtp_port",
        "smtp_tls",
        "smtp_user",
        "smtp_password",
        "email_from",
        "email_to",
    )
    for key in fields:
        if key not in body:
            continue
        val = body[key]
        if key in ("telegram_bot_token", "smtp_password") and val in (_MASK, "", None):
            continue
        if key == "smtp_port":
            try:
                val = int(val)
            except (TypeError, ValueError):
                val = 587
        if key in ("notify_on_fail", "telegram_enabled", "email_enabled", "smtp_tls"):
            val = bool(val)
        cur[key] = val
    save_settings(cur)
    return public_settings(cur)


def _send_telegram(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not token or not chat_id:
        return False, "telegram not configured"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text[:4000]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 400:
                return False, f"telegram HTTP {resp.status}"
        return True, "telegram sent"
    except urllib.error.HTTPError as ex:
        body = ex.read().decode("utf-8", errors="replace")[:300]
        return False, f"telegram HTTP {ex.code}: {body}"
    except Exception as ex:
        return False, str(ex)


def _send_email(settings: dict[str, Any], subject: str, body: str) -> tuple[bool, str]:
    host = settings.get("smtp_host") or ""
    to_addr = settings.get("email_to") or ""
    if not host or not to_addr:
        return False, "email not configured"
    port = int(settings.get("smtp_port") or 587)
    user = settings.get("smtp_user") or ""
    password = settings.get("smtp_password") or ""
    from_addr = settings.get("email_from") or user or to_addr
    use_tls = bool(settings.get("smtp_tls", True))

    msg = EmailMessage()
    msg["Subject"] = subject[:200]
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        if use_tls and port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        return True, "email sent"
    except Exception as ex:
        return False, str(ex)


def send_test_notifications(lang: str | None = None) -> list[dict[str, str]]:
    lng = lang or get_lang()
    settings = get_notify_settings()
    text = t("notify.test_body", lng)
    subject = t("notify.test_subject", lng)
    results: list[dict[str, str]] = []
    if settings.get("telegram_enabled"):
        ok, msg = _send_telegram(
            settings.get("telegram_bot_token", ""),
            settings.get("telegram_chat_id", ""),
            text,
        )
        results.append({"channel": "telegram", "ok": ok, "message": msg})
    if settings.get("email_enabled"):
        ok, msg = _send_email(settings, subject, text)
        results.append({"channel": "email", "ok": ok, "message": msg})
    if not results:
        results.append({"channel": "none", "ok": False, "message": t("notify.none_enabled", lng)})
    return results


def notify_job_fail(
    job_name: str,
    route: str,
    fail_message: str,
    lang: str | None = None,
) -> None:
    lng = lang or get_lang()
    settings = get_notify_settings()
    if not settings.get("notify_on_fail"):
        return

    subject = t("notify.fail_subject", lng, name=job_name)
    body = t(
        "notify.fail_body",
        lng,
        name=job_name,
        route=route,
        message=fail_message,
    )
    sent_any = False
    if settings.get("telegram_enabled"):
        ok, msg = _send_telegram(
            settings.get("telegram_bot_token", ""),
            settings.get("telegram_chat_id", ""),
            f"{subject}\n\n{body}",
        )
        append_log(f"NOTIFY telegram: {msg}" if ok else f"NOTIFY telegram FAIL: {msg}")
        sent_any = sent_any or ok
    if settings.get("email_enabled"):
        ok, msg = _send_email(settings, subject, body)
        append_log(f"NOTIFY email: {msg}" if ok else f"NOTIFY email FAIL: {msg}")
        sent_any = sent_any or ok
    if not sent_any and (settings.get("telegram_enabled") or settings.get("email_enabled")):
        append_log("NOTIFY: all channels failed or misconfigured")
