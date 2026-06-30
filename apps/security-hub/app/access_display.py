# -*- coding: utf-8 -*-
"""Zugriffsziel aus LoginEvent ableiten (SMB-Pfad, API, Dienst)."""
from __future__ import annotations

import re

from access_collect import LoginEvent

_UGOS_API = re.compile(r"(/ugreen/v1/[^\s,\"']+)")
_VOLUME_PATH = re.compile(r"(/volume\d+/[^\s|\"']+)", re.IGNORECASE)
_WIN_UNC = re.compile(r"(\\\\[^\s|\"']+)")
_NAS_CONN = re.compile(r"Client ([^:]+):(\d+) -> ([^:]+):(\d+)", re.IGNORECASE)

_PORT_LABELS: dict[str, str] = {
    "22": "SSH",
    "80": "HTTP",
    "443": "HTTPS",
    "445": "SMB",
    "139": "SMB (NetBIOS)",
    "2049": "NFS",
    "9999": "UGOS",
    "9443": "HTTPS (alt)",
}


def _port_label(port: str) -> str:
    return _PORT_LABELS.get(port, f"TCP :{port}")


def format_access_target(ev: LoginEvent) -> str:
    source = (ev.source or "").strip()
    detail = (ev.detail or "").strip()
    outcome = (ev.outcome or "").strip().lower()
    if not detail and not source:
        return ""

    if source == "UGOS Samba":
        if "|" in detail:
            left, right = detail.split("|", 1)
            target = right.strip()
            action = left.strip()
            if target:
                return f"{action}: {target}" if action else target
        m = _VOLUME_PATH.search(detail) or _WIN_UNC.search(detail)
        return m.group(1) if m else detail

    if source == "SSH":
        if outcome == "ok":
            return "SSH-Anmeldung (Shell)"
        if outcome == "session" or "session" in detail.lower():
            return "SSH-Sitzung"
        if outcome == "failed":
            return "SSH (fehlgeschlagen)"
        if "disconnect" in detail.lower():
            return "SSH-Trennung"
        return "SSH"

    if source == "NAS connection":
        m = _NAS_CONN.search(detail)
        if m:
            svc = _port_label(m.group(4))
            return f"{svc} → {m.group(3)}:{m.group(4)}"
        return detail

    if source in ("UGOS HTTP", "UGOS Web"):
        m = _UGOS_API.search(detail)
        return m.group(1) if m else detail

    if source.startswith("UGOS"):
        m = _UGOS_API.search(detail)
        if m:
            return m.group(1)
        m = _VOLUME_PATH.search(detail) or _WIN_UNC.search(detail)
        if m:
            return m.group(1)
        low = detail.lower()
        if "logged in successfully" in low or "login-anfrage" in low:
            return "UGOS-Anmeldung"
        if "app-zugriff" in low or "session aktiv" in low or "is_login" in low:
            return "UGOS-App-Session"
        if "verify/login" in low:
            return "/ugreen/v1/verify/login"
        if detail:
            return detail[:120]

    if source == "lastlog":
        return "Letzter Login (lastlog)"

    if source == "last":
        return detail[:120] if detail else "last"

    m = _UGOS_API.search(detail) or _VOLUME_PATH.search(detail) or _WIN_UNC.search(detail)
    if m:
        return m.group(1)

    return detail[:120] if detail else ""
