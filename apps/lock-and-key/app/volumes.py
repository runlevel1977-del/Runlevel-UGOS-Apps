# -*- coding: utf-8 -*-
"""Local NAS volume mounts — every real /volumeN plus granted UGOS folders."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from usb_storage import discover_usb_mounts
from volume_discover import discover_pool_volumes, discover_ugos_folder_mounts

_USB_ROOT = Path(os.environ.get("NAS_USB_MOUNT", "/mnt/@usb"))
_USB_PREFIX = "usb-"


def usb_root() -> Path:
    return _USB_ROOT


def usb_volume_id(mount_path: Path) -> str:
    return _usb_volume_id(mount_path, _USB_ROOT)


def _configured_volumes() -> list[tuple[str, Path, str]]:
    rows = discover_pool_volumes()
    rows.extend(discover_ugos_folder_mounts())
    return rows


def _usb_volume_id(mount_path: Path, usb_root: Path) -> str:
    try:
        rel = mount_path.resolve().relative_to(usb_root.resolve())
        slug = str(rel).replace("\\", "/")
    except (ValueError, OSError):
        slug = mount_path.name
    slug = slug.replace("/", "__")
    slug = re.sub(r"[^\w.\-]+", "_", slug).strip("._") or "device"
    return f"{_USB_PREFIX}{slug}"


def _pool_label(vid: str, lng: str) -> str:
    from i18n import t

    if vid == "ugos" or vid.startswith("ugos"):
        return t("volume.ugos", lng)
    if vid.isdigit():
        key = f"volume.{vid}"
        labeled = t(key, lng)
        if labeled and labeled != key:
            return labeled
        return t("volume.storage_fallback", lng, id=vid)
    return t("volume.storage_fallback", lng, id=vid)


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
                "label": _pool_label(vid, lng),
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
        label = (
            t("volume.usb_fmt", lng, name=name, size=size)
            if size and size != "—"
            else t("volume.usb_name_fmt", lng, name=name)
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
    known = {row[0] for row in _configured_volumes()}
    if v in known:
        return v
    if v.startswith(_USB_PREFIX):
        return v
    pools = discover_pool_volumes()
    if pools:
        return pools[0][0]
    return "1"


def resolve_local_path(volume_id: str, subpath: str) -> Path:
    from i18n import I18nError

    vid = normalize_volume_id(volume_id)
    rel = (subpath or "").strip().strip("/")
    if vid.startswith(_USB_PREFIX):
        for row in discover_usb_mounts(_USB_ROOT):
            mp = Path(row["mount"])
            if _usb_volume_id(mp, _USB_ROOT) == vid:
                base = mp
                target = (base / rel).resolve() if rel else base.resolve()
                if not str(target).startswith(str(base.resolve())):
                    raise I18nError("err.invalid_path")
                return target
        raise I18nError("err.usb_not_mounted", id=vid)
    for v, mount, _ in _configured_volumes():
        if v == vid and mount.is_dir():
            base = mount
            target = (base / rel).resolve() if rel else base.resolve()
            try:
                base_resolved = base.resolve()
            except OSError as exc:
                raise ValueError(str(exc)) from exc
            if not str(target).startswith(str(base_resolved)):
                raise I18nError("err.invalid_path")
            if not target.is_dir():
                raise I18nError("err.not_directory")
            return target
    raise I18nError("err.no_storage")


def seal_scan_roots() -> list[tuple[str, Path]]:
    """All real pool volumes (any N) for discovering sealed folders."""
    out: list[tuple[str, Path]] = []
    for vid, mount, _ in discover_pool_volumes():
        if mount.is_dir():
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
