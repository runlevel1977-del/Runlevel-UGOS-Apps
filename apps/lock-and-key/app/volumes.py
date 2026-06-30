# -*- coding: utf-8 -*-
"""Local NAS volume mounts."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from usb_storage import discover_usb_mounts

_UGOS = Path(os.environ.get("NAS_UGOS_MOUNT", "/mnt/ugos"))
_VOL1 = Path(os.environ.get("NAS_VOL1_MOUNT", "/mnt/vol1"))
_VOL2 = Path(os.environ.get("NAS_VOL2_MOUNT", "/mnt/vol2"))
_USB_ROOT = Path(os.environ.get("NAS_USB_MOUNT", "/mnt/@usb"))
_USB_PREFIX = "usb-"
_VOLUME_KEYS = {"1": "volume.1", "2": "volume.2", "ugos": "volume.ugos"}


def usb_root() -> Path:
    return _USB_ROOT


def usb_volume_id(mount_path: Path) -> str:
    return _usb_volume_id(mount_path, _USB_ROOT)


def _configured_volumes() -> list[tuple[str, Path, str]]:
    return [
        ("1", _VOL1, "/volume1"),
        ("2", _VOL2, "/volume2"),
        ("ugos", _UGOS, os.environ.get("NAS_DATA_ROOT_HOST", "UGOS selection")),
    ]


def _usb_volume_id(mount_path: Path, usb_root: Path) -> str:
    try:
        rel = mount_path.resolve().relative_to(usb_root.resolve())
        slug = str(rel).replace("\\", "/")
    except (ValueError, OSError):
        slug = mount_path.name
    slug = slug.replace("/", "__")
    slug = re.sub(r"[^\w.\-]+", "_", slug).strip("._") or "device"
    return f"{_USB_PREFIX}{slug}"


def list_volumes() -> list[dict[str, Any]]:
    from i18n import get_lang, t

    lng = get_lang()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for vid, mount, host_hint in _configured_volumes():
        if not mount.is_dir():
            continue
        try:
            key = str(mount.resolve())
        except OSError:
            key = str(mount)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": vid,
                "label": t(_VOLUME_KEYS.get(vid, "volume.storage_fallback"), lng, id=vid),
                "mount": str(mount),
                "host_path": host_hint,
                "kind": "pool",
            }
        )
    for row in discover_usb_mounts(_USB_ROOT):
        mp = Path(row["mount"])
        vid = _usb_volume_id(mp, _USB_ROOT)
        try:
            key = str(mp.resolve())
        except OSError:
            key = str(mp)
        if key in seen:
            continue
        seen.add(key)
        name = (row.get("model") or mp.name or "?").strip()
        size = (row.get("size") or "").strip()
        label = t("volume.usb_fmt", lng, name=name, size=size) if size and size != "—" else t(
            "volume.usb_name_fmt", lng, name=name
        )
        out.append(
            {
                "id": vid,
                "label": label,
                "mount": str(mp),
                "host_path": str(row.get("host_mount") or mp),
                "kind": "usb",
            }
        )
    try:
        from store import DATA_DIR, append_log
        from ugos_support import enrich_volume_rows, fetch_metrics

        out = enrich_volume_rows(out, fetch_metrics(DATA_DIR, log=append_log))
    except Exception:
        pass
    return out


def normalize_volume_id(volume_id: str | None) -> str:
    v = (volume_id or "").strip()
    if v in ("1", "2", "ugos"):
        return v
    if v.startswith(_USB_PREFIX):
        return v
    return "1"


def resolve_local_path(volume_id: str, subpath: str) -> Path:
    from i18n import get_lang, t

    vid = normalize_volume_id(volume_id)
    rel = (subpath or "").strip().strip("/")
    if vid.startswith(_USB_PREFIX):
        for row in discover_usb_mounts(_USB_ROOT):
            mp = Path(row["mount"])
            if _usb_volume_id(mp, _USB_ROOT) == vid:
                base = mp
                target = (base / rel).resolve() if rel else base.resolve()
                if not str(target).startswith(str(base.resolve())):
                    raise ValueError("invalid path")
                return target
        raise ValueError(t("err.usb_not_mounted", get_lang(), id=vid))
    for v, mount, _ in _configured_volumes():
        if v == vid and mount.is_dir():
            base = mount
            target = (base / rel).resolve() if rel else base.resolve()
            try:
                base_resolved = base.resolve()
            except OSError as exc:
                raise ValueError(str(exc)) from exc
            if not str(target).startswith(str(base_resolved)):
                raise ValueError("invalid path")
            if not target.is_dir():
                raise ValueError("not a directory")
            return target
    raise ValueError(t("err.no_storage", get_lang()))


def seal_scan_roots() -> list[tuple[str, Path]]:
    """Volume id + mount for discovering sealed folders (Volume 1/2 only)."""
    out: list[tuple[str, Path]] = []
    for vid, mount, _ in _configured_volumes():
        if vid in ("1", "2") and mount.is_dir():
            out.append((vid, mount))
    return out


def host_path_for(volume_id: str, subpath: str) -> str:
    rel = (subpath or "").strip().strip("/")
    vid = normalize_volume_id(volume_id)
    for v, _mount, host_hint in _configured_volumes():
        if v == vid:
            base = (host_hint or "").rstrip("/")
            return f"{base}/{rel}" if rel else base
    for row in list_volumes():
        if row["id"] == vid:
            base = (row.get("host_path") or row.get("mount") or "").rstrip("/")
            return f"{base}/{rel}" if rel else base
    return rel
