# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
from typing import Any

LANG_COOKIE = "bv_lang"
_thread_lang = threading.local()

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "app.title": "Backup Verifier",
        "app.intro": "Vergleicht zwei Ordner — dieses NAS, USB, PC-Freigabe (SMB) oder anderes NAS. Nur lesen, nichts wird kopiert oder gelöscht.",
        "app.readonly": "NAS-Pfade sind schreibgeschützt; SMB/PC wird nur per rclone check gelesen.",
        "devices.network": "Geräte im Netz",
        "devices.scan": "Netzwerk scannen",
        "devices.scan_loading": "Heimnetz: wird geladen…",
        "devices.add_ip_btn": "Hinzufügen…",
        "devices.saved": "Gespeicherte Geräte",
        "devices.host": "Host",
        "devices.services": "Dienste",
        "devices.name": "Name",
        "devices.type": "Typ",
        "devices.remove": "Entfernen",
        "devices.add": "Hinzufügen",
        "modal.add_device": "Gerät hinzufügen (SMB)",
        "modal.display_name": "Anzeigename",
        "modal.user": "Benutzer (SMB)",
        "modal.password": "Passwort",
        "modal.connect": "Verbinden & speichern",
        "modal.pick_folder": "Ordner wählen",
        "modal.pick_up": "↑ Übergeordnet",
        "picker.root": "Stamm",
        "job.fail_diff_unknown": "Abweichungen — Details im Log.",
        "job.pick_none": "— Ordner wählen —",
        "ui.language": "Sprache",
        "ui.scan_running": "Scan läuft…",
        "ui.lan_not_set": "Heimnetz (LAN_SUBNET): nicht gesetzt — in App-Einstellungen z. B. 192.168.2.0/24.",
        "ui.lan_set": "Heimnetz (LAN_SUBNET): {subnet}",
        "ui.lan_extra": " · Zusatz-IPs: {ips}",
        "ui.host_smb": "Host: {host} (SMB)",
        "ui.pick_choose_volume": " / Speicher wählen",
        "ui.pick_volume_path": " / Volume {vol}{path}",
        "ui.manual_ip_ph": "z. B. 192.168.2.200",
        "ui.add_pc_hint": "PC oder anderes NAS per IP (SMB)",
        "err.host_missing": "Host/IP fehlt",
        "err.device_not_found": "Gerät nicht gefunden",
        "err.enter_ip": "Bitte IP eingeben",
        "err.pick_volume_first": "Bitte zuerst Speicher wählen.",
        "err.confirm_remove_device": "Gerät entfernen?",
        "err.smb_share_missing": "SMB-Freigabe fehlt",
        "err.unknown_device_type": "Unbekannter Gerätetyp",
        "probe.no_services": "Kein SMB (445) — trotzdem mit Zugangsdaten versuchen.",
        "browse.pick_volume": "Volume 1/2, USB oder UGOS-Ordner wählen.",
        "scan.invalid_subnet": "Ungültiges LAN_SUBNET ({subnet}): {err}",
        "scan.no_subnet": "Heimnetz nicht konfiguriert — LAN_SUBNET in App-Einstellungen setzen.",
        "scan.none_found": "0 Geräte mit SMB (445){hint}.",
        "scan.found": "{count} Gerät(e) mit SMB gefunden{hint}.",
        "scan.hint_subnet": " (Scan: {subnet})",
        "scan.hint_extra_only": " (nur Zusatz-IPs)",
        "job.new": "Neue Prüfung",
        "job.name": "Name",
        "job.name_ph": "z. B. Volume1 vs USB-Spiegel",
        "job.source": "Referenz (Quelle)",
        "job.dest": "Vergleichen mit (Ziel)",
        "job.pick": "Ordner wählen…",
        "job.save": "Prüfung speichern",
        "job.run": "Jetzt prüfen",
        "job.delete": "Löschen",
        "job.list": "Gespeicherte Prüfungen",
        "job.col_name": "Name",
        "job.col_route": "Referenz → Ziel",
        "job.col_status": "Status",
        "job.col_action": "Aktion",
        "job.col_schedule": "Automatik",
        "job.auto": "Automatisch prüfen",
        "job.interval": "Intervall (Minuten)",
        "job.schedule_off": "—",
        "job.schedule_fmt": "alle {min} min",
        "job.edit": "Bearbeiten",
        "modal.edit_job": "Prüfung bearbeiten",
        "modal.save_changes": "Speichern",
        "notify.title": "Benachrichtigung bei Abweichung",
        "notify.hint": "E-Mail und/oder Telegram — nur bei Fehlschlag, nicht bei OK.",
        "notify.app_hint": "Werte aus den UGOS-App-Einstellungen werden automatisch genutzt. Hier nur ausfüllen, wenn du sie in der Oberfläche überschreiben willst — Speichern ist dann optional.",
        "notify.token_from_app": "•••• aus App-Einstellungen (nicht erneut nötig)",
        "notify.token_saved": "•••• gespeichert (leer lassen = behalten)",
        "notify.pass_from_app": "•••• aus App-Einstellungen",
        "notify.summary_none": "nicht eingerichtet",
        "notify.summary_ready": "bereit",
        "notify.on_fail": "Bei Abweichung benachrichtigen",
        "notify.telegram": "Telegram",
        "notify.telegram_token": "Bot-Token",
        "notify.telegram_chat": "Chat-ID",
        "notify.email": "E-Mail (SMTP)",
        "notify.smtp_host": "SMTP-Server",
        "notify.smtp_port": "Port",
        "notify.smtp_tls": "TLS/STARTTLS",
        "notify.smtp_user": "Benutzer",
        "notify.smtp_pass": "Passwort",
        "notify.email_from": "Absender",
        "notify.email_to": "Empfänger",
        "notify.save": "Einstellungen speichern",
        "notify.test": "Test senden",
        "notify.test_ok": "Test gesendet.",
        "notify.test_fail": "Test fehlgeschlagen — siehe Log.",
        "notify.none_enabled": "Kein Kanal aktiviert.",
        "notify.test_subject": "Backup Verifier — Test",
        "notify.test_body": "Testbenachrichtigung — Backup Verifier ist erreichbar.",
        "notify.fail_subject": "Backup Verifier — Abweichung: {name}",
        "notify.fail_body": "Prüfung: {name}\nRoute: {route}\n\n{message}",
        "job.status_ok": "OK",
        "job.status_fail": "Abweichung",
        "job.status_running": "Läuft…",
        "job.status_never": "Noch nicht geprüft",
        "job.running": "Prüfung läuft…",
        "progress.active_title": "Laufende Prüfungen",
        "progress.none": "Keine aktive Prüfung",
        "progress.starting": "Starte Prüfung…",
        "progress.stats_source": "Referenz analysieren…",
        "progress.stats_dest": "Ziel analysieren…",
        "progress.stats_source_count": "Referenz: {count} Dateien gezählt…",
        "progress.stats_dest_count": "Ziel: {count} Dateien gezählt…",
        "progress.compare_rsync": "Vergleich läuft (rsync)…",
        "progress.compare_rclone": "Vergleich läuft (rclone)…",
        "job.started": "Prüfung gestartet",
        "job.ok": "Keine Abweichungen — Backup stimmt überein.",
        "job.fail_diff": "Abweichungen: {count} Einträge (Details im Log).",
        "job.fail_diff_backup": "Backup unvollständig: {missing} fehlen im Ziel, {differ} abweichend (Details im Log).",
        "job.fail_source_missing": "Referenzordner nicht gefunden.",
        "job.fail_dest_missing": "Zielordner nicht gefunden.",
        "job.fail_timeout": "Zeitüberschreitung.",
        "job.fail_rsync_error": "rsync-Fehler — siehe Log.",
        "log.title": "Log",
        "log.refresh": "Aktualisieren",
        "log.empty": "(leer)",
        "modal.pick": "Ordner wählen",
        "modal.pick_hint": "Speicher wählen → Öffnen → Ordner auswählen.",
        "modal.pick_here": "Diesen Ordner übernehmen",
        "modal.up": "↑ Übergeordnet",
        "modal.cancel": "Abbrechen",
        "picker.open": "Öffnen",
        "picker.select": "Auswählen",
        "picker.whole_volume": "Ganzes Volume",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "Gewählter Ordner (UGOS)",
        "volume.usb_fmt": "USB: {name} ({size})",
        "volume.usb_name_fmt": "USB: {name}",
        "volume.whole": " (gesamt)",
        "volume.storage_fallback": "Speicher {id}",
        "device.this_nas": "Dieses NAS",
        "modal.pick_hint": "Gerät wählen → Speicher/Freigabe → Ordner.",
        "browse.no_subdirs": "Keine Unterordner (diesen Ordner direkt wählen).",
        "picker.open_volume_fmt": "{label} öffnen",
        "err.generic": "Fehler",
        "err.pick_both": "Bitte Referenz und Ziel per Ordnerwahl setzen.",
        "err.same_path": "Referenz und Ziel dürfen nicht identisch sein.",
        "err.job_not_found": "Prüfung nicht gefunden",
        "err.job_running": "Prüfung läuft bereits",
        "err.cannot_delete": "Löschen nicht möglich (läuft gerade)",
        "err.usb_not_mounted": "USB {id} nicht gemountet",
        "err.no_storage": "Kein Speicher verfügbar",
        "job.default_name": "Prüfung",
        "companion": "Desktop-Begleiter:",
    },
    "en": {
        "app.title": "Backup Verifier",
        "app.intro": "Compare two folders — this NAS, USB, PC share (SMB), or another NAS. Read-only, nothing is copied or deleted.",
        "app.readonly": "NAS paths are read-only; SMB/PC is read via rclone check only.",
        "devices.network": "Devices on the network",
        "devices.scan": "Scan network",
        "devices.scan_loading": "Home network: loading…",
        "devices.add_ip_btn": "Add…",
        "devices.saved": "Saved devices",
        "devices.host": "Host",
        "devices.services": "Services",
        "devices.name": "Name",
        "devices.type": "Type",
        "devices.remove": "Remove",
        "devices.add": "Add",
        "modal.add_device": "Add device (SMB)",
        "modal.display_name": "Display name",
        "modal.user": "User (SMB)",
        "modal.password": "Password",
        "modal.connect": "Connect & save",
        "modal.pick_folder": "Pick folder",
        "modal.pick_up": "↑ Parent",
        "picker.root": "Root",
        "job.fail_diff_unknown": "Differences — see log.",
        "job.pick_none": "— pick folder —",
        "ui.language": "Language",
        "ui.scan_running": "Scanning…",
        "ui.lan_not_set": "Home network (LAN_SUBNET) not set — configure in app settings.",
        "ui.lan_set": "Home network (LAN_SUBNET): {subnet}",
        "ui.lan_extra": " · Extra IPs: {ips}",
        "ui.host_smb": "Host: {host} (SMB)",
        "ui.pick_choose_volume": " / pick storage",
        "ui.pick_volume_path": " / Volume {vol}{path}",
        "ui.manual_ip_ph": "e.g. 192.168.2.200",
        "ui.add_pc_hint": "Add PC or other NAS by IP (SMB)",
        "err.host_missing": "Host/IP missing",
        "err.device_not_found": "Device not found",
        "err.enter_ip": "Please enter an IP",
        "err.pick_volume_first": "Pick a storage volume first.",
        "err.confirm_remove_device": "Remove device?",
        "err.smb_share_missing": "SMB share missing",
        "err.unknown_device_type": "Unknown device type",
        "probe.no_services": "No SMB (445) — try credentials anyway.",
        "browse.pick_volume": "Pick Volume 1/2, USB, or UGOS folder.",
        "scan.invalid_subnet": "Invalid LAN_SUBNET ({subnet}): {err}",
        "scan.no_subnet": "Home network not configured — set LAN_SUBNET in app settings.",
        "scan.none_found": "0 devices with SMB (445){hint}.",
        "scan.found": "{count} device(s) with SMB found{hint}.",
        "scan.hint_subnet": " (scan: {subnet})",
        "scan.hint_extra_only": " (extra IPs only)",
        "job.new": "New check",
        "job.name": "Name",
        "job.name_ph": "e.g. Volume1 vs USB mirror",
        "job.source": "Reference (source)",
        "job.dest": "Compare with (destination)",
        "job.pick": "Pick folder…",
        "job.save": "Save check",
        "job.run": "Verify now",
        "job.delete": "Delete",
        "job.list": "Saved checks",
        "job.col_name": "Name",
        "job.col_route": "Reference → target",
        "job.col_status": "Status",
        "job.col_action": "Action",
        "job.col_schedule": "Schedule",
        "job.auto": "Auto-verify",
        "job.interval": "Interval (minutes)",
        "job.schedule_off": "—",
        "job.schedule_fmt": "every {min} min",
        "job.edit": "Edit",
        "modal.edit_job": "Edit check",
        "modal.save_changes": "Save",
        "notify.title": "Notify on mismatch",
        "notify.hint": "Email and/or Telegram — on failure only, not on OK.",
        "notify.app_hint": "Values from UGOS app settings are used automatically. Fill in here only to override in the UI — saving is optional.",
        "notify.token_from_app": "•••• from app settings (no re-entry needed)",
        "notify.token_saved": "•••• saved (leave blank to keep)",
        "notify.pass_from_app": "•••• from app settings",
        "notify.summary_none": "not configured",
        "notify.summary_ready": "ready",
        "notify.on_fail": "Notify on mismatch",
        "notify.telegram": "Telegram",
        "notify.telegram_token": "Bot token",
        "notify.telegram_chat": "Chat ID",
        "notify.email": "Email (SMTP)",
        "notify.smtp_host": "SMTP server",
        "notify.smtp_port": "Port",
        "notify.smtp_tls": "TLS/STARTTLS",
        "notify.smtp_user": "User",
        "notify.smtp_pass": "Password",
        "notify.email_from": "From",
        "notify.email_to": "To",
        "notify.save": "Save settings",
        "notify.test": "Send test",
        "notify.test_ok": "Test sent.",
        "notify.test_fail": "Test failed — see log.",
        "notify.none_enabled": "No channel enabled.",
        "notify.test_subject": "Backup Verifier — test",
        "notify.test_body": "Test notification — Backup Verifier is reachable.",
        "notify.fail_subject": "Backup Verifier — mismatch: {name}",
        "notify.fail_body": "Check: {name}\nRoute: {route}\n\n{message}",
        "job.status_ok": "OK",
        "job.status_fail": "Mismatch",
        "job.status_running": "Running…",
        "job.status_never": "Not run yet",
        "job.running": "Verification running…",
        "progress.active_title": "Running checks",
        "progress.none": "No active check",
        "progress.starting": "Starting check…",
        "progress.stats_source": "Analyzing reference…",
        "progress.stats_dest": "Analyzing target…",
        "progress.stats_source_count": "Reference: {count} files counted…",
        "progress.stats_dest_count": "Target: {count} files counted…",
        "progress.compare_rsync": "Comparing (rsync)…",
        "progress.compare_rclone": "Comparing (rclone)…",
        "job.started": "Verification started",
        "job.ok": "No differences — backup matches.",
        "job.fail_diff": "Differences: {count} items (see log).",
        "job.fail_diff_backup": "Backup incomplete: {missing} missing on target, {differ} differ (see log).",
        "job.fail_source_missing": "Reference folder not found.",
        "job.fail_dest_missing": "Target folder not found.",
        "job.fail_timeout": "Timed out.",
        "job.fail_rsync_error": "rsync error — see log.",
        "log.title": "Log",
        "log.refresh": "Refresh",
        "log.empty": "(empty)",
        "modal.pick": "Pick folder",
        "modal.pick_hint": "Choose storage → Open → select folder.",
        "modal.pick_here": "Use this folder",
        "modal.up": "↑ Parent",
        "modal.cancel": "Cancel",
        "picker.open": "Open",
        "picker.select": "Select",
        "picker.whole_volume": "Whole volume",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "Selected folder (UGOS)",
        "volume.usb_fmt": "USB: {name} ({size})",
        "volume.usb_name_fmt": "USB: {name}",
        "volume.whole": " (whole)",
        "volume.storage_fallback": "Storage {id}",
        "device.this_nas": "This NAS",
        "modal.pick_hint": "Choose device → storage/share → folder.",
        "browse.no_subdirs": "No subfolders (select this folder directly).",
        "picker.open_volume_fmt": "Open {label}",
        "err.generic": "Error",
        "err.pick_both": "Set reference and target via folder picker.",
        "err.same_path": "Reference and target must differ.",
        "err.job_not_found": "Check not found",
        "err.job_running": "Check already running",
        "err.cannot_delete": "Cannot delete while running",
        "err.usb_not_mounted": "USB {id} not mounted",
        "err.no_storage": "No storage available",
        "job.default_name": "Check",
        "companion": "Desktop companion:",
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
    else:
        if hasattr(_thread_lang, "value"):
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
