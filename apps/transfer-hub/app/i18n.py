# -*- coding: utf-8 -*-
"""UI languages: German if NAS/browser locale is German, otherwise English."""
from __future__ import annotations

import os
from typing import Any

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "app.title": "Transfer Hub",
        "app.intro": "In den UGOS-App-Einstellungen einen Unterordner wählen (UGOS erlaubt oft kein Bestätigen auf „Freigegebener Ordner“). Hier: Volume 1/2, USB am NAS oder UGOS-Ordner → Auswählen.",
        "devices.network": "Geräte im Netz",
        "devices.scan": "Netzwerk scannen",
        "devices.scan_loading": "Heimnetz: wird geladen…",
        "devices.add_ip": "Gerät per IP hinzufügen",
        "devices.add_ip_btn": "Hinzufügen…",
        "devices.saved": "Gespeicherte Geräte",
        "devices.host": "Host",
        "devices.services": "Dienste",
        "devices.name": "Name",
        "devices.type": "Typ",
        "devices.remove": "Entfernen",
        "devices.add": "Hinzufügen",
        "device.this_nas": "Dieses NAS",
        "profile.new": "Neues Übertragungsprofil",
        "profile.one_way": "Eine Richtung. Für die Gegenrichtung ein zweites Profil anlegen.",
        "profile.name": "Name",
        "profile.name_ph": "z. B. PC-Inbox → NAS-Archiv",
        "profile.source": "Quelle",
        "profile.dest": "Ziel",
        "profile.pick_folder": "Ordner wählen…",
        "profile.pick_none": "— Ordner wählen —",
        "profile.auto": "Automatisch neue/geänderte Dateien übertragen",
        "profile.move_source": "Quelle nach erfolgreicher Übertragung leeren (Verschieben)",
        "profile.move_hint": "Gelöscht wird nur nach erfolgreicher Kopie und Ziel-Prüfung. Erst mit Kopier-Profil testen! PC/SMB: Schreibrecht nötig. Nicht mit Auto-Sync kombinierbar.",
        "profile.interval": "Intervall",
        "profile.schedule_type": "Automatik",
        "profile.schedule_always_opt": "Rund um die Uhr (NAS immer erreichbar)",
        "profile.schedule_window_opt": "Zeitfenster (z. B. PC-Backup)",
        "profile.window_start": "Von",
        "profile.window_end": "Bis",
        "profile.schedule_hint": "Zeitfenster: nur zwischen Von und Bis wird versucht (z. B. 15:30–22:00 alle 30 min). PC aus → kurzer Check (~2 s), kein voller SMB-Versuch.",
        "profile.schedule_window": "{start}–{end}, alle {min} min",
        "profile.schedule_always": "24/7, alle {min} min",
        "profile.save": "Profil speichern",
        "profiles.title": "Profile",
        "profiles.col_route": "Quelle → Ziel",
        "profiles.col_mode": "Modus",
        "profiles.mode_move": "Verschieben",
        "profiles.col_status": "Status",
        "profiles.now": "Jetzt",
        "profiles.edit": "Bearbeiten",
        "profiles.delete": "Löschen",
        "log.title": "Log",
        "log.refresh": "Aktualisieren",
        "log.empty": "(leer)",
        "modal.add_device": "Gerät hinzufügen",
        "modal.display_name": "Anzeigename",
        "modal.user": "Benutzer (SMB)",
        "modal.password": "Passwort",
        "modal.connect": "Verbinden & speichern",
        "modal.cancel": "Abbrechen",
        "modal.edit_profile": "Profil bearbeiten",
        "modal.save_changes": "Änderungen speichern",
        "modal.pick_folder": "Ordner wählen",
        "modal.pick_hint": "Zuerst Speicher wählen → Öffnen → neben Ordner Auswählen. „Ganzes Volume“ nur für alles auf einmal.",
        "modal.pick_here": "Diesen Ordner übernehmen",
        "modal.pick_up": "↑ Übergeordnet",
        "picker.open": "Öffnen",
        "picker.select": "Auswählen",
        "picker.whole_volume": "Ganzes Volume",
        "picker.root": "Stamm",
        "picker.choose_volume": " / Speicher wählen",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "Gewählter Ordner (UGOS)",
        "volume.usb_fmt": "USB: {name} ({size})",
        "volume.usb_name_fmt": "USB: {name}",
        "volume.whole": " (gesamt)",
        "volume.open": " öffnen",
        "err.generic": "Fehler",
        "err.host_missing": "Host/IP fehlt",
        "err.device_not_found": "Gerät nicht gefunden",
        "err.profile_not_found": "Profil nicht gefunden",
        "err.cannot_delete": "Kann nicht gelöscht werden",
        "err.pick_source_dest": "Bitte Quelle und Ziel per „Ordner wählen“ setzen.",
        "err.pick_both": "Bitte Quelle und Ziel setzen.",
        "err.enter_ip": "Bitte IP eingeben (z. B. 192.168.2.200)",
        "err.pick_volume_first": "Bitte zuerst einen Speicher öffnen oder „Ganzes Volume“ wählen.",
        "err.confirm_remove_device": "Gerät entfernen?",
        "err.confirm_delete_profile": "Profil löschen?",
        "transfer.done": "Übertragung abgeschlossen",
        "transfer.move_done": "Verschieben abgeschlossen — übertragene Dateien an der Quelle entfernt",
        "transfer.move_cleanup_failed": "Kopie OK, aber Quelle konnte nicht geleert werden: {detail}",
        "transfer.verify_failed": "Ziel unvollständig — Übertragung nicht bestätigt: {detail}",
        "transfer.partial_ok": "Übertragung abgeschlossen ({count} System-/Docker-Dateien übersprungen). Nicht ganze Docker-Verzeichnisse wählen.",
        "profile.default_name": "Profil",
        "err.pick_via_ui": "Quelle und Ziel per Auswahl setzen",
        "err.pick_devices": "Gerät für Quelle/Ziel wählen",
        "err.same_endpoints": "Quelle und Ziel dürfen nicht identisch sein",
        "err.conflict_auto": "Konflikt mit Auto-Sync „{name}“ (entgegengesetzte Richtung).",
        "err.move_with_auto": "Verschieben und Auto-Sync können nicht zusammen aktiviert werden.",
        "err.unknown_device_type": "Unbekannter Gerätetyp",
        "err.no_storage": "Kein NAS-Speicher eingebunden.",
        "err.usb_not_mounted": "USB-Speicher nicht verfügbar ({id}). Stick eingesteckt? App neu starten, wenn er gerade angeschlossen wurde.",
        "err.smb_share_missing": "SMB-Freigabe fehlt",
        "err.smb_failed": "SMB-Verbindung fehlgeschlagen",
        "smb.connected": "Verbunden",
        "probe.no_services": "Kein SMB (445) oder SSH (22) — trotzdem mit Zugangsdaten versuchen.",
        "browse.no_subdirs": "Keine Unterordner sichtbar. Anderen Speicher probieren (z. B. Volume 1). Beim UGOS-Ordner: in den App-Einstellungen einen Unterordner wählen, der über oder neben dem Ziel liegt.",
        "browse.pick_volume": "Volume 1 / Volume 2 = gesamtes Volume. USB-Einträge = am NAS eingesteckte Platte/Stick (typisch /mnt/@usb/…). „Gewählter Ordner (UGOS)“ = Ordner aus den App-Einstellungen.",
        "picker.open_volume_fmt": "{label} öffnen",
        "scan.invalid_subnet": "Ungültiges LAN_SUBNET ({subnet}): {err}",
        "scan.no_subnet": "Heimnetz nicht konfiguriert: In den App-Einstellungen LAN_SUBNET setzen (bei dir z. B. 192.168.2.0/24), App neu starten. Oder PC per IP unten hinzufügen.",
        "scan.none_found": "0 Gerät(e) mit offenem SMB (445) oder SSH (22){hint}. PC eingeschaltet? Windows-Freigabe aktiv? Oder IP manuell hinzufügen (z. B. 192.168.2.200).",
        "scan.found": "{count} Gerät(e) mit SMB/SSH gefunden{hint}.",
        "scan.hint_subnet": " (Scan: {subnet})",
        "scan.hint_extra_only": " (nur Zusatz-IPs)",
        "ui.scan_running": "Scan läuft…",
        "ui.lan_not_set": "Heimnetz (LAN_SUBNET): nicht gesetzt — in App-Einstellungen z. B. 192.168.2.0/24 eintragen und App neu starten.",
        "ui.lan_set": "Heimnetz (LAN_SUBNET): {subnet}",
        "ui.lan_extra": " · Zusatz-IPs: {ips}",
        "ui.host_smb": "Host: {host} (SMB)",
        "ui.pick_choose_volume": " / Speicher wählen",
        "ui.pick_volume_path": " / Volume {vol}{path}",
        "ui.manual_ip_ph": "z. B. 192.168.2.200",
        "ui.add_pc_hint": "PC per IP hinzufügen (wenn Scan leer bleibt)",
        "volume.storage_fallback": "Speicher {id}",
        "ui.language": "Sprache",
        "footer.nas_admin": "Mehr NAS-Funktionen auf dem PC:",
        "footer.nas_admin_link": "Ugreen NAS Admin",
        "jobs.active_title": "Aktive Übertragungen",
        "jobs.none": "Keine aktiven Übertragungen.",
        "jobs.started": "Übertragung gestartet.",
        "jobs.already_running": "Läuft bereits.",
        "jobs.running": "Läuft…",
        "jobs.done": "Abgeschlossen",
        "jobs.failed": "Fehler",
        "jobs.skip_offline": "Übersprungen — {host} nicht erreichbar (SMB).",
        "err.source_not_found": "Quelle nicht gefunden: {path}",
    },
    "en": {
        "app.title": "Transfer Hub",
        "app.intro": "In UGOS app settings, pick a subfolder (UGOS often cannot confirm at shared-folder root). Here: Volume 1/2, USB on NAS, or UGOS folder → Select.",
        "devices.network": "Devices on network",
        "devices.scan": "Scan network",
        "devices.scan_loading": "Home network: loading…",
        "devices.add_ip": "Add device by IP",
        "devices.add_ip_btn": "Add…",
        "devices.saved": "Saved devices",
        "devices.host": "Host",
        "devices.services": "Services",
        "devices.name": "Name",
        "devices.type": "Type",
        "devices.remove": "Remove",
        "devices.add": "Add",
        "device.this_nas": "This NAS",
        "profile.new": "New transfer profile",
        "profile.one_way": "One direction only. Create a second profile for the reverse direction.",
        "profile.name": "Name",
        "profile.name_ph": "e.g. PC-Inbox → NAS-Archive",
        "profile.source": "Source",
        "profile.dest": "Destination",
        "profile.pick_folder": "Choose folder…",
        "profile.pick_none": "— Choose folder —",
        "profile.auto": "Automatically transfer new/changed files",
        "profile.move_source": "Empty source after successful transfer (move)",
        "profile.move_hint": "Source removed only after copy and destination verification. Test with copy-only profile first! PC/SMB: write permission required. Cannot combine with auto-sync.",
        "profile.interval": "Interval",
        "profile.schedule_type": "Automation",
        "profile.schedule_always_opt": "Around the clock (NAS always reachable)",
        "profile.schedule_window_opt": "Time window (e.g. PC backup)",
        "profile.window_start": "From",
        "profile.window_end": "Until",
        "profile.schedule_hint": "Time window: sync attempts only between From and Until (e.g. 15:30–22:00 every 30 min). PC off → quick check (~2 s), no full SMB attempt.",
        "profile.schedule_window": "{start}–{end}, every {min} min",
        "profile.schedule_always": "24/7, every {min} min",
        "profile.save": "Save profile",
        "profiles.title": "Profiles",
        "profiles.col_route": "Source → Destination",
        "profiles.col_mode": "Mode",
        "profiles.mode_move": "Move",
        "profiles.col_status": "Status",
        "profiles.now": "Run now",
        "profiles.edit": "Edit",
        "profiles.delete": "Delete",
        "log.title": "Log",
        "log.refresh": "Refresh",
        "log.empty": "(empty)",
        "modal.add_device": "Add device",
        "modal.display_name": "Display name",
        "modal.user": "User (SMB)",
        "modal.password": "Password",
        "modal.connect": "Connect & save",
        "modal.cancel": "Cancel",
        "modal.edit_profile": "Edit profile",
        "modal.save_changes": "Save changes",
        "modal.pick_folder": "Choose folder",
        "modal.pick_hint": "Pick storage → Open → Select next to target folder. “Whole volume” only if you mean everything.",
        "modal.pick_here": "Use this folder",
        "modal.pick_up": "↑ Up",
        "picker.open": "Open",
        "picker.select": "Select",
        "picker.whole_volume": "Whole volume",
        "picker.root": "Root",
        "picker.choose_volume": " / Choose storage",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "UGOS folder",
        "volume.usb_fmt": "USB: {name} ({size})",
        "volume.usb_name_fmt": "USB: {name}",
        "volume.whole": " (entire)",
        "volume.open": " open",
        "err.generic": "Error",
        "err.host_missing": "Host/IP missing",
        "err.device_not_found": "Device not found",
        "err.profile_not_found": "Profile not found",
        "err.cannot_delete": "Cannot delete",
        "err.pick_source_dest": "Please set source and destination via “Choose folder”.",
        "err.pick_both": "Please set source and destination.",
        "err.enter_ip": "Please enter an IP (e.g. 192.168.2.200)",
        "err.pick_volume_first": "Please open a storage first or choose “Whole volume”.",
        "err.confirm_remove_device": "Remove device?",
        "err.confirm_delete_profile": "Delete profile?",
        "transfer.done": "Transfer completed",
        "transfer.move_done": "Move completed — transferred files removed at source",
        "transfer.move_cleanup_failed": "Copy OK but source cleanup failed: {detail}",
        "transfer.verify_failed": "Destination incomplete — transfer not confirmed: {detail}",
        "transfer.partial_ok": "Transfer completed ({count} system/Docker files skipped). Avoid syncing whole Docker folders.",
        "profile.default_name": "Profile",
        "err.pick_via_ui": "Set source and destination via the picker",
        "err.pick_devices": "Choose devices for source and destination",
        "err.same_endpoints": "Source and destination must differ",
        "err.conflict_auto": "Conflict with auto-sync profile “{name}” (opposite direction).",
        "err.move_with_auto": "Move and auto-sync cannot be enabled together.",
        "err.unknown_device_type": "Unknown device type",
        "err.no_storage": "No NAS storage mounted.",
        "err.usb_not_mounted": "USB storage not available ({id}). Drive plugged in? Restart the app if you just connected it.",
        "err.smb_share_missing": "SMB share missing",
        "err.smb_failed": "SMB connection failed",
        "smb.connected": "Connected",
        "probe.no_services": "No SMB (445) or SSH (22) — you can still try with credentials.",
        "browse.no_subdirs": "No subfolders visible. Try another storage (e.g. Volume 1). For UGOS folder: pick a subfolder in app settings above or beside the target.",
        "browse.pick_volume": "Volume 1 / Volume 2 = entire volume. USB entries = drive/stick on this NAS (often /mnt/@usb/…). “UGOS folder” = folder from app settings.",
        "picker.open_volume_fmt": "Open {label}",
        "scan.invalid_subnet": "Invalid LAN_SUBNET ({subnet}): {err}",
        "scan.no_subnet": "Home network not configured: set LAN_SUBNET in app settings (e.g. 192.168.2.0/24) and restart the app. Or add a PC by IP below.",
        "scan.none_found": "0 device(s) with SMB (445) or SSH (22) open{hint}. PC on? Windows sharing enabled? Or add IP manually (e.g. 192.168.2.200).",
        "scan.found": "{count} device(s) with SMB/SSH found{hint}.",
        "scan.hint_subnet": " (scan: {subnet})",
        "scan.hint_extra_only": " (extra IPs only)",
        "ui.scan_running": "Scanning…",
        "ui.lan_not_set": "Home network (LAN_SUBNET): not set — enter e.g. 192.168.2.0/24 in app settings and restart.",
        "ui.lan_set": "Home network (LAN_SUBNET): {subnet}",
        "ui.lan_extra": " · Extra IPs: {ips}",
        "ui.host_smb": "Host: {host} (SMB)",
        "ui.pick_choose_volume": " / Choose storage",
        "ui.pick_volume_path": " / Volume {vol}{path}",
        "ui.manual_ip_ph": "e.g. 192.168.2.200",
        "ui.add_pc_hint": "Add PC by IP (if scan stays empty)",
        "volume.storage_fallback": "Storage {id}",
        "ui.language": "Language",
        "footer.nas_admin": "More NAS tools on your PC:",
        "footer.nas_admin_link": "Ugreen NAS Admin",
        "jobs.active_title": "Active transfers",
        "jobs.none": "No active transfers.",
        "jobs.started": "Transfer started.",
        "jobs.already_running": "Already running.",
        "jobs.running": "Running…",
        "jobs.done": "Completed",
        "jobs.failed": "Failed",
        "jobs.skip_offline": "Skipped — {host} unreachable (SMB).",
        "err.source_not_found": "Source not found: {path}",
    },
}

