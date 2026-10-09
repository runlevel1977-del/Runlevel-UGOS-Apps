# -*- coding: utf-8 -*-
"""RSA-OAEP (SHA-256) for HTTP credential fields. Private key stays on the NAS data dir."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_PRIV_NAME = ".rsa_private.pem"
_PUB_NAME = ".rsa_public.pem"


def _priv_path(data_dir: Path) -> Path:
    return data_dir / _PRIV_NAME


def _pub_path(data_dir: Path) -> Path:
    return data_dir / _PUB_NAME


def _oaep() -> padding.OAEP:
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )


def ensure_keypair(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    priv_p = _priv_path(data_dir)
    pub_p = _pub_path(data_dir)
    if priv_p.is_file() and pub_p.is_file():
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_p.write_bytes(priv_pem)
    pub_p.write_bytes(pub_pem)
    try:
        os.chmod(priv_p, 0o600)
        os.chmod(pub_p, 0o644)
    except OSError:
        pass


def public_pem(data_dir: Path) -> str:
    ensure_keypair(data_dir)
    return _pub_path(data_dir).read_text(encoding="ascii")


def _load_private(data_dir: Path):
    ensure_keypair(data_dir)
    return serialization.load_pem_private_key(
        _priv_path(data_dir).read_bytes(),
        password=None,
    )


def decrypt_oaep_bytes(data_dir: Path, b64_cipher: str) -> bytes:
    raw = str(b64_cipher or "").strip()
    if not raw:
        raise ValueError("empty ciphertext")
    blob = base64.b64decode(raw, validate=False)
    key = _load_private(data_dir)
    try:
        return key.decrypt(blob, _oaep())
    except Exception:
        return key.decrypt(blob, padding.PKCS1v15())


def decrypt_oaep(data_dir: Path, b64_cipher: str) -> str:
    return decrypt_oaep_bytes(data_dir, b64_cipher).decode("utf-8")


def decrypt_chunked(data_dir: Path, blob: str) -> bytes:
    """Decrypt RSA ciphertext, including c1:<n>:<chunk>:… envelopes for large payloads."""
    raw = str(blob or "").strip()
    if not raw:
        raise ValueError("empty ciphertext")
    if raw.startswith("c1:"):
        parts = raw.split(":")
        if len(parts) < 3:
            raise ValueError("invalid ciphertext")
        try:
            n = int(parts[1])
        except ValueError as exc:
            raise ValueError("invalid ciphertext") from exc
        chunks = parts[2:]
        if n != len(chunks) or n < 1:
            raise ValueError("invalid ciphertext")
        return b"".join(decrypt_oaep_bytes(data_dir, c) for c in chunks)
    return decrypt_oaep_bytes(data_dir, raw)


def encrypt_oaep(data_dir: Path, plaintext: str) -> str:
    """Test helper: OAEP encrypt with the local public key."""
    ensure_keypair(data_dir)
    pub = serialization.load_pem_public_key(_pub_path(data_dir).read_bytes())
    blob = pub.encrypt(plaintext.encode("utf-8"), _oaep())
    return base64.b64encode(blob).decode("ascii")


def encrypt_pkcs1(data_dir: Path, plaintext: str) -> str:
    """HTTP fallback used by the browser when crypto.subtle is missing."""
    ensure_keypair(data_dir)
    pub = serialization.load_pem_public_key(_pub_path(data_dir).read_bytes())
    blob = pub.encrypt(plaintext.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(blob).decode("ascii")


def decrypt_wire_fields(data_dir: Path, obj: dict, *names: str) -> None:
    """Reject plaintext for `names`; decrypt `{name}_enc` into `name`.

    Empty values are left unchanged so the caller can keep stored data.
    """
    if not isinstance(obj, dict):
        return
    for name in names:
        if str(obj.get(name) or "").strip():
            raise ValueError("plaintext values are not accepted")
        enc = str(obj.get(f"{name}_enc") or "").strip()
        if enc:
            obj[name] = decrypt_oaep(data_dir, enc)
            obj.pop(f"{name}_enc", None)
