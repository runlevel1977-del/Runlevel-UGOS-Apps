# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "app" / "i18n.py"
OUT = ROOT / "_en_strings.json"

ns: dict = {}
partial = SRC.read_text(encoding="utf-8").split("def normalize_lang", 1)[0]
exec(compile(partial, "i18n_partial.py", "exec"), ns)
en: dict[str, str] = dict(ns["STRINGS"]["en"])
de: dict[str, str] = dict(ns["STRINGS"]["de"])
assert set(en) == set(de), (set(en) - set(de), set(de) - set(en))

extra: dict[str, tuple[str, str]] = {
    "err.no_usb": (
        "Kein USB-Stick eingesteckt.",
        "No USB stick mounted.",
    ),
    "err.usb_selected_missing": (
        "Gewählter USB-Stick ist nicht gemountet.",
        "Selected USB stick not mounted.",
    ),
    "err.select_usb": (
        "Bitte einen USB-Stick wählen.",
        "Select a USB stick.",
    ),
    "err.folder_not_found": (
        "Ordner nicht gefunden.",
        "Folder not found.",
    ),
    "err.folder_already_sealed": (
        "Ordner bereits gesperrt (Tresor „{name}“) — zuerst öffnen oder anderen Ordner wählen.",
        "Folder already sealed (vault “{name}”) — unlock first or pick another folder.",
    ),
    "err.folder_partial": (
        "Ordner teilweise gesperrt (Mix aus offenen und .lkenc-Dateien) — zuerst mit Schlüssel öffnen oder verwaiste verschlüsselte Dateien entfernen.",
        "Folder is partially sealed (mix of open files and .lkenc) — unlock with key first or remove orphaned encrypted files manually.",
    ),
    "err.no_encryptable": (
        "Keine verschlüsselbaren Dateien in {host} — für Freigaben Volume 1/2 nutzen, nicht den UGOS-Kurzweg.",
        "No encryptable files in {host} — use Volume 1/2 for shared folders, not the UGOS shortcut.",
    ),
    "err.usb_bound_other": (
        "USB-Stick ist bereits Tresor „{name}“ zugeordnet.",
        "USB stick is already bound to vault “{name}”.",
    ),
    "err.usb_owned_other": (
        "USB-Stick gehört noch zu Tresor „{name}“ — anderen Stick wählen oder diesen Tresor zuerst löschen.",
        "USB stick still belongs to vault “{name}” — pick another stick or delete that vault first.",
    ),
    "err.encrypted_zero": (
        "0 Dateien verschlüsselt in {folder}.",
        "Encrypted 0 files in {folder}.",
    ),
    "err.vault_not_found": (
        "Tresor nicht gefunden.",
        "Vault not found.",
    ),
    "err.vault_not_locked": (
        "Tresor ist nicht gesperrt.",
        "Vault is not locked.",
    ),
    "err.vault_not_unlocked": (
        "Tresor ist nicht geöffnet.",
        "Vault is not unlocked.",
    ),
    "err.folder_already_sealed_simple": (
        "Ordner ist bereits gesperrt.",
        "Folder already sealed.",
    ),
    "err.key_not_on_usb": (
        "Schlüsseldatei nicht auf dem USB-Stick gefunden.",
        "Key file not found on USB.",
    ),
    "err.key_vault_mismatch": (
        "Schlüsseldatei gehört zu einem anderen Tresor.",
        "Key file vault mismatch.",
    ),
    "err.usb_binding_mismatch": (
        "USB-Bindung stimmt nicht (Stick/Seriennummer).",
        "USB binding mismatch.",
    ),
    "err.vault_busy": (
        "Tresor ist beschäftigt.",
        "Vault is busy.",
    ),
    "err.vault_locked_delete": (
        "Tresor ist gesperrt — Löschen bestätigen, um nur den Listeneintrag zu entfernen.",
        "Vault is locked — confirm delete to remove from list only.",
    ),
    "err.not_directory": (
        "Kein Ordner.",
        "Not a directory.",
    ),
    "err.invalid_path": (
        "Ungültiger Pfad.",
        "Invalid path.",
    ),
    "err.key_pw_short": (
        "Schlüssel-Passwort mindestens 8 Zeichen.",
        "Key password must be at least 8 characters.",
    ),
    "err.key_pw_required": (
        "Passwort für Schlüsseldatei erforderlich.",
        "Key file password required.",
    ),
    "err.not_pw_key": (
        "Keine passwortgeschützte Schlüsseldatei.",
        "Not a password-protected key file.",
    ),
    "err.wrong_key_pw": (
        "Falsches Passwort für Schlüsseldatei.",
        "Wrong key file password.",
    ),
    "err.invalid_key_file": (
        "Ungültige Schlüsseldatei.",
        "Invalid key file.",
    ),
    "err.no_encrypted_files": (
        "Keine verschlüsselten Dateien.",
        "No encrypted files.",
    ),
    "err.no_files_to_seal": (
        "Keine Dateien zum Sperren.",
        "No files to seal.",
    ),
    "err.verify_fail_detail": (
        "Integritätsprüfung fehlgeschlagen: {detail}",
        "Integrity check failed: {detail}",
    ),
    "err.usb_refuse_format": (
        "Formatieren verweigert: kein USB-Gerät.",
        "Refusing to format: not a USB device.",
    ),
    "err.usb_mount_missing": (
        "USB-Mount nicht verfügbar.",
        "USB mount not available.",
    ),
    "err.usb_clear_keys": (
        "Alte Schlüsseldateien auf dem Stick konnten nicht gelöscht werden.",
        "Could not clear old key files from USB stick.",
    ),
    "job.timeout": (
        "Zeitüberschreitung",
        "Timeout",
    ),
}

for key, (d, e) in extra.items():
    de[key] = d
    en[key] = e

OUT.write_text(json.dumps({"de": de, "en": en}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("keys", len(en))
print("wrote", OUT)
