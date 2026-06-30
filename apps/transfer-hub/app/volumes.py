# -*- coding: utf-8 -*-

"""Local NAS volume mounts inside the container."""

from __future__ import annotations



import os

import re

from pathlib import Path

from typing import Any



from usb_storage import discover_usb_mounts



# UGOS path picker (user must pick a subfolder — cannot confirm at „Freigegebener Ordner“)

_UGOS = Path(os.environ.get("NAS_UGOS_MOUNT", "/mnt/ugos"))

# Whole pools (fixed host paths — work in Transfer Hub picker)

_VOL1 = Path(os.environ.get("NAS_VOL1_MOUNT", "/mnt/vol1"))

_VOL2 = Path(os.environ.get("NAS_VOL2_MOUNT", "/mnt/vol2"))

_USB_ROOT = Path(os.environ.get("NAS_USB_MOUNT", "/mnt/@usb"))



_VOLUME_KEYS = {"1": "volume.1", "2": "volume.2", "ugos": "volume.ugos"}

_USB_PREFIX = "usb-"





def _configured_volumes() -> list[tuple[str, Path, str]]:

    """(id, container_path, host_hint)."""

    return [

        ("1", _VOL1, "/volume1"),

        ("2", _VOL2, "/volume2"),

        (

            "ugos",

            _UGOS,

            os.environ.get("NAS_DATA_ROOT_HOST", "UGOS-Auswahl"),

        ),

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





def _configured_usb_volumes() -> list[tuple[str, Path, str, dict[str, Any]]]:

    """(id, container_path, host_hint, meta)."""

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

        out.append({

            "id": vid,

            "label": t(_VOLUME_KEYS.get(vid, "volume.storage_fallback"), lng, id=vid),

            "mount": str(mount),

            "host_path": host_hint,

            "kind": "pool",

        })

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

        out.append({

            "id": vid,

            "label": _usb_label(meta, lng),

            "mount": str(mount),

            "host_path": host_hint,

            "kind": "usb",

            "usb_size": meta.get("size") or "",

            "usb_model": meta.get("model") or "",

        })

    try:
        from store import DATA_DIR, append_log
        from ugos_support import enrich_volume_rows, fetch_metrics

        out = enrich_volume_rows(out, fetch_metrics(DATA_DIR, log=append_log))
    except Exception:
        pass

    return out





def volume_label(volume_id: str) -> str:

    from i18n import get_lang, t



    vid = volume_id or "1"

    for v in list_volumes():

        if v["id"] == vid:

            return v["label"]

    if vid.startswith(_USB_PREFIX):

        slug = vid[len(_USB_PREFIX) :].replace("__", "/")

        return t("volume.usb_name_fmt", get_lang(), name=slug)

    return t(

        _VOLUME_KEYS.get(vid, "volume.storage_fallback"),

        get_lang(),

        id=vid,

    )





def resolve_local_path(volume_id: str, subpath: str) -> Path:

    from i18n import get_lang, t



    vid = (volume_id or "1").strip() or "1"

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

    if v in ("1", "2", "ugos"):

        return v

    if v.startswith(_USB_PREFIX):

        for vid, mount, _, _ in _configured_usb_volumes():

            if vid == v and mount.is_dir():

                return v

        return v

    return "1"


