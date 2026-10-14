# -*- coding: utf-8 -*-
"""Local NAS mounts for Wake & Sync — granted folders (+ optional real pools)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from usb_storage import discover_usb_mounts
from volume_discover import discover_pool_volumes, discover_ugos_folder_mounts

_USB_ROOT = Path(os.environ.get("NAS_USB_MOUNT", "/mnt/@usb"))
_USB_PREFIX = "usb-"


def _configured_volumes() -> list[tuple[str, Path, str]]:
    rows: list[tuple[str, Path, str]] = []
    # Real pool mounts only when present in the container (pid:host → /proc/1/root).
    # Never invent empty Volume 3+ placeholders.
    rows.extend(discover_pool_volumes())
    rows.extend(discover_ugos_folder_mounts())
    out: list[tuple[str, Path, str]] = []
    seen: set[str] = set()
    for vid, mount, hint in rows:
        try:
            key = str(mount.resolve())
        except OSError:
            key = f"{vid}:{mount}"
        if key in seen:
            continue
        seen.add(key)
        out.append((vid, mount, hint))
    return out


def _usb_volume_id(mount_path: Path, usb_root: Path) -> str:
    try:
        rel = mount_path.resolve().relative_to(usb_root.resolve())
        slug = str(rel).replace("\\", "/")
    except (ValueError, OSError):
        slug = mount_path.name
    slug = slug.replace("/", "__")
    slug = re.sub(r"[^\w.\-]+", "_", slug).strip("._") or "device"
    return f"{_USB_PREFIX}{slug}"


def _configured_usb_volumes() -> list[tuple[str, Path, str, dict[str, Any]]]:
    rows: list[tuple[str, Path, str, dict[str, Any]]] = []
    for row in discover_usb_mounts(_USB_ROOT):
        mp = Path(row["mount"])
        vid = _usb_volume_id(mp, _USB_ROOT)
        host_hint = str(row.get("host_mount") or mp)
        rows.append((vid, mp, host_hint, row))
    return rows


def _usb_label(meta: dict[str, Any], lng: str) -> str:
    from i18n import t

    name = (meta.get("model") or Path(str(meta.get("mount") or "")).name or "?").strip()
    size = (meta.get("size") or "").strip()
    if size and size != "—":
        return t("volume.usb_fmt", lng, name=name, size=size)
    return t("volume.usb_name_fmt", lng, name=name)


def _pool_label(vid: str, host_hint: str, lng: str) -> str:
    from i18n import t

    if vid == "ugos" or vid.startswith("ugos"):
        base = t("volume.ugos", lng)
        hint = (host_hint or "").strip()
        if vid == "ugos" or not hint:
            return base
        short = hint.rstrip("/").split("/")[-1] or hint
        return f"{base} ({short})"
    if vid.isdigit():
        key = f"volume.{vid}"
        labeled = t(key, lng)
        if labeled and labeled != key:
            return labeled
        return f"Volume {vid}"
    return f"Volume {vid}"


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
                "label": _pool_label(vid, host_hint, lng),
                "mount": str(mount),
                "host_path": host_hint,
                "kind": "pool",
            }
        )
    for vid, mount, host_hint, meta in _configured_usb_volumes():
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
                "label": _usb_label(meta, lng),
                "mount": str(mount),
                "host_path": host_hint,
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


def volume_label(volume_id: str) -> str:
    from i18n import get_lang, t

    vid = volume_id or "ugos"
    for v in list_volumes():
        if v["id"] == vid:
            return v["label"]
    if vid.startswith(_USB_PREFIX):
        slug = vid[len(_USB_PREFIX) :].replace("__", "/")
        return t("volume.usb_name_fmt", get_lang(), name=slug)
    return _pool_label(vid, "", get_lang())


def resolve_local_path(volume_id: str, subpath: str) -> Path:
    from i18n import get_lang, t

    vid = (volume_id or "ugos").strip() or "ugos"
    rel = (subpath or "").strip().strip("/")

    if vid.startswith(_USB_PREFIX):
        for v, mount, _, _ in _configured_usb_volumes():
            if v == vid and mount.is_dir():
                return mount / rel if rel else mount
        raise ValueError(t("err.usb_not_mounted", get_lang(), id=vid))

    for v, mount, _ in _configured_volumes():
        if v == vid and mount.is_dir():
            return mount / rel if rel else mount

    mounts = list_volumes()
    if mounts:
        m = Path(mounts[0]["mount"])
        return m / rel if rel else m
    raise ValueError(t("err.no_storage", get_lang()))


def normalize_volume_id(volume_id: str | None) -> str:
    v = (volume_id or "").strip()
    known = {row[0] for row in _configured_volumes()}
    if v in known:
        return v
    if v.startswith(_USB_PREFIX):
        for vid, mount, _, _ in _configured_usb_volumes():
            if vid == v and mount.is_dir():
                return v
        return v
    if known:
        # Prefer ugos* then lowest pool id
        ug = sorted(x for x in known if x.startswith("ugos"))
        if ug:
            return ug[0]
        return sorted(known, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))[0]
    return "ugos"