LANG_COOKIE = "transfer_hub_lang"


def normalize_lang(code: str | None) -> str | None:
    if not code:
        return None
    token = code.strip().lower().split("-")[0].split("_")[0]
    if token in ("de", "en"):
        return token
    return None


def resolve_lang(
    accept_language: str | None = None,
    *,
    query_lang: str | None = None,
    cookie_lang: str | None = None,
) -> str:
    """User choice (query/cookie) beats env, NAS locale, then browser; default en."""
    for raw in (query_lang, cookie_lang):
        picked = normalize_lang(raw)
        if picked:
            return picked
    forced = os.environ.get("TRANSFER_HUB_LANG", "").strip().lower()
    if forced in ("de", "en"):
        return forced
    for var in ("LC_ALL", "LANG", "LC_MESSAGES"):
        val = (os.environ.get(var) or "").strip().lower()
        if val.startswith("de"):
            return "de"
    if accept_language:
        for part in accept_language.split(","):
            token = part.split(";")[0].strip().lower()
            if token.startswith("de"):
                return "de"
            if token.startswith("en"):
                return "en"
    return "en"


def lang_from_request(req) -> str:
    return resolve_lang(
        req.headers.get("Accept-Language"),
        query_lang=req.args.get("lang"),
        cookie_lang=req.cookies.get(LANG_COOKIE),
    )


def t(key: str, lang: str | None = None, **fmt: Any) -> str:
    lng = lang or "en"
    s = STRINGS.get(lng, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))
    if fmt:
        try:
            return s.format(**fmt)
        except (KeyError, ValueError):
            return s
    return s


def bundle(lang: str) -> dict[str, str]:
    return dict(STRINGS.get(lang, STRINGS["en"]))


def get_lang() -> str:
    try:
        from flask import g

        return getattr(g, "lang", resolve_lang())
    except RuntimeError:
        return resolve_lang()
