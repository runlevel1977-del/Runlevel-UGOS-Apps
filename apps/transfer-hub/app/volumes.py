# -*- coding: utf-8 -*-
"""Local NAS volume mounts inside the container."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from usb_storage import discover_usb_mounts

# UGOS path picker — only the folder the user chose at install (UGREEN: no whole /home or /volumeN)
_UGOS = Path(os.environ.get("NAS_UGOS_MOUNT", "/mnt/ugos"))
_USB_ROOT = Path(os.environ.get("NAS_USB_MOUNT", "/mnt/@usb"))

_VOLUME_KEYS = {
    "ugos": "volume.ugos",
}
_USB_PREFIX = "usb-"
_KNOWN_POOL_IDS = frozenset({"ugos"})


class OutsideVolumeError(ValueError):
    """Raised when a local path leaves the selected volume mount."""


def safe_relative(subpath: str) -> str:
    """Return a relative path with no parent or absolute segments.

    Args:
        subpath: User-supplied folder path inside a volume.

    Returns:
        Normalized relative path. Empty means the volume root.

    Raises:
        OutsideVolumeError: The path is absolute, contains ``..``, or a NUL.
    """
    raw = (subpath or "").replace("\\", "/").strip()
    if "\x00" in raw:
        raise OutsideVolumeError("path outside volume")
    raw = raw.strip("/")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise OutsideVolumeError("path outside volume")
    return "/".join(parts)


def _is_within(child: Path, root: Path) -> bool:
    try:
        child.relative_to(root)
    except ValueError:
        return False
    return True


def contained_join(root: Path, subpath: str) -> Path:
    """Join ``subpath`` under ``root`` and reject escapes after ``resolve()``.

    Args:
        root: Volume mount inside the container.
        subpath: Relative folder under that mount.

    Returns:
        Resolved path that stays inside ``root``.

    Raises:
        OutsideVolumeError: The path leaves the mount or uses a symlink.
    """
    rel = safe_relative(subpath)
    try:
        root_real = root.resolve()
    except OSError as exc:
        raise OutsideVolumeError("path outside volume") from exc
    candidate = root_real.joinpath(*rel.split("/")) if rel else root_real
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise OutsideVolumeError("path outside volume") from exc
    if not _is_within(resolved, root_real):
        raise OutsideVolumeError("path outside volume")
    cursor = root_real
    if rel:
        for part in rel.split("/"):
            cursor = cursor / part
            if cursor.is_symlink():
                raise OutsideVolumeError("path outside volume")
            if not cursor.exists():
                break
    return resolved


def _configured_volumes() -> list[tuple[str, Path, str]]:
    """(id, container_path, host_hint)."""
    return [
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
        out.append(
            {
                "id": vid,
                "label": t(_VOLUME_KEYS.get(vid, "volume.storage_fallback"), lng, id=vid),
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
                "usb_size": meta.get("size") or "",
                "usb_model": meta.get("model") or "",
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
    return t(
        _VOLUME_KEYS.get(vid, "volume.storage_fallback"),
        get_lang(),
        id=vid,
    )


def resolve_local_path(volume_id: str, subpath: str) -> Path:
    from i18n import get_lang, t

    vid = (volume_id or "ugos").strip() or "ugos"
    rel = safe_relative(subpath)

    if vid.startswith(_USB_PREFIX):
        for v, mount, _, _ in _configured_usb_volumes():
            if v == vid and mount.is_dir():
                return contained_join(mount, rel)
        raise ValueError(t("err.usb_not_mounted", get_lang(), id=vid))

    for v, mount, _ in _configured_volumes():
        if v == vid and mount.is_dir():
            return contained_join(mount, rel)

    mounts = list_volumes()
    if mounts:
        return contained_join(Path(mounts[0]["mount"]), rel)
    raise ValueError(t("err.no_storage", get_lang()))


def normalize_volume_id(volume_id: str | None) -> str:
    v = (volume_id or "").strip()
    if v in _KNOWN_POOL_IDS:
        return v
    if v.startswith(_USB_PREFIX):
        for vid, mount, _, _ in _configured_usb_volumes():
            if vid == v and mount.is_dir():
                return v
        return v
    return "ugos"
