# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
from typing import Any

LANG_COOKIE = "sh_lang"
_thread_lang = threading.local()

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "app.title": "Stats Hub",
        "app.intro": "Live-Systemstatistik — CPU/RAM/Netz/Volumes primär über UGOS-Web-API (wie UGOS-GUI), Docker/RAID/SMART weiter per Host.",
        "ui.language": "Sprache",
        "companion": "Desktop-Begleiter:",
        "hw.title": "Hardware",
        "hw.cpu": "CPU",
        "hw.ram": "RAM",
        "hw.temp": "CPU-Temp",
        "hw.load": "Load",
        "hw.fan": "Lüfter",
        "hw.fan_none": "Keine Lüfter-Sensoren (/proc/it86/fan, hwmon)",
        "vol.title": "Volumes & Speicher",
        "storage.title": "RAID & Festplatten",
        "storage.raid": "RAID (mdstat)",
        "storage.raid_none": "Kein md-Array erkannt",
        "storage.disks": "Festplatten-Temperatur",
        "storage.disks_hint": "SMART-Temperatur (Firmware aktualisiert oft erst alle 1–3 Min).",
        "storage.disks_updated": "Zuletzt gelesen: vor {sec}s",
        "storage.poll_interval": "Abfrage-Intervall",
        "storage.poll_15s": "15 Sekunden",
        "storage.poll_30s": "30 Sekunden",
        "storage.poll_60s": "1 Minute",
        "storage.poll_120s": "2 Minuten",
        "storage.poll_300s": "5 Minuten",
        "storage.poll_600s": "10 Minuten",
        "storage.poll_1800s": "30 Minuten",
        "storage.skip_standby": "HDD: im Standby nicht wecken",
        "storage.skip_standby_hint": "Nur Festplatten (rotational). SSD/NVMe werden immer gelesen. HDD nach Zugriff: Temperatur sobald I/O erkannt.",
        "storage.save": "Speichern",
        "storage.saved": "Gespeichert",
        "storage.standby": "Standby",
        "storage.disks_none": "Keine Disk-Temperaturen (smartctl/hwmon)",
        "storage.col_drive": "Laufwerk",
        "storage.col_slot": "Slot",
        "net.title": "Netzwerk",
        "apps.title": "Runlevel Apps",
        "apps.open": "Öffnen",
        "apps.offline": "nicht erreichbar",
        "apps.self": "dieses Dashboard",
        "net.no_ip": "Keine IPv4 (Link evtl. down)",
        "net.default": "Standardroute",
        "net.gateway": "Gateway",
        "docker.title": "Docker",
        "docker.empty": "Keine Container",
        "docker.df": "Speicher",
        "docker.health": "Health",
        "docker.runlevel": "Runlevel",
        "proc.title": "Prozess Top-5 (CPU)",
        "proc.empty": "Keine Prozessdaten",
        "proc.col_cpu": "CPU %",
        "proc.col_mem": "RAM %",
        "proc.col_cmd": "Befehl",
        "top.title": "Größte Ordner",
        "top.scan": "Neu scannen",
        "top.scanning": "Scan läuft (du, max. ~5 Min) …",
        "top.empty": "Noch kein Scan",
        "top.col_path": "Ordner",
        "top.col_gb": "GB",
        "os.title": "System",
        "log.title": "Log",
        "status.waiting": "Warte auf erste Messung …",
        "status.offline": "Keine Host-Daten — pid:host / privileged prüfen",
        "ugos.title": "UGOS Web-API",
        "ugos.hint": "Gleiche Live-Quelle wie Ugreen NAS Admin (Port 9443, RSA-Login). Host 127.0.0.1 bei network_mode: host.",
        "ugos.enabled": "UGOS-API aktiv",
        "ugos.host": "Host",
        "ugos.port": "Port",
        "ugos.user": "Benutzer",
        "ugos.password": "Passwort",
        "ugos.password_placeholder": "leer = unverändert",
        "ugos.https": "HTTPS",
        "ugos.verify_ssl": "SSL-Zertifikat prüfen",
        "ugos.save": "Speichern",
        "ugos.saved": "Gespeichert",
        "ugos.source_active": "Datenquelle: UGOS Web-API",
        "ugos.source_host": "Datenquelle: Host (/proc) — UGOS-API nicht aktiv",
        "ugos.error": "UGOS-API: {msg}",
    },
    "en": {
        "app.title": "Stats Hub",
        "app.intro": "Live system stats — CPU/RAM/network/volumes primarily via UGOS Web API (same as UGOS GUI); Docker/RAID/SMART still from host.",
        "ui.language": "Language",
        "companion": "Desktop companion:",
        "hw.title": "Hardware",
        "hw.cpu": "CPU",
        "hw.ram": "RAM",
        "hw.temp": "CPU temp",
        "hw.load": "Load",
        "hw.fan": "Fans",
        "hw.fan_none": "No fan sensors (/proc/it86/fan, hwmon)",
        "vol.title": "Volumes & storage",
        "storage.title": "RAID & disks",
        "storage.raid": "RAID (mdstat)",
        "storage.raid_none": "No md array detected",
        "storage.disks": "Disk temperature",
        "storage.disks_hint": "SMART temperature (drive firmware often updates only every 1–3 min).",
        "storage.disks_updated": "Last read: {sec}s ago",
        "storage.poll_interval": "Poll interval",
        "storage.poll_15s": "15 seconds",
        "storage.poll_30s": "30 seconds",
        "storage.poll_60s": "1 minute",
        "storage.poll_120s": "2 minutes",
        "storage.poll_300s": "5 minutes",
        "storage.poll_600s": "10 minutes",
        "storage.poll_1800s": "30 minutes",
        "storage.skip_standby": "HDD: do not wake from standby",
        "storage.skip_standby_hint": "Rotational drives only. SSD/NVMe always read. HDD after access: temp once I/O is detected.",
        "storage.save": "Save",
        "storage.saved": "Saved",
        "storage.standby": "Standby",
        "storage.disks_none": "No disk temps (smartctl/hwmon)",
        "storage.col_drive": "Drive",
        "storage.col_slot": "Slot",
        "net.title": "Network",
        "apps.title": "Runlevel apps",
        "apps.open": "Open",
        "apps.offline": "not reachable",
        "apps.self": "this dashboard",
        "net.no_ip": "No IPv4 (link may be down)",
        "net.default": "Default route",
        "net.gateway": "Gateway",
        "docker.title": "Docker",
        "docker.empty": "No containers",
        "docker.df": "Disk usage",
        "docker.health": "Health",
        "docker.runlevel": "Runlevel",
        "proc.title": "Process top 5 (CPU)",
        "proc.empty": "No process data",
        "proc.col_cpu": "CPU %",
        "proc.col_mem": "RAM %",
        "proc.col_cmd": "Command",
        "top.title": "Largest folders",
        "top.scan": "Scan again",
        "top.scanning": "Scan running (du, up to ~5 min) …",
        "top.empty": "No scan yet",
        "top.col_path": "Folder",
        "top.col_gb": "GB",
        "os.title": "System",
        "log.title": "Log",
        "status.waiting": "Waiting for first sample …",
        "status.offline": "No host data — check pid:host / privileged",
        "ugos.title": "UGOS Web API",
        "ugos.hint": "Same live source as Ugreen NAS Admin (port 9443, RSA login). Use 127.0.0.1 with network_mode: host.",
        "ugos.enabled": "UGOS API enabled",
        "ugos.host": "Host",
        "ugos.port": "Port",
        "ugos.user": "Username",
        "ugos.password": "Password",
        "ugos.password_placeholder": "empty = unchanged",
        "ugos.https": "HTTPS",
        "ugos.verify_ssl": "Verify SSL certificate",
        "ugos.save": "Save",
        "ugos.saved": "Saved",
        "ugos.source_active": "Data source: UGOS Web API",
        "ugos.source_host": "Data source: host (/proc) — UGOS API inactive",
        "ugos.error": "UGOS API: {msg}",
    },
}


def env_lang() -> str:
    loc = (os.environ.get("LANG") or "").lower()
    return "de" if "de" in loc else "en"


def normalize_lang(raw: str | None) -> str | None:
    if not raw:
        return None
    v = str(raw).strip().lower()[:2]
    return v if v in STRINGS else None


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
    if normalize_lang(request.args.get("lang")):
        return normalize_lang(request.args.get("lang")) or "en"
    if (request.headers.get("Accept-Language") or "").lower().startswith("de"):
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
