# -*- coding: utf-8 -*-
"""Encrypt credential fields at rest (Fernet). Key lives next to the data, not in env."""
from __future__ import annotations

import os
from pathlib import Path

_PREFIX = "enc:v1:"


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    return Fernet


def key_path(data_dir: Path) -> Path:
    return data_dir / ".app_secret"


def _load_or_create_key(data_dir: Path) -> bytes | None:
    Fernet = _fernet()
    if Fernet is None:
        return None
    data_dir.mkdir(parents=True, exist_ok=True)
    path = key_path(data_dir)
    if path.is_file():
        raw = path.read_bytes().strip()
        if raw:
            return raw
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def encrypt_secret(data_dir: Path, plaintext: str) -> str:
    if not plaintext:
        return ""
    if str(plaintext).startswith(_PREFIX):
        return str(plaintext)
    Fernet = _fernet()
    key = _load_or_create_key(data_dir)
    if Fernet is None or key is None:
        return plaintext
    token = Fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt_secret(data_dir: Path, stored: str) -> str:
    raw = str(stored or "")
    if not raw.startswith(_PREFIX):
        return raw
    Fernet = _fernet()
    key = _load_or_create_key(data_dir)
    if Fernet is None or key is None:
        return ""
    try:
        return Fernet(key).decrypt(raw[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except Exception:
        return ""
