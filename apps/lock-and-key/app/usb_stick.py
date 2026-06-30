# -*- coding: utf-8 -*-
"""Prepare a USB stick: one vault, one key file — format or wipe before write."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from crypto_engine import KEY_FILE_PREFIX, hash_binding
from store import append_log, load_vaults
from usb_bind import device_path_for_mount
from usb_storage import device_is_usb_transport

_PART = re.compile(r"^sd[a-z]+\d+$", re.I)


def _run_rc(cmd: list[str], timeout: float = 60.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        text = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, text.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)


def vault_bound_to_usb_serial(serial: str, exclude_vault_id: str = "") -> dict[str, Any] | None:
    serial = (serial or "").strip()
    if not serial:
        return None
    serial_hash = hash_binding(serial)
    for vault in load_vaults():
        vid = (vault.get("id") or "").strip()
        if exclude_vault_id and vid == exclude_vault_id:
            continue
        if (vault.get("usb_serial_hash") or "") == serial_hash:
            return vault
    return None


def list_lockkey_files(mount: Path) -> list[Path]:
    try:
        return sorted(mount.glob(f"{KEY_FILE_PREFIX}*.lk"))
    except OSError:
        return []


def wipe_mount_contents(mount: Path) -> None:
    for child in mount.iterdir():
        name = child.name
        if name in (".", ".."):
            continue
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError as exc:
            raise ValueError(f"cannot wipe {child}: {exc}") from exc


def _format_partition(part_dev: str, mount: Path) -> bool:
    if not _PART.match(Path(part_dev).name):
        raise ValueError("refusing to format: not a USB partition")
    if not device_is_usb_transport(part_dev):
        raise ValueError("refusing to format: not a USB device")

    rc, _ = _run_rc(["umount", str(mount)], timeout=20.0)
    if rc != 0:
        return False
    rc, out = _run_rc(["mkfs.vfat", "-F", "32", "-n", "LOCKKEY", part_dev], timeout=120.0)
    if rc != 0:
        append_log(f"mkfs.vfat failed on {part_dev}: {out}")
        _run_rc(["mount", part_dev, str(mount)], timeout=15.0)
        return False
    append_log(f"USB formatted {part_dev} as FAT32 (LOCKKEY)")
    rc, out = _run_rc(["mount", part_dev, str(mount)], timeout=15.0)
    if rc != 0:
        append_log(f"remount {mount} after format failed: {out}")
    return True


def owning_vault_for_stick(mount: Path) -> dict[str, Any] | None:
    """Return vault record if a key file on the stick still belongs to a registered vault."""
    from store import get_vault

    for key_file in list_lockkey_files(mount):
        stem = key_file.stem
        if not stem.startswith(KEY_FILE_PREFIX):
            continue
        vid = stem[len(KEY_FILE_PREFIX) :].strip()
        if not vid:
            continue
        vault = get_vault(vid)
        if vault:
            return vault
    return None


def prepare_usb_stick_for_vault(row: dict[str, Any], vault_id: str) -> Path:
    """
    Wipe/format removable USB media, then leave it empty for a single key file.
    One stick must not serve multiple vaults (checked via USB serial when known).
    """
    mount = Path(row.get("mount") or "")
    if not mount.is_dir():
        raise ValueError("USB mount not available")

    serial = (row.get("usb_serial") or "").strip()
    other = vault_bound_to_usb_serial(serial, exclude_vault_id=vault_id)
    if other:
        raise ValueError(
            f"USB stick already used by vault “{other.get('name') or other.get('id')}”"
        )

    device = (row.get("device") or "").strip()
    part_dev = device_path_for_mount(mount, device)
    if not part_dev.startswith("/dev/"):
        raise ValueError("USB partition device not found")
    if not device_is_usb_transport(part_dev):
        raise ValueError("refusing to prepare: not a USB device")

    if not _format_partition(part_dev, mount):
        wipe_mount_contents(mount)
        append_log(f"USB wiped at {mount} (full format unavailable)")

    for key_file in list_lockkey_files(mount):
        try:
            key_file.unlink()
        except OSError:
            pass

    if list_lockkey_files(mount):
        raise ValueError("could not clear old key files from USB stick")

    return mount
