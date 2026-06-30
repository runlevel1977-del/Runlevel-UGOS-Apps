# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = "RUNLEVEL_LOCKKEY_V1"
MAGIC_WRAP = "RUNLEVEL_LOCKKEY_V1_WRAP"
NONCE_SIZE = 12
KEY_SIZE = 32
KDF_ITERATIONS = 600_000
MARKER_NAME = ".lockkey-sealed"
MANIFEST_NAME = ".lockkey-manifest"
MANIFEST_MAGIC = "RUNLEVEL_LOCKKEY_V1_MANIFEST"
ENC_SUFFIX = ".lkenc"
ENC_STAGING_SUFFIX = ".lkenc.staging"
DEC_STAGING_SUFFIX = ".lkdec.staging"
KEY_FILE_PREFIX = "lockkey_"
_RESERVED_NAMES = frozenset({MARKER_NAME, MANIFEST_NAME})


def _sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def new_master_key() -> bytes:
    return secrets.token_bytes(KEY_SIZE)


def key_file_name(vault_id: str) -> str:
    return f"{KEY_FILE_PREFIX}{vault_id}.lk"


def build_key_payload(
    vault_id: str,
    name: str,
    key: bytes,
    usb_label: str = "",
    usb_serial: str = "",
    usb_model: str = "",
    volume: str = "",
    path: str = "",
    host_path: str = "",
) -> dict[str, Any]:
    return {
        "magic": MAGIC,
        "vault_id": vault_id,
        "name": name,
        "key_b64": base64.b64encode(key).decode("ascii"),
        "usb_label": (usb_label or "").strip(),
        "usb_serial": (usb_serial or "").strip(),
        "usb_model": (usb_model or "").strip(),
        "volume": (volume or "").strip(),
        "path": (path or "").strip().strip("/"),
        "host_path": (host_path or "").strip(),
        "created": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }


