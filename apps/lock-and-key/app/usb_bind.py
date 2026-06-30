# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from usb_storage import discover_usb_mounts, parse_lsblk_pair_line

_UGOS_PART = re.compile(r"^sd[a-z]\d+$", re.I)


def _run(cmd: list[str], timeout: float = 10.0) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            return ""
        return proc.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _read_sysfs_file(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        pass
    return ""


def _disk_name_from_partition(part: str) -> str:
    part = (part or "").strip()
    if not part:
        return ""
    if part.startswith("/dev/"):
        part = Path(part).name
    m = re.match(r"^(sd[a-z]+)\d+$", part, re.I)
    return m.group(1) if m else ""


def _device_pair(device: str) -> tuple[str, str]:
    """Return (partition_dev, disk_dev) e.g. (/dev/sde1, /dev/sde)."""
    dev = (device or "").strip()
    if not dev:
        return "", ""
    name = Path(dev).name if dev.startswith("/dev/") else dev
    part_dev = f"/dev/{name}" if not dev.startswith("/dev/") else dev
    disk = _disk_name_from_partition(name)
    disk_dev = f"/dev/{disk}" if disk else ""
    return part_dev, disk_dev


def device_path_for_mount(mount: Path, device_hint: str = "") -> str:
    hint = (device_hint or "").strip()
    if hint.startswith("/dev/"):
        return hint
    if _UGOS_PART.match(mount.name):
        return f"/dev/{mount.name}"
    src = _run(["findmnt", "-no", "SOURCE", str(mount)], timeout=8.0).strip()
    if src.startswith("/dev/"):
        return src
    return hint


def _lsblk_rows() -> list[dict[str, str]]:
    text = _run(
        ["lsblk", "-P", "-o", "NAME,LABEL,SERIAL,MODEL,MOUNTPOINT,SIZE,TYPE,TRAN"],
        timeout=12.0,
    )
    rows: list[dict[str, str]] = []
    for raw in (text or "").replace("\r", "").splitlines():
        ln = raw.strip()
        if not ln:
            continue
        kv = parse_lsblk_pair_line(ln)
        rows.append(
            {
                "name": (kv.get("NAME") or "").strip(),
                "label": (kv.get("LABEL") or "").strip(),
                "serial": (kv.get("SERIAL") or "").strip(),
                "model": (kv.get("MODEL") or "").strip(),
                "mountpoint": (kv.get("MOUNTPOINT") or "").strip(),
                "size": (kv.get("SIZE") or "").strip(),
                "type": (kv.get("TYPE") or "").strip(),
                "tran": (kv.get("TRAN") or "").strip(),
            }
        )
    return rows


def _lsblk_map_by_mountpoint() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in _lsblk_rows():
        mp = row.get("mountpoint") or ""
        if mp:
            out[mp] = row
    return out


def _lsblk_row_for_device(device: str) -> dict[str, str]:
    part_dev, disk_dev = _device_pair(device)
    names = {Path(d).name for d in (part_dev, disk_dev) if d}
    found_part: dict[str, str] = {}
    found_disk: dict[str, str] = {}
    for row in _lsblk_rows():
        name = row.get("name") or ""
        if name not in names:
            continue
        if row.get("type") == "disk" or name == Path(disk_dev).name:
            found_disk = row
        else:
            found_part = row
    return found_disk or found_part


def _udev_properties(device: str) -> dict[str, str]:
    out = _run(["udevadm", "info", "-q", "property", "-n", device], timeout=8.0)
    props: dict[str, str] = {}
    for line in (out or "").splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            props[key] = val.strip()
    return props


def _walk_usb_serial(disk_name: str) -> str:
    if not disk_name:
        return ""
    candidates: list[Path] = [
        Path(f"/sys/block/{disk_name}/device/serial"),
    ]
    device_link = Path(f"/sys/block/{disk_name}/device")
    try:
        if device_link.exists():
            resolved = device_link.resolve()
            p = resolved
            for _ in range(8):
                candidates.append(p / "serial")
                if p.parent == p:
                    break
                p = p.parent
    except OSError:
        pass
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        val = _read_sysfs_file(path)
        if val and val.upper() not in {"0", "NONE", "N/A"}:
            return val
    return ""


def model_for_device(device: str) -> str:
    part_dev, disk_dev = _device_pair(device)
    row = _lsblk_row_for_device(device)
    if row.get("model"):
        return row["model"]
    for dev in (disk_dev, part_dev):
        if not dev:
            continue
        out = _run(["lsblk", "-dn", "-o", "MODEL", dev], timeout=8.0).strip()
        if out:
            return out
        props = _udev_properties(dev)
        for key in ("ID_MODEL", "ID_MODEL_FROM_DATABASE", "ID_USB_MODEL"):
            if props.get(key):
                return props[key]
    return ""


def fs_label_for_mount(mount: Path, device: str = "") -> str:
    dev = device_path_for_mount(mount, device)
    mp = str(mount)
    blk = _lsblk_map_by_mountpoint().get(mp, {})
    if blk.get("label"):
        return blk["label"]
    for target in (dev, mp):
        if not target:
            continue
        out = _run(["blkid", "-s", "LABEL", "-o", "value", target], timeout=8.0)
        label = (out or "").strip().strip('"')
        if label:
            return label
        out = _run(["lsblk", "-no", "LABEL", target], timeout=8.0).strip()
        if out:
            return out
    return _run(["findmnt", "-no", "LABEL", mp], timeout=8.0).strip()


def serial_for_device(device: str) -> str:
    part_dev, disk_dev = _device_pair(device)
    disk_name = Path(disk_dev).name if disk_dev else _disk_name_from_partition(part_dev)

    row = _lsblk_row_for_device(device)
    if row.get("serial"):
        return row["serial"]

    serial = _walk_usb_serial(disk_name)
    if serial:
        return serial

    for dev in (disk_dev, part_dev):
        if not dev:
            continue
        out = _run(["lsblk", "-dn", "-o", "SERIAL", dev], timeout=8.0).strip()
        if out:
            return out
        props = _udev_properties(dev)
        for key in (
            "ID_SERIAL_SHORT",
            "ID_USB_SERIAL",
            "ID_SERIAL",
            "ID_SCSI_SERIAL",
        ):
            val = props.get(key, "")
            if val:
                return val
    return ""


def stick_display_name(model: str, fs_label: str) -> str:
    """Name like UGOS shows (Patriot), not partition id (sde1)."""
    model = (model or "").strip()
    fs_label = (fs_label or "").strip()
    if model and not _UGOS_PART.match(model):
        return model
    return fs_label


def usb_rows_enriched() -> list[dict[str, Any]]:
    lsblk_map = _lsblk_map_by_mountpoint()
    rows: list[dict[str, Any]] = []
    for row in discover_usb_mounts():
        mount = Path(row["mount"])
        device = device_path_for_mount(mount, str(row.get("device") or ""))
        blk = lsblk_map.get(str(mount), {})
        fs_label = fs_label_for_mount(mount, device)
        model = model_for_device(device) or (blk.get("model") or "").strip()
        if model in ("", "—", mount.name):
            model = model_for_device(device)
        serial = serial_for_device(device) or (blk.get("serial") or "").strip()
        display = stick_display_name(model, fs_label)
        rows.append(
            {
                **row,
                "device": device or row.get("device") or "",
                "fs_label": fs_label,
                "model": model,
                "stick_name": display,
                "volume_label": display or fs_label,
                "usb_serial": serial,
            }
        )
    return rows


def find_key_on_usb(vault_id: str, usb_mount: Path) -> Path | None:
    from crypto_engine import KEY_FILE_PREFIX, MAGIC, MAGIC_WRAP

    wanted = f"{KEY_FILE_PREFIX}{vault_id}.lk"
    direct = usb_mount / wanted
    if direct.is_file():
        return direct
    try:
        for child in usb_mount.iterdir():
            if not child.is_file() or child.name.startswith("."):
                continue
            if child.name == wanted or child.suffix.lower() in {".lk", ".json", ".key"}:
                try:
                    text = child.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if (MAGIC in text or MAGIC_WRAP in text) and vault_id in text:
                    return child
    except OSError:
        return None
    return None


def match_usb_binding(
    vault: dict[str, Any],
    usb_rows: list[dict[str, Any]] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    from crypto_engine import hash_binding

    rows = usb_rows if usb_rows is not None else usb_rows_enriched()
    label_hash = (vault.get("usb_label_hash") or "").strip()
    serial_hash = (vault.get("usb_serial_hash") or "").strip()
    model_hash = (vault.get("usb_model_hash") or "").strip()
    if not label_hash and not serial_hash and not model_hash:
        return True, "no binding", rows[0] if rows else None
    for row in rows:
        label_ok = True
        serial_ok = True
        model_ok = True
        if label_hash:
            label_ok = hash_binding(row.get("volume_label") or row.get("stick_name") or "") == label_hash
        if serial_hash:
            serial_ok = hash_binding(row.get("usb_serial") or "") == serial_hash
        if model_hash:
            model_ok = hash_binding(row.get("model") or "") == model_hash
        if serial_hash and serial_ok and (not model_hash or model_ok) and (not label_hash or label_ok):
            return True, "matched", row
        if not serial_hash and model_hash and model_ok and (not label_hash or label_ok):
            return True, "matched", row
        if not serial_hash and not model_hash and label_hash and label_ok:
            return True, "matched", row
    return False, "usb binding mismatch", None
