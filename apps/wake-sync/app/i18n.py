# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
from typing import Any

LANG_COOKIE = "ws_lang"
_thread_lang = threading.local()

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "app.title": "Wake & Sync",
        "app.intro": "Festes Rezept: Ziel-NAS per Wake-on-LAN aufwecken, warten bis SMB erreichbar, dann einseitig synchronisieren (z. B. UGREEN → QNAP).",
        "app.wol_hint": "WoL: WOL_BROADCAST = Subnetz-Broadcast (z. B. 10.0.0.255). WOL_SOURCE_IP = IP am Link zum Ziel-NAS. Am Ziel-NAS WoL aktivieren.",
        "companion": "Desktop-Begleiter:",
        "ui.language": "Sprache",
        "plan.new": "Neuer Zeitplan",
        "plan.edit": "Zeitplan bearbeiten",
        "plan.update": "Änderungen speichern",
        "plan.cancel_edit": "Abbrechen",
        "plan.edit_btn": "Bearbeiten",
        "plan.name": "Name",
        "plan.name_ph": "z. B. Zweit-NAS täglich 12:30",
        "plan.run_at": "Uhrzeit",
        "plan.schedule_type": "Wiederholung",
        "plan.weekday": "Wochentag",
        "plan.monthly_week": "Im Monat",
        "schedule.type.daily": "Täglich",
        "schedule.type.weekly": "Wöchentlich",
        "schedule.type.biweekly": "Alle 2 Wochen",
        "schedule.type.monthly": "Monatlich",
        "schedule.daily": "Täglich {time}",
        "schedule.weekly": "Jeden {weekday} {time}",
        "schedule.biweekly": "Alle 2 Wochen {weekday} {time}",
        "schedule.monthly": "Jeden {nth} {weekday} im Monat {time}",
        "schedule.monthly_last": "letzten",
        "schedule.monthly_nth.1": "1.",
        "schedule.monthly_nth.2": "2.",
        "schedule.monthly_nth.3": "3.",
        "schedule.monthly_nth.4": "4.",
        "weekday.0": "Montag",
        "weekday.1": "Dienstag",
        "weekday.2": "Mittwoch",
        "weekday.3": "Donnerstag",
        "weekday.4": "Freitag",
        "weekday.5": "Samstag",
        "weekday.6": "Sonntag",
        "plan.col_schedule": "Zeitplan",
        "plan.enabled": "Aktiv",
        "plan.wol_info": "Wake-on-LAN nutzt IP und MAC des gewählten Ziel-NAS (siehe Geräte-Liste).",
        "plan.wol_preview": "WoL-Ziel: {ip} · MAC {mac} · Broadcast {bc}",
        "plan.wol_bc_hint": "WOL_BROADCAST in App-Einstellungen: {bc} (Broadcast, nicht die NAS-IP!)",
        "devices.wol_test": "WoL testen",
        "plan.wol_preview_missing": "WoL-Ziel: {ip} — MAC am Ziel-NAS noch eintragen",
        "plan.wake_broadcast": "WoL-Broadcast (optional)",
        "plan.ready_wait": "Wartezeit nach WoL (Minuten)",
        "plan.ready_port": "Prüf-Port (SMB 445)",
        "plan.source": "Quelle (dieses NAS)",
        "plan.dest": "Ziel (SMB-Freigabe)",
        "plan.save": "Zeitplan speichern",
        "plan.run": "Jetzt ausführen",
        "plan.delete": "Löschen",
        "plan.list": "Zeitpläne",
        "plan.running": "Läuft…",
        "plan.started": "Gestartet",
        "plan.ok": "Sync abgeschlossen.",
        "plan.fail_wol": "Wake-on-LAN fehlgeschlagen: {detail}",
        "plan.fail_wait": "Ziel nicht erreichbar: {detail}",
        "plan.fail_sync": "Sync fehlgeschlagen: {detail}",
        "plan.col_name": "Name",
        "plan.col_route": "Route",
        "plan.col_time": "Zeitplan",
        "plan.col_status": "Status",
        "plan.status_ok": "OK",
        "plan.status_fail": "Fehler",
        "plan.status_never": "Noch nicht gelaufen",
        "devices.target": "Ziel-NAS (SMB)",
        "devices.setup_hint": "Ziel-NAS muss eingeschaltet sein — beim Speichern wird die Ordnerstruktur gemerkt (später auch bei ausgeschaltetem NAS wählbar).",
        "devices.add": "Ziel-NAS hinzufügen",
        "devices.host_ph": "IP des Ziel-NAS",
        "devices.col_cache": "Ordner",
        "devices.cache_ready": "gespeichert",
        "devices.cache_missing": "fehlt",
        "devices.refresh_cache": "Ordner aktualisieren",
        "devices.scanning_cache": "Speichere Ordnerstruktur…",
        "devices.scanning_progress": "Scanne Ordner… ({n} Ebenen)",
        "devices.cache_building": "Scan läuft…",
        "devices.cache_partial": "teilweise gespeichert",
        "modal.online_required": "Ziel-NAS muss eingeschaltet und per SMB erreichbar sein.",
        "modal.add_device": "Ziel-NAS (SMB)",
        "modal.display_name": "Anzeigename",
        "modal.mac": "MAC (Wake-on-LAN)",
        "modal.mac_hint": "Aus der Systemsteuerung des Ziel-NAS — für Aufwecken nötig",
        "modal.user": "Benutzer",
        "modal.password": "Passwort",
        "modal.connect": "Speichern",
        "modal.cancel": "Abbrechen",
        "modal.pick_folder": "Ordner wählen",
        "modal.pick_hint": "Speicher wählen → Öffnen → Ordner auswählen.",
        "modal.pick_up": "↑ Übergeordnet",
        "modal.pick_here": "Diesen Ordner übernehmen",
        "picker.root": "Stamm",
        "picker.open": "Öffnen",
        "picker.select": "Auswählen",
        "picker.whole_volume": "Ganzes Volume",
        "picker.open_volume_fmt": "{label} öffnen",
        "browse.pick_volume": "Volume 1/2, USB oder UGOS-Ordner wählen.",
        "browse.no_subdirs": "Keine Unterordner (diesen Ordner direkt wählen).",
        "browse.cached_offline": "Gespeicherter Ordnerbaum (Ziel-NAS aus/ausgeschaltet).",
        "browse.cached_leaf": "Gespeichert — keine Unterordner in diesem Pfad.",
        "ui.pick_choose_volume": " / Speicher wählen",
        "ui.pick_volume_path": " / Volume {vol}{path}",
        "job.pick": "Ordner wählen…",
        "job.pick_none": "— Ordner wählen —",
        "volume.usb_name_fmt": "USB: {name}",
        "err.pick_volume_first": "Bitte zuerst Speicher wählen.",
        "err.smb_share_missing": "SMB-Freigabe fehlt — Ziel: Freigabe öffnen (z. B. Public), dann Ordner wählen.",
        "err.pick_share_first": "Bitte zuerst SMB-Freigabe öffnen, dann Ordner auswählen.",
        "err.device_not_found": "Gerät nicht gefunden",
        "err.nas_offline_no_cache": "Ziel-NAS nicht erreichbar und kein Ordnerbaum gespeichert — NAS einschalten und „Ordner aktualisieren“.",
        "err.cache_path_missing": "Pfad nicht im gespeicherten Baum — NAS einschalten und Ordner aktualisieren.",
        "err.nas_must_be_online": "Ziel-NAS muss eingeschaltet sein (SMB nicht erreichbar).",
        "err.cache_build_failed": "Ordnerstruktur konnte nicht gespeichert werden: {detail}",
        "err.cache_scan_failed": "Ordner-Scan fehlgeschlagen: {detail}",
        "device.this_nas": "Dieses NAS",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "UGOS-Ordner",
        "volume.whole": " (gesamt)",
        "notify.title": "Benachrichtigung",
        "notify.hint": "Standard: nur bei Fehler. Erfolg optional.",
        "notify.app_hint": "Werte aus UGOS-App-Einstellungen werden genutzt — hier nur zum Überschreiben.",
        "notify.on_fail": "Bei Fehler",
        "notify.on_success": "Bei Erfolg",
        "notify.test": "Test senden",
        "notify.save": "Speichern",
        "notify.fail_subject": "Wake & Sync — Fehler: {name}",
        "notify.ok_subject": "Wake & Sync — OK: {name}",
        "notify.fail_body": "Plan: {name}\n{route}\n\n{message}",
        "notify.ok_body": "Plan: {name}\n{route}\n\n{message}",
        "notify.test_subject": "Wake & Sync — Test",
        "notify.test_body": "Testbenachrichtigung.",
        "log.title": "Log",
        "log.refresh": "Aktualisieren",
        "err.plan_not_found": "Zeitplan nicht gefunden",
        "err.plan_running": "Läuft bereits",
        "err.pick_both": "Quelle und Ziel wählen",
        "err.mac_missing": "MAC-Adresse fehlt",
        "err.mac_on_device": "MAC am Ziel-NAS hinterlegen (Geräte-Liste)",
        "err.ip_missing": "Ziel-IP fehlt",
        "devices.col_mac": "MAC",
        "err.generic": "Fehler",
    },
    "en": {
        "app.title": "Wake & Sync",
        "app.intro": "Fixed recipe: wake target NAS via WoL, wait for SMB, one-way sync (e.g. UGREEN → QNAP).",
        "app.wol_hint": "WoL: set WOL_BROADCAST to subnet broadcast (e.g. 10.0.0.255). WOL_SOURCE_IP = your IP on the link to the target NAS. Enable WoL on the target NAS.",
        "companion": "Desktop companion:",
        "ui.language": "Language",
        "plan.new": "New schedule",
        "plan.edit": "Edit schedule",
        "plan.update": "Save changes",
        "plan.cancel_edit": "Cancel",
        "plan.edit_btn": "Edit",
        "plan.name": "Name",
        "plan.name_ph": "e.g. second NAS daily 12:30",
        "plan.run_at": "Time",
        "plan.schedule_type": "Repeat",
        "plan.weekday": "Weekday",
        "plan.monthly_week": "In month",
        "schedule.type.daily": "Daily",
        "schedule.type.weekly": "Weekly",
        "schedule.type.biweekly": "Every 2 weeks",
        "schedule.type.monthly": "Monthly",
        "schedule.daily": "Daily {time}",
        "schedule.weekly": "Every {weekday} {time}",
        "schedule.biweekly": "Every 2 weeks on {weekday} {time}",
        "schedule.monthly": "Every {nth} {weekday} of month {time}",
        "schedule.monthly_last": "last",
        "schedule.monthly_nth.1": "1st",
        "schedule.monthly_nth.2": "2nd",
        "schedule.monthly_nth.3": "3rd",
        "schedule.monthly_nth.4": "4th",
        "weekday.0": "Monday",
        "weekday.1": "Tuesday",
        "weekday.2": "Wednesday",
        "weekday.3": "Thursday",
        "weekday.4": "Friday",
        "weekday.5": "Saturday",
        "weekday.6": "Sunday",
        "plan.col_schedule": "Schedule",
        "plan.enabled": "Enabled",
        "plan.wol_info": "Wake-on-LAN uses the IP and MAC of the selected target NAS (see device list).",
        "plan.wol_preview": "WoL target: {ip} · MAC {mac} · broadcast {bc}",
        "plan.wol_bc_hint": "WOL_BROADCAST in app settings: {bc} (broadcast, not the NAS IP!)",
        "devices.wol_test": "Test WoL",
        "plan.wol_preview_missing": "WoL target: {ip} — add MAC on target NAS",
        "plan.wake_broadcast": "WoL broadcast (optional)",
        "plan.ready_wait": "Wait after WoL (minutes)",
        "plan.ready_port": "Check port (SMB 445)",
        "plan.source": "Source (this NAS)",
        "plan.dest": "Destination (SMB share)",
        "plan.save": "Save schedule",
        "plan.run": "Run now",
        "plan.delete": "Delete",
        "plan.list": "Schedules",
        "plan.running": "Running…",
        "plan.started": "Started",
        "plan.ok": "Sync completed.",
        "plan.fail_wol": "Wake-on-LAN failed: {detail}",
        "plan.fail_wait": "Target not reachable: {detail}",
        "plan.fail_sync": "Sync failed: {detail}",
        "plan.col_name": "Name",
        "plan.col_route": "Route",
        "plan.col_time": "Schedule",
        "plan.col_status": "Status",
        "plan.status_ok": "OK",
        "plan.status_fail": "Error",
        "plan.status_never": "Never run",
        "devices.target": "Target NAS (SMB)",
        "devices.setup_hint": "Target NAS must be powered on — folder structure is saved on add (usable later when NAS is off).",
        "devices.add": "Add target NAS",
        "devices.host_ph": "Target NAS IP",
        "devices.col_cache": "Folders",
        "devices.cache_ready": "saved",
        "devices.cache_missing": "missing",
        "devices.refresh_cache": "Refresh folders",
        "devices.scanning_cache": "Saving folder structure…",
        "devices.scanning_progress": "Scanning folders… ({n} levels)",
        "devices.cache_building": "Scan running…",
        "devices.cache_partial": "partially saved",
        "modal.online_required": "Target NAS must be on and reachable via SMB.",
        "modal.add_device": "Target NAS (SMB)",
        "modal.display_name": "Display name",
        "modal.mac": "MAC (Wake-on-LAN)",
        "modal.mac_hint": "From target NAS control panel — required for wake",
        "modal.user": "User",
        "modal.password": "Password",
        "modal.connect": "Save",
        "modal.cancel": "Cancel",
        "modal.pick_folder": "Pick folder",
        "modal.pick_hint": "Pick storage → Open → select folder.",
        "modal.pick_up": "↑ Parent",
        "modal.pick_here": "Use this folder",
        "picker.root": "Root",
        "picker.open": "Open",
        "picker.select": "Select",
        "picker.whole_volume": "Whole volume",
        "picker.open_volume_fmt": "Open {label}",
        "browse.pick_volume": "Pick Volume 1/2, USB, or UGOS folder.",
        "browse.no_subdirs": "No subfolders (select this folder directly).",
        "browse.cached_offline": "Saved folder tree (target NAS off/unreachable).",
        "browse.cached_leaf": "Saved — no subfolders at this path.",
        "ui.pick_choose_volume": " / pick storage",
        "ui.pick_volume_path": " / Volume {vol}{path}",
        "job.pick": "Pick folder…",
        "job.pick_none": "— pick folder —",
        "volume.usb_name_fmt": "USB: {name}",
        "err.pick_volume_first": "Pick storage first.",
        "err.smb_share_missing": "SMB share missing — open share (e.g. Public) then pick folder.",
        "err.pick_share_first": "Open SMB share first, then select folder.",
        "err.device_not_found": "Device not found",
        "err.nas_offline_no_cache": "Target NAS unreachable and no folder tree saved — power on NAS and use Refresh folders.",
        "err.cache_path_missing": "Path not in saved tree — power on NAS and refresh folders.",
        "err.nas_must_be_online": "Target NAS must be powered on (SMB unreachable).",
        "err.cache_build_failed": "Could not save folder structure: {detail}",
        "err.cache_scan_failed": "Folder scan failed: {detail}",
        "device.this_nas": "This NAS",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "UGOS folder",
        "volume.whole": " (whole)",
        "notify.title": "Notifications",
        "notify.hint": "Default: failures only. Success optional.",
        "notify.app_hint": "UGOS app settings are used — override here only if needed.",
        "notify.on_fail": "On failure",
        "notify.on_success": "On success",
        "notify.test": "Send test",
        "notify.save": "Save",
        "notify.fail_subject": "Wake & Sync — error: {name}",
        "notify.ok_subject": "Wake & Sync — OK: {name}",
        "notify.fail_body": "Plan: {name}\n{route}\n\n{message}",
        "notify.ok_body": "Plan: {name}\n{route}\n\n{message}",
        "notify.test_subject": "Wake & Sync — test",
        "notify.test_body": "Test notification.",
        "log.title": "Log",
        "log.refresh": "Refresh",
        "err.plan_not_found": "Schedule not found",
        "err.plan_running": "Already running",
        "err.pick_both": "Pick source and destination",
        "err.mac_missing": "MAC address missing",
        "err.mac_on_device": "Add MAC on target NAS (device list)",
        "err.ip_missing": "Target IP missing",
        "devices.col_mac": "MAC",
        "err.generic": "Error",
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
