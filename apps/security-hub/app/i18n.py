# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
from typing import Any

LANG_COOKIE = "security_hub_lang"
_thread_lang = threading.local()

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "app.title": "Security Hub",
        "app.intro": "Zugriffsverlauf und Live-Überwachung auf dem NAS — SSH, SMB, UGOS-App/Web und aktive Verbindungen. Nur Lesen, keine Sperre.",
        "app.mount_hint": "Liest Host-Logs unter /var/log und /var/ugreen/log. Sortieren, filtern, exportieren — alles sichtbar machen.",
        "app.readonly_note": "Keine IP-Sperre in dieser App: UGOS block_ip_list sperrt auf dem DXP4800 weder SSH noch SMB zuverlässig. Echten Zugriffsschutz über die UGOS-Firewall; IP-Sperre optional in Ugreen NAS Admin (Desktop).",
        "ui.language": "Sprache",
        "companion": "Desktop-Begleiter (Login Track + IP-Sperre):",
        "btn.refresh": "Aktualisieren",
        "btn.export": "Export",
        "live.enable": "Echtzeit (nur seit Tab-Start)",
        "live.hint": "Echtzeit an: nur neue Anmeldungen. Echtzeit aus: Historie laden.",
        "filter.hide_pings": "App-Session-Pings ausblenden",
        "sort.label": "Sortieren",
        "sort.time": "Datum / Uhrzeit",
        "sort.ip": "IP-Adresse",
        "sort.user": "Benutzer",
        "sort.source": "Quelle",
        "sort.outcome": "Ergebnis",
        "sort.desc": "Absteigend",
        "sort.asc": "Aufsteigend",
        "days.label": "Historie (Tage)",
        "col.time": "Zeit",
        "col.ip": "IP",
        "col.source": "Quelle",
        "col.outcome": "Ergebnis",
        "col.user": "Benutzer",
        "col.access": "Zugriff / Ziel",
        "col.detail": "Detail (Rohlog)",
        "access.hint": "SMB-Ordner und API-Pfade aus UGOS-/Samba-Audit; SSH zeigt Anmeldung/Sitzung.",
        "status.loading": "Lade Log-Daten …",
        "status.live_waiting": "Echtzeit aktiv — warte auf neue Anmeldungen …",
        "status.busy": "Abfrage läuft …",
        "status.entries": "{count} Einträge angezeigt",
        "status.collect_empty": "Keine Log-Einträge gefunden — Mounts und Log-Pfade prüfen (Diagnose unten).",
        "empty": "Noch keine Einträge. Echtzeit aus → Aktualisieren lädt Historie. Echtzeit an → warte auf neue Anmeldungen.",
        "diag.title": "Diagnose",
        "log.title": "App-Log",
        "export.empty": "Keine Daten zum Exportieren.",
    },
    "en": {
        "app.title": "Security Hub",
        "app.intro": "Access history and live monitoring on the NAS — SSH, SMB, UGOS app/web, and active connections. Read-only, no blocking.",
        "app.mount_hint": "Reads host logs under /var/log and /var/ugreen/log. Sort, filter, export — full visibility.",
        "app.readonly_note": "No IP block in this app: UGOS block_ip_list does not reliably block SSH or SMB on DXP4800. Use the UGOS firewall for real access control; optional IP block in Ugreen NAS Admin (desktop).",
        "ui.language": "Language",
        "companion": "Desktop companion (Login Track + block IP):",
        "btn.refresh": "Refresh",
        "btn.export": "Export",
        "live.enable": "Live (since tab start only)",
        "live.hint": "Live on: new logins only. Live off: load history.",
        "filter.hide_pings": "Hide app session pings",
        "sort.label": "Sort",
        "sort.time": "Date / time",
        "sort.ip": "IP address",
        "sort.user": "User",
        "sort.source": "Source",
        "sort.outcome": "Outcome",
        "sort.desc": "Descending",
        "sort.asc": "Ascending",
        "days.label": "History (days)",
        "col.time": "Time",
        "col.ip": "IP",
        "col.source": "Source",
        "col.outcome": "Outcome",
        "col.user": "User",
        "col.access": "Access / target",
        "col.detail": "Detail (raw log)",
        "access.hint": "SMB folders and API paths from UGOS/Samba audit; SSH shows login/session.",
        "status.loading": "Loading log data …",
        "status.live_waiting": "Live active — waiting for new logins …",
        "status.busy": "Query in progress …",
        "status.entries": "{count} entries shown",
        "status.collect_empty": "No log entries found — check mounts and log paths (diagnostics below).",
        "empty": "No entries yet. Live off → Refresh loads history. Live on → wait for new logins.",
        "diag.title": "Diagnostics",
        "log.title": "App log",
        "export.empty": "Nothing to export.",
    },
}


def env_lang() -> str:
    tz = (os.environ.get("TZ") or "").lower()
    loc = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    if "de" in loc or tz == "europe/berlin":
        return "de"
    return "en"


def normalize_lang(raw: str | None) -> str | None:
    if not raw:
        return None
    v = str(raw).strip().lower()[:2]
    return v if v in STRINGS else None


def set_thread_lang(lang: str | None) -> None:
    if lang:
        _thread_lang.value = lang
    elif hasattr(_thread_lang, "value"):
        del _thread_lang.value


def get_lang() -> str:
    tl = getattr(_thread_lang, "value", None)
    if tl:
        return tl
    try:
        from flask import g

        return getattr(g, "lang", "en")
    except RuntimeError:
        return env_lang()


def lang_from_request(request) -> str:
    c = normalize_lang(request.cookies.get(LANG_COOKIE))
    if c:
        return c
    q = normalize_lang(request.args.get("lang"))
    if q:
        return q
    accept = (request.headers.get("Accept-Language") or "").lower()
    if accept.startswith("de"):
        return "de"
    return env_lang()


def t(key: str, lang: str | None = None, **fmt: Any) -> str:
    lng = lang or get_lang()
    s = STRINGS.get(lng, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    if fmt:
        try:
            return s.format(**fmt)
        except (KeyError, ValueError):
            return s
    return s


def bundle(lang: str) -> dict[str, str]:
    return dict(STRINGS.get(lang, STRINGS["en"]))
