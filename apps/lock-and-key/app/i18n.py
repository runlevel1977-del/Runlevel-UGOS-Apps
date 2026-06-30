# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
from typing import Any

LANG_COOKIE = "lk_lang"
_thread_lang = threading.local()

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "app.title": "Lock & Key",
        "app.intro": "Ordner auf dem NAS verschlüsseln — öffnen nur mit Schlüsseldatei vom USB-Stick am NAS.",
        "ui.language": "Sprache",
        "companion": "Desktop-Begleiter:",
        "vaults.title": "Tresore",
        "vaults.empty": "Noch kein Tresor angelegt.",
        "vaults.col_name": "Name",
        "vaults.col_path": "Ordner",
        "vaults.col_status": "Status",
        "vaults.col_usb": "USB-Bindung",
        "vaults.col_files": "Dateien",
        "vaults.col_actions": "Aktion",
        "vaults.delete": "Löschen",
        "vaults.delete_confirm": "Tresor „{name}“ aus der Liste entfernen?",
        "vaults.delete_locked_confirm": "Tresor „{name}“ ist GESPERRT. Nur der Listeneintrag wird gelöscht — der verschlüsselte Ordner bleibt auf dem NAS. Schlüsseldatei aufbewahren! Fortfahren?",
        "vaults.status_locked": "gesperrt",
        "vaults.status_unlocked": "offen",
        "vaults.status_locking": "wird gesperrt …",
        "vaults.bind_yes": "Label/Seriennr.",
        "vaults.bind_no": "nur Schlüsseldatei",
        "vaults.key_pw_yes": "passwortgeschützt",
        "vaults.key_pw_no": "ohne Passwort",
        "create.title": "Neuen Tresor sperren",
        "create.name": "Name",
        "create.volume": "Volume",
        "create.volume_hint": "Für NAS-Ordner in der Dateien-App: Volume 1 oder Volume 2 wählen — nicht „UGOS-Auswahl“.",
        "create.files_ready": "{n} Dateien werden verschlüsselt (inkl. Unterordner)",
        "create.folder": "Ordner",
        "create.subfolder": "Unterordner öffnen",
        "create.browse_here": "Aktueller Ort",
        "create.browse_sealed": "bereits gesperrt — {enc} verschlüsselt, {open} offen",
        "create.browse_open": "{open} offene Dateien, {enc} bereits .lkenc",
        "create.already_sealed": "Dieser Ordner ist bereits gesperrt (Tresor „{name}“). Zum erneuten Sperren zuerst öffnen oder einen anderen Ordner wählen.",
        "create.selected": "Ausgewählter Tresor-Ordner",
        "create.select_folder": "Diesen Ordner auswählen",
        "create.not_selected": "Noch kein Ordner gewählt — hierhin navigieren, dann „Diesen Ordner auswählen“.",
        "create.err_no_folder": "Bitte zuerst einen Ordner auswählen.",
        "create.bind_usb": "Schlüssel auf USB-Stick schreiben (Stick zuordnen)",
        "create.bind_hint": "Nach erfolgreichem Sperren wird der gewählte Stick formatiert — nur die Schlüsseldatei bleibt darauf. Ohne Haken: Schlüssel nur per Download.",
        "create.seal": "Ordner sperren",
        "create.key_password": "Schlüsseldatei mit Passwort schützen (optional)",
        "create.key_password_hint": "Mindestens 8 Zeichen. Das NAS speichert das Passwort nicht — Download und USB-Stick brauchen dasselbe Passwort zum Öffnen.",
        "create.key_password_field": "Passwort für Schlüsseldatei",
        "create.key_password_confirm": "Passwort bestätigen",
        "create.err_password_short": "Passwort mindestens 8 Zeichen.",
        "create.err_password_mismatch": "Passwörter stimmen nicht überein.",
        "create.pick": "Ordner wählen …",
        "unlock.title": "Öffnen / wieder sperren",
        "unlock.pick": "Tresor",
        "unlock.from_usb": "Mit USB am NAS öffnen",
        "unlock.upload_key": "Schlüsseldatei hochladen",
        "unlock.key_password": "Passwort für Schlüsseldatei",
        "unlock.key_password_hint": "Nur nötig, wenn beim Sperren ein Passwort gesetzt wurde.",
        "unlock.run": "Öffnen",
        "relock.run": "Wieder sperren",
        "usb.title": "USB am NAS",
        "usb.empty": "Kein USB-Stick eingesteckt.",
        "usb.write_key": "Stick formatieren & Schlüssel schreiben",
        "usb.format_confirm": "Der USB-Stick wird vollständig gelöscht/formatiert. Alle Daten auf dem Stick gehen verloren. Fortfahren?",
        "usb.one_stick": "Pro Stick nur ein Tresor — alte Schlüssel werden entfernt.",
        "usb.pick": "USB-Stick",
        "usb.pick_hint": "Bei mehreren Sticks am NAS den gewünschten Schlüssel-Stick wählen.",
        "usb.none": "Kein Stick eingesteckt",
        "usb.key_written": "Schlüssel auf Stick geschrieben: {path} — dieser Stick ist jetzt diesem Tresor zugeordnet.",
        "usb.browser_alert_hint": "Hinweis: Die Browser-Meldung mit „Weitere Aufforderungen verbieten“ betrifft nur Pop-ups vom Browser — nicht den Stick-Schutz (der läuft automatisch über Seriennummer + Formatierung).",
        "log.title": "Log",
        "job.running": "Aufgabe läuft …",
        "job.writing_key": "Schlüssel wird auf USB-Stick geschrieben …",
        "job.done": "Fertig",
        "job.error": "Fehler",
        "job.files_encrypted": "Dateien verschlüsselt",
        "job.files_decrypted": "Dateien entschlüsselt",
        "job.verify_ok": "Integritätsprüfung OK ({n} Dateien)",
        "job.verify_ok_legacy": "Entschlüsselung OK ({n} Dateien — älterer Tresor ohne Prüfmanifest)",
        "job.verify_fail": "Integritätsprüfung fehlgeschlagen",
        "job.seal_failed_safe": "Sperren abgebrochen — alle Originaldateien sind unverändert.",
        "job.unlock_failed_safe": "Entsperren abgebrochen — alle verschlüsselten Dateien sind unverändert.",
        "warn.seal_result": "Nach dem Sperren: Originaldateien sind weg, stattdessen Dateien mit Endung .lkenc. Der Ordner bleibt im UGOS-Dateimanager sichtbar.",
        "warn.usb_remove": "USB abziehen versteckt den Ordner nicht — ohne Schlüssel sind die .lkenc-Dateien nur unlesbar.",
        "warn.no_recovery": "Ohne Schlüsseldatei gibt es keine Wiederherstellung.",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "UGOS-Auswahl",
        "volume.storage_fallback": "Speicher {id}",
        "volume.usb_fmt": "USB: {name} ({size})",
        "volume.usb_name_fmt": "USB: {name}",
        "err.no_storage": "Kein Speicher verfügbar",
        "err.usb_not_mounted": "USB {id} nicht gemountet",
        "err.system_folder": "Systemordner (Name enthält @) können nicht verschlüsselt werden.",
    },
    "en": {
        "app.title": "Lock & Key",
        "app.intro": "Encrypt a folder on the NAS — unlock only with the key file from a USB stick on the NAS.",
        "ui.language": "Language",
        "companion": "Desktop companion:",
        "vaults.title": "Vaults",
        "vaults.empty": "No vaults yet.",
        "vaults.col_name": "Name",
        "vaults.col_path": "Folder",
        "vaults.col_status": "Status",
        "vaults.col_usb": "USB binding",
        "vaults.col_files": "Files",
        "vaults.col_actions": "Action",
        "vaults.delete": "Delete",
        "vaults.delete_confirm": "Remove vault “{name}” from the list?",
        "vaults.delete_locked_confirm": "Vault “{name}” is LOCKED. Only the list entry is removed — encrypted files stay on the NAS. Keep your key file! Continue?",
        "vaults.status_locked": "locked",
        "vaults.status_unlocked": "unlocked",
        "vaults.status_locking": "locking …",
        "vaults.bind_yes": "label/serial",
        "vaults.bind_no": "key file only",
        "vaults.key_pw_yes": "password-protected",
        "vaults.key_pw_no": "no password",
        "create.title": "Seal a new vault",
        "create.name": "Name",
        "create.volume": "Volume",
        "create.volume_hint": "For folders in the UGOS Files app: pick Volume 1 or Volume 2 — not “UGOS selection”.",
        "create.files_ready": "{n} files will be encrypted (including subfolders)",
        "create.folder": "Folder",
        "create.subfolder": "Open subfolder",
        "create.browse_here": "Current location",
        "create.browse_sealed": "already sealed — {enc} encrypted, {open} open",
        "create.browse_open": "{open} open files, {enc} already .lkenc",
        "create.already_sealed": "This folder is already sealed (vault “{name}”). Unlock it first or pick another folder.",
        "create.selected": "Selected vault folder",
        "create.select_folder": "Select this folder",
        "create.not_selected": "No folder selected yet — browse here, then click “Select this folder”.",
        "create.err_no_folder": "Please select a folder first.",
        "create.bind_usb": "Write key to USB stick (bind stick)",
        "create.bind_hint": "After a successful seal, the selected stick is formatted — only the key file remains. Unchecked: download key only.",
        "create.seal": "Seal folder",
        "create.key_password": "Password-protect key file (optional)",
        "create.key_password_hint": "At least 8 characters. The NAS never stores the password — download and USB stick need the same password to unlock.",
        "create.key_password_field": "Key file password",
        "create.key_password_confirm": "Confirm password",
        "create.err_password_short": "Password must be at least 8 characters.",
        "create.err_password_mismatch": "Passwords do not match.",
        "create.pick": "Pick folder …",
        "unlock.title": "Unlock / re-lock",
        "unlock.pick": "Vault",
        "unlock.from_usb": "Unlock with NAS USB",
        "unlock.upload_key": "Upload key file",
        "unlock.key_password": "Key file password",
        "unlock.key_password_hint": "Only required if you set a password when sealing.",
        "unlock.run": "Unlock",
        "relock.run": "Re-lock",
        "usb.title": "USB on NAS",
        "usb.empty": "No USB stick mounted.",
        "usb.write_key": "Format stick & write key",
        "usb.format_confirm": "The USB stick will be fully erased/formatted. All data on the stick will be lost. Continue?",
        "usb.one_stick": "One stick per vault — old keys are removed.",
        "usb.pick": "USB stick",
        "usb.pick_hint": "When several sticks are plugged in, pick the one that holds the key file.",
        "usb.none": "No stick mounted",
        "usb.key_written": "Key written to stick: {path} — this stick is now bound to this vault.",
        "usb.browser_alert_hint": "Note: The browser’s “prevent further prompts” checkbox only blocks pop-ups — not stick protection (that is automatic via serial + format).",
        "log.title": "Log",
        "job.running": "Job running …",
        "job.writing_key": "Writing key to USB stick …",
        "job.done": "Done",
        "job.error": "Error",
        "job.files_encrypted": "files encrypted",
        "job.files_decrypted": "files decrypted",
        "job.verify_ok": "integrity check OK ({n} files)",
        "job.verify_ok_legacy": "decryption OK ({n} files — older vault without checksum manifest)",
        "job.verify_fail": "integrity check failed",
        "job.seal_failed_safe": "Seal aborted — all original files are unchanged.",
        "job.unlock_failed_safe": "Unlock aborted — all encrypted files are unchanged.",
        "warn.seal_result": "After sealing: originals are gone, replaced by .lkenc files. The folder stays visible in the UGOS file manager.",
        "warn.usb_remove": "Removing the USB stick does not hide the folder — without the key, .lkenc files are unreadable only.",
        "warn.no_recovery": "Without the key file there is no recovery.",
        "volume.1": "Volume 1",
        "volume.2": "Volume 2",
        "volume.ugos": "UGOS selection",
        "volume.storage_fallback": "Storage {id}",
        "volume.usb_fmt": "USB: {name} ({size})",
        "volume.usb_name_fmt": "USB: {name}",
        "err.no_storage": "No storage available",
        "err.usb_not_mounted": "USB {id} not mounted",
        "err.system_folder": "System folders (name contains @) cannot be encrypted.",
    },
}


def normalize_lang(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    if v in ("de", "de-de", "ger"):
        return "de"
    if v in ("en", "en-us", "eng"):
        return "en"
    return None


def set_thread_lang(lang: str) -> None:
    _thread_lang.value = lang


def get_lang() -> str:
    return getattr(_thread_lang, "value", "de")


def lang_from_request(request) -> str:
    from flask import request as _unused  # noqa: F401

    picked = normalize_lang(request.cookies.get(LANG_COOKIE))
    if picked:
        set_thread_lang(picked)
        return picked
    picked = normalize_lang(request.args.get("lang"))
    if picked:
        set_thread_lang(picked)
        return picked
    accept = (request.headers.get("Accept-Language") or "").lower()
    if accept.startswith("de"):
        set_thread_lang("de")
        return "de"
    set_thread_lang("en")
    return "en"


def t(key: str, lang: str | None = None, **fmt: Any) -> str:
    lng = lang or get_lang()
    table = STRINGS.get(lng) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"].get(key) or key
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, ValueError):
            return text
    return text


def bundle(lang: str) -> dict[str, str]:
    lng = normalize_lang(lang) or "en"
    return dict(STRINGS.get(lng) or STRINGS["en"])