def _derive_wrap_key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def wrap_key_file(inner: dict[str, Any], passphrase: str) -> dict[str, Any]:
    phrase = (passphrase or "").strip()
    if len(phrase) < 8:
        raise ValueError("key password must be at least 8 characters")
    salt = os.urandom(16)
    wrap_key = _derive_wrap_key(phrase, salt)
    plain = json.dumps(inner, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    blob = encrypt_bytes(wrap_key, plain)
    return {
        "magic": MAGIC_WRAP,
        "vault_id": (inner.get("vault_id") or "").strip(),
        "name": (inner.get("name") or "").strip(),
        "volume": (inner.get("volume") or "").strip(),
        "path": (inner.get("path") or "").strip().strip("/"),
        "host_path": (inner.get("host_path") or "").strip(),
        "kdf": "pbkdf2-sha256",
        "iterations": KDF_ITERATIONS,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "ciphertext_b64": base64.b64encode(blob).decode("ascii"),
        "created": inner.get("created"),
    }


def unwrap_key_file(outer: dict[str, Any], passphrase: str) -> dict[str, Any]:
    phrase = (passphrase or "").strip()
    if not phrase:
        raise ValueError("key file password required")
    if outer.get("magic") != MAGIC_WRAP:
        raise ValueError("not a password-protected key file")
    try:
        salt = base64.b64decode((outer.get("salt_b64") or "").strip())
        blob = base64.b64decode((outer.get("ciphertext_b64") or "").strip())
    except Exception as exc:
        raise ValueError("invalid wrapped key file") from exc
    wrap_key = _derive_wrap_key(phrase, salt)
    try:
        plain = decrypt_bytes(wrap_key, blob)
        inner = json.loads(plain.decode("utf-8"))
    except Exception as exc:
        raise ValueError("wrong key file password") from exc
    if inner.get("magic") != MAGIC:
        raise ValueError("invalid inner key file")
    return inner


def is_wrapped_key_file(data: dict[str, Any]) -> bool:
    return (data.get("magic") or "").strip() == MAGIC_WRAP


def serialize_key_file(inner: dict[str, Any], passphrase: str = "") -> bytes:
    phrase = (passphrase or "").strip()
    payload = wrap_key_file(inner, phrase) if phrase else inner
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def parse_key_payload(raw: bytes | str, passphrase: str = "") -> tuple[bytes, dict[str, Any]]:
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("invalid key file")
    if is_wrapped_key_file(data):
        data = unwrap_key_file(data, passphrase)
    if data.get("magic") != MAGIC:
        raise ValueError("invalid key file magic")
    vault_id = (data.get("vault_id") or "").strip()
    if not vault_id:
        raise ValueError("vault_id missing in key file")
    key_b64 = (data.get("key_b64") or "").strip()
    try:
        key = base64.b64decode(key_b64)
    except Exception as exc:
        raise ValueError("invalid key_b64") from exc
    if len(key) != KEY_SIZE:
        raise ValueError("invalid key length")
    return key, data


def default_usb_label(vault_id: str) -> str:
    return f"RL-LK-{vault_id}"


def encrypt_bytes(key: bytes, plaintext: bytes) -> bytes:
    nonce = os.urandom(NONCE_SIZE)
    aes = AESGCM(key)
    return nonce + aes.encrypt(nonce, plaintext, None)


def decrypt_bytes(key: bytes, blob: bytes) -> bytes:
    if len(blob) < NONCE_SIZE + 16:
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    aes = AESGCM(key)
    return aes.decrypt(nonce, ct, None)


def write_marker(folder: Path, vault_id: str, name: str) -> None:
    payload = {
        "magic": MAGIC,
        "vault_id": vault_id,
        "name": name,
        "sealed": True,
    }
    (folder / MARKER_NAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_marker(folder: Path) -> dict[str, Any] | None:
    path = folder / MARKER_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def remove_marker(folder: Path) -> None:
    path = folder / MARKER_NAME
    if path.is_file():
        path.unlink()


def _is_encrypted_filename(name: str) -> bool:
    return name.endswith(ENC_SUFFIX) and not name.endswith(ENC_STAGING_SUFFIX)


def _is_staging_filename(name: str) -> bool:
    return name.endswith(ENC_STAGING_SUFFIX) or name.endswith(DEC_STAGING_SUFFIX)


def _cleanup_staging_files(folder: Path) -> None:
    for root, dirs, files in os.walk(folder, topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if _is_staging_filename(name):
                try:
                    (Path(root) / name).unlink()
                except OSError:
                    pass


def repair_folder_before_seal(folder: Path) -> None:
    """Drop aborted staging and orphaned .lkenc when the original file still exists."""
    _cleanup_staging_files(folder)
    for enc in iter_encrypted(folder):
        orig = enc.with_name(enc.name[: -len(ENC_SUFFIX)])
        if orig.is_file():
            try:
                enc.unlink()
            except OSError:
                pass


def repair_folder_before_unlock(folder: Path) -> None:
    _cleanup_staging_files(folder)


def _rollback_seal_staging(staged: list[Path]) -> None:
    for path in staged:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def _rollback_unlock_staging(staged: list[Path]) -> None:
    for path in staged:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def iter_files(folder: Path) -> list[Path]:
    import stat

    out: list[Path] = []
    for root, dirs, files in os.walk(folder, topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        root_path = Path(root)
        for name in files:
            if name.startswith(".") or name in _RESERVED_NAMES:
                continue
            if _is_staging_filename(name) or _is_encrypted_filename(name):
                continue
            path = root_path / name
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                if not stat.S_ISREG(path.stat().st_mode):
                    continue
            except OSError:
                continue
            out.append(path)
    return out


def count_sealable_files(folder: Path) -> int:
    return len(iter_files(folder))


def count_encrypted_files(folder: Path) -> int:
    return len(iter_encrypted(folder))


def iter_encrypted(folder: Path) -> list[Path]:
    out: list[Path] = []
    for root, dirs, files in os.walk(folder, topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        root_path = Path(root)
        for name in files:
            if _is_encrypted_filename(name):
                out.append(root_path / name)
    return out


def seal_folder(
    folder: Path,
    key: bytes,
    vault_id: str = "",
    vault_name: str = "",
    progress_cb=None,
) -> dict[str, Any]:
    repair_folder_before_seal(folder)
    sources = sorted(
        iter_files(folder),
        key=lambda p: str(p.relative_to(folder)).replace("\\", "/").casefold(),
    )
    if not sources:
        raise ValueError("no files to seal")
    files_manifest: dict[str, dict[str, Any]] = {}
    staged_paths: list[Path] = []
    staged_pairs: list[tuple[Path, Path, str]] = []
    count = 0
    try:
        for src in sources:
            rel = str(src.relative_to(folder)).replace("\\", "/")
            if not src.is_file():
                raise ValueError(f"missing file during seal: {rel}")
            plain = src.read_bytes()
            entry = {"size": len(plain), "sha256": _sha256_bytes(plain)}
            staging = src.with_name(src.name + ENC_STAGING_SUFFIX)
            if staging.is_file():
                staging.unlink()
            blob = encrypt_bytes(key, plain)
            staging.write_bytes(blob)
            round_plain = decrypt_bytes(key, blob)
            _verify_plaintext(round_plain, entry, rel)
            files_manifest[rel] = entry
            staged_paths.append(staging)
            staged_pairs.append((src, staging, rel))
            count += 1
            if progress_cb:
                progress_cb(count, rel)

        encrypted_paths: list[tuple[Path, Path]] = []
        for src, staging, rel in staged_pairs:
            final = src.with_name(src.name + ENC_SUFFIX)
            if final.is_file():
                final.unlink()
            staging.replace(final)
            if not final.is_file():
                raise ValueError(f"integrity check failed: encrypted file missing after staging: {rel}")
            encrypted_paths.append((src, final))

        for src, final in encrypted_paths:
            rel = str(src.relative_to(folder)).replace("\\", "/")
            if not final.is_file():
                raise ValueError(f"integrity check failed: encrypted file missing before commit: {rel}")
            if not src.is_file():
                raise ValueError(f"integrity check failed: source missing before commit: {rel}")

        for src, _final in encrypted_paths:
            src.unlink()

        enc_count = count_encrypted_files(folder)
        if enc_count != len(files_manifest):
            raise ValueError(f"integrity check failed: encrypted count {enc_count} != {len(files_manifest)}")
        open_left = count_sealable_files(folder)
        if open_left > 0:
            raise ValueError(f"integrity check failed: {open_left} open files remain after seal commit")
        if vault_id:
            write_manifest(folder, vault_id, files_manifest)
            write_marker(folder, vault_id, (vault_name or vault_id).strip())
        extras_open = count_sealable_files(folder)
        return {"files": count, "verify": _verify_ok(count, extras_open=extras_open)}
    except Exception:
        for src, staging, _rel in staged_pairs:
            final = src.with_name(src.name + ENC_SUFFIX)
            if final.is_file() and src.is_file():
                try:
                    final.unlink()
                except OSError:
                    pass
        _rollback_seal_staging(staged_paths)
        raise


def unlock_folder(folder: Path, key: bytes, progress_cb=None) -> dict[str, Any]:
    repair_folder_before_unlock(folder)
    manifest_data = read_manifest(folder)
    files_manifest: dict[str, dict[str, Any]] = {}
    legacy = True
    if manifest_data:
        raw_files = manifest_data.get("files")
        if isinstance(raw_files, dict) and raw_files:
            files_manifest = raw_files
            legacy = False
    enc_files = iter_encrypted(folder)
    if not enc_files:
        raise ValueError("no encrypted files")
    count = 0
    staged_paths: list[Path] = []
    staged_pairs: list[tuple[Path, Path, Path, str]] = []
    try:
        for enc in enc_files:
            orig_name = enc.name[: -len(ENC_SUFFIX)]
            if not orig_name:
                continue
            rel_plain = str(enc.relative_to(folder).with_name(orig_name)).replace("\\", "/")
            plain = decrypt_bytes(key, enc.read_bytes())
            if not legacy:
                entry = files_manifest.get(rel_plain)
                if not entry:
                    raise ValueError(f"integrity check failed: manifest missing {rel_plain}")
                _verify_plaintext(plain, entry, rel_plain)
            staging = enc.with_name(orig_name + DEC_STAGING_SUFFIX)
            if staging.is_file():
                staging.unlink()
            staging.write_bytes(plain)
            staged_paths.append(staging)
            staged_pairs.append((enc, staging, enc.with_name(orig_name), rel_plain))
            count += 1
            if progress_cb:
                progress_cb(count, rel_plain)

        restored: list[tuple[Path, Path]] = []
        for enc, staging, final, rel_plain in staged_pairs:
            if final.is_file():
                final.unlink()
            staging.replace(final)
            if not final.is_file():
                raise ValueError(f"integrity check failed: restored file missing after staging: {rel_plain}")
            restored.append((enc, final))

        if not legacy:
            for rel, entry in files_manifest.items():
                path = folder / rel
                if not path.is_file():
                    raise ValueError(f"integrity check failed: missing restored file {rel}")
                _verify_plaintext(path.read_bytes(), entry, rel)
            if count != len(files_manifest):
                raise ValueError(f"integrity check failed: restored count {count} != {len(files_manifest)}")

        for enc, _final in restored:
            enc.unlink()

        enc_left = count_encrypted_files(folder)
        if enc_left > 0:
            raise ValueError(f"integrity check failed: {enc_left} encrypted files remain after unlock commit")
        remove_marker(folder)
        remove_manifest(folder)
        return {"files": count, "verify": _verify_ok(count, legacy=legacy)}
    except Exception:
        for enc, staging, final, _rel in staged_pairs:
            if final.is_file():
                try:
                    final.unlink()
                except OSError:
                    pass
        _rollback_unlock_staging(staged_paths)
        raise


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_entry_size(entry: dict[str, Any]) -> int:
    raw = entry.get("size")
    if raw is None:
        return -1
    return int(raw)


def _verify_plaintext(plain: bytes, entry: dict[str, Any], rel: str) -> None:
    expected_size = _manifest_entry_size(entry)
    expected_hash = (entry.get("sha256") or "").strip().lower()
    if len(plain) != expected_size:
        raise ValueError(f"integrity check failed (size): {rel}")
    if _sha256_bytes(plain) != expected_hash:
        raise ValueError(f"integrity check failed (hash): {rel}")


def build_file_manifest(folder: Path) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for src in iter_files(folder):
        rel = str(src.relative_to(folder)).replace("\\", "/")
        data = src.read_bytes()
        manifest[rel] = {"size": len(data), "sha256": _sha256_bytes(data)}
    return manifest


def write_manifest(folder: Path, vault_id: str, files: dict[str, dict[str, Any]]) -> None:
    payload = {
        "magic": MANIFEST_MAGIC,
        "vault_id": vault_id,
        "version": 1,
        "files": files,
    }
    (folder / MANIFEST_NAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_manifest(folder: Path) -> dict[str, Any] | None:
    path = folder / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("magic") != MANIFEST_MAGIC:
        return None
    files = data.get("files")
    if not isinstance(files, dict):
        return None
    return data


def remove_manifest(folder: Path) -> None:
    path = folder / MANIFEST_NAME
    if path.is_file():
        path.unlink()


def _verify_ok(checked: int, *, legacy: bool = False, extras_open: int = 0) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True, "checked": checked, "legacy": legacy}
    if extras_open > 0:
        out["extras_open"] = extras_open
    return out


def hash_binding(value: str) -> str:
    return _sha256_text(value.strip().lower())
