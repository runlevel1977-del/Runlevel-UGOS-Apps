# -*- coding: utf-8 -*-
"""Discover real NAS storage volumes (any count) without inventing empty ones.

Rules:
- Only report /volumeN that are real mountpoints (or reachable via host pid namespace).
- Never invent Volume 3+ placeholders.
- Docker bind-mounts of missing host paths create empty dirs — those fail the
  mountpoint check (same st_dev as parent) and stay hidden.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

_VOL_MP = re.compile(r"^/volume(\d+)$", re.I)
_DEFAULT_MAX = 32


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def volume_numbers_from_mountinfo(*paths: str) -> list[int]:
    """Parse mountinfo files for mount targets /volumeN."""
    found: set[int] = set()
    candidates = paths or (
        "/proc/1/mountinfo",
        "/proc/self/mountinfo",
        "/proc/mounts",
    )
    for path in candidates:
        text = _read_text(path)
        if not text:
            continue
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            # mountinfo: mountpoint is field 5; /proc/mounts: field 2
            if path.endswith("mounts") and not path.endswith("mountinfo"):
                mp = parts[1] if len(parts) > 1 else ""
            else:
                mp = parts[4]
            m = _VOL_MP.match(mp.rstrip("/") or mp)
            if m:
                found.add(int(m.group(1)))
    return sorted(found)


def is_real_mountpoint(path: Path | str) -> bool:
    """True if path exists and is a distinct filesystem from its parent."""
    p = Path(path)
    try:
        if not p.is_dir():
            return False
        # Compare device ids — bind-created empty dirs share the parent device.
        return p.stat().st_dev != p.parent.stat().st_dev
    except OSError:
        return False


def candidate_paths_for_volume(n: int) -> list[Path]:
    """Ordered places where volume N may appear inside the container."""
    env_key = f"NAS_VOL{n}_MOUNT"
    env = (os.environ.get(env_key) or "").strip()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            Path(f"/volume{n}"),
            Path(f"/mnt/vol{n}"),
            Path(f"/proc/1/root/volume{n}"),
        ]
    )
    # de-dupe preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def resolve_volume_path(n: int) -> Path | None:
    """Return a usable container path for /volumeN, or None if not really present."""
    for p in candidate_paths_for_volume(n):
        if is_real_mountpoint(p):
            return p
    return None


def discover_pool_volumes(max_n: int | None = None) -> list[tuple[str, Path, str]]:
    """Return (id, container_path, host_hint) for every real pool volume.

    ``id`` is the decimal string ("1", "2", "3", …).
    ``host_hint`` is the host path ``/volumeN``.
    """
    limit = int(max_n or int(os.environ.get("NAS_VOLUME_MAX", _DEFAULT_MAX) or _DEFAULT_MAX))
    limit = max(1, min(64, limit))

    numbers = set(volume_numbers_from_mountinfo())
    # Also probe 1..limit in case mountinfo is restricted but binds exist
    numbers.update(range(1, limit + 1))

    rows: list[tuple[str, Path, str]] = []
    for n in sorted(numbers):
        if n < 1 or n > limit:
            continue
        path = resolve_volume_path(n)
        if path is None:
            continue
        rows.append((str(n), path, f"/volume{n}"))
    return rows


def discover_ugos_folder_mounts(
    base: str = "/mnt/ugos",
    host_hints_env: str = "NAS_DATA_ROOT_HOST",
) -> list[tuple[str, Path, str]]:
    """User-granted UGOS folders (Transfer Hub style).

    Supports:
    - single ``NAS_UGOS_MOUNT=/mnt/ugos``
    - multi ``/mnt/ugos0``, ``/mnt/ugos1``, … from compose range mounts
    - ``NAS_UGOS_MOUNTS`` colon/comma-separated override
    """
    rows: list[tuple[str, Path, str]] = []
    seen: set[str] = set()

    def _add(vid: str, mount: Path, hint: str) -> None:
        try:
            if not mount.is_dir():
                return
            key = str(mount.resolve())
        except OSError:
            key = str(mount)
            if not mount.is_dir():
                return
        if key in seen:
            return
        seen.add(key)
        rows.append((vid, mount, hint))

    explicit = (os.environ.get("NAS_UGOS_MOUNTS") or "").strip()
    hints = [
        h.strip()
        for h in re.split(r"[,;]", os.environ.get(host_hints_env, "") or "")
        if h.strip()
    ]

    if explicit:
        mounts = [Path(p.strip()) for p in re.split(r"[:;,]", explicit) if p.strip()]
        for i, mp in enumerate(mounts):
            hint = hints[i] if i < len(hints) else (hints[0] if hints else str(mp))
            vid = "ugos" if i == 0 and len(mounts) == 1 else f"ugos-{i}"
            _add(vid, mp, hint)
        return rows

    primary = Path(os.environ.get("NAS_UGOS_MOUNT", base))
    _add("ugos", primary, hints[0] if hints else os.environ.get(host_hints_env, "UGOS selection"))

    # Multi-bind siblings: /mnt/ugos0, /mnt/ugos1, … or /mnt/ugos_0
    parent = primary.parent if primary != Path("/") else Path("/mnt")
    stem = primary.name  # ugos
    extras: list[Path] = []
    try:
        for child in sorted(parent.iterdir()):
            name = child.name
            if name == stem:
                continue
            if name.startswith(stem) and (
                name[len(stem) :].isdigit()
                or (name[len(stem) :].startswith("_") and name[len(stem) + 1 :].isdigit())
                or (name[len(stem) :].startswith("-") and name[len(stem) + 1 :].isdigit())
            ):
                extras.append(child)
    except OSError:
        extras = []

    # Also probe ugos0..ugos31 explicitly (dir may exist before listdir works)
    for i in range(32):
        for cand in (parent / f"{stem}{i}", parent / f"{stem}_{i}", parent / f"{stem}-{i}"):
            if cand not in extras and cand != primary:
                extras.append(cand)

    hint_i = 1
    for i, mp in enumerate(extras):
        if not mp.is_dir():
            continue
        hint = hints[hint_i] if hint_i < len(hints) else (hints[-1] if hints else str(mp))
        _add(f"ugos-{i}", mp, hint)
        hint_i += 1

    return rows


def parse_host_hint_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [h.strip() for h in re.split(r"[,;]", raw) if h.strip()]
