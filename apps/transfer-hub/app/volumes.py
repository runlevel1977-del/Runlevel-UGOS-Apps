# -*- coding: utf-8 -*-
"""Local NAS mounts — user-granted folders only (UGREEN: no whole /volumeN).

Multiple App Center paths are supported (any volume), each mounted under /mnt/ugos*.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from usb_storage import discover_usb_mounts
from volume_discover import discover_ugos_folder_mounts

_USB_ROOT = Path(os.environ.get("NAS_USB_MOUNT", "/mnt/@usb"))
_USB_PREFIX = "usb-"


def _configured_volumes() -> list[tuple[str, Path, str]]:
    return discover_ugos_folder_mounts()


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


def _ugos_label(vid: str, host_hint: str, lng: str) -> str:
    from i18n import t

    base = t("volume.ugos", lng)
    hint = (host_hint or "").strip()
    if vid == "ugos" or not hint:
        return base
    # Distinguish multiple granted folders by host path basename
    short = hint.rstrip("/").split("/")[-1] or hint
    return f"{base} ({short})"


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
                "label": _ugos_label(vid, host_hint, lng),
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
    return t("volume.ugos", get_lang())


class OutsideVolumeError(ValueError):
    """Canonical path is outside the selected volume root."""


def safe_relative(subpath: str) -> str:
    """Volume-relative path. Parent segments and NUL bytes are rejected.

    A leading slash is stripped. Profile paths are relative to the selected
    volume, not host-absolute.
    """
    raw = (subpath or "").replace("\\", "/").strip()
    if "\x00" in raw:
        raise OutsideVolumeError("invalid path")
    raw = raw.lstrip("/")
    if len(raw) >= 2 and raw[1] == ":":
        raise OutsideVolumeError("absolute path")
    parts: list[str] = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise OutsideVolumeError("parent segment")
        parts.append(part)
    return "/".join(parts)


def canonical_path(path: Path) -> Path:
    """Symlink-normalized absolute path."""
    try:
        return Path(os.path.realpath(os.fspath(path)))
    except (OSError, ValueError) as exc:
        raise OutsideVolumeError("path unavailable") from exc


def _within_root(root_real: Path, candidate_real: Path) -> bool:
    """True when candidate is the root or a descendant, after canonicalization."""
    root_s = os.path.normcase(os.path.normpath(os.fspath(root_real)))
    cand_s = os.path.normcase(os.path.normpath(os.fspath(candidate_real)))
    if cand_s == root_s:
        return True
    prefix = root_s.rstrip("\\/") + os.sep
    return cand_s.startswith(prefix)


def contained_join(root: Path, subpath: str) -> Path:
    """Join ``subpath`` onto ``root`` and reject canonical escapes.

    The lexical filter and the realpath check both run. A symlink whose
    target leaves ``root`` is rejected even when the lexical filter is bypassed.
    """
    rel = safe_relative(subpath)
    try:
        if not root.is_dir():
            raise OutsideVolumeError("volume root unavailable")
    except OSError as exc:
        raise OutsideVolumeError("volume root unavailable") from exc
    root_real = canonical_path(root)
    candidate = root_real / rel if rel else root_real
    resolved = canonical_path(candidate)
    if not _within_root(root_real, resolved):
        raise OutsideVolumeError("outside volume")
    return resolved


def _mount_for_volume(volume_id: str) -> Path | None:
    """Selected volume root inside the container, or the first granted pool."""
    vid = (volume_id or "ugos").strip() or "ugos"
    if vid.startswith(_USB_PREFIX):
        for vol_id, mount, _, _ in _configured_usb_volumes():
            if vol_id == vid and mount.is_dir():
                return mount
        return None
    for vol_id, mount, _ in _configured_volumes():
        if vol_id == vid and mount.is_dir():
            return mount
    for _vol_id, mount, _ in _configured_volumes():
        if mount.is_dir():
            return mount
    for _vol_id, mount, _, _ in _configured_usb_volumes():
        if mount.is_dir():
            return mount
    return None


def assert_canonical_under_volume(volume_id: str, parsed_path: str | Path) -> Path:
    """Reject a parsed filesystem path that is outside the selected volume.

    ``parsed_path`` is the string produced for a local endpoint (the result of
    ``rclone_remote_url``). Comparison uses symlink-normalized canonical paths.
    """
    text = os.fspath(parsed_path)
    if "\x00" in text:
        raise OutsideVolumeError("invalid path")
    root = _mount_for_volume(volume_id)
    if root is None:
        raise OutsideVolumeError("volume root unavailable")
    root_real = canonical_path(root)
    resolved = canonical_path(Path(text))
    if not _within_root(root_real, resolved):
        raise OutsideVolumeError("outside volume")
    return resolved


def resolve_local_path(volume_id: str, subpath: str) -> Path:
    """Canonical path of ``subpath`` inside the selected volume root."""
    from i18n import get_lang, t

    vid = (volume_id or "ugos").strip() or "ugos"
    root = _mount_for_volume(vid)
    if root is None:
        if vid.startswith(_USB_PREFIX):
            raise ValueError(t("err.usb_not_mounted", get_lang(), id=vid))
        raise ValueError(t("err.no_storage", get_lang()))
    return contained_join(root, subpath or "")


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
        return sorted(known)[0]
    return "ugos"
