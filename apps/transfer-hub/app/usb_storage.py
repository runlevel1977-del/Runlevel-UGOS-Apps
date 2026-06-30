# -*- coding: utf-8 -*-
"""USB / removable storage discovery inside the Transfer Hub container."""
from __future__ import annotations

import os
import posixpath
import re
import subprocess
from pathlib import Path
from typing import Any

_USB_SKIP_HOTPLUG = re.compile(r"^/(?:volume\d+|Volumes)(?:/|$)", re.I)
_USB_MOUNT_INTERNAL = re.compile(
    r"^/$"
    r"|^/(proc|sys|dev|Volumes|lost\+found|runtimes)(/|$)"
    r"|^/mnt/dm-[0-9]+(/|$)"
    r"|^/volume[0-9]+$"
    r"|^/run/docker"
    r"|^/snap(/|$)",
    re.I,
)
_USB_DEV_SKIP = re.compile(r"^/dev/(loop|dm-|md|mtdblock|mtd|zram)", re.I)
_USB_HINT_PATH = re.compile(
    r"(^|/)@usb(/|$)"
    r"|volumeusb|(^|[^a-z])usb([^a-z]|$)"
    r"|/[Uu]sb"
    r"|/[Mm]edia/|/[Rr]un/media/"
    r"|/[Vv]olumes/"
    r"|/[Uu]green|\.ugreen|ugreen_usb|external_vol|externaldisk|removabledisk",
    re.I,
)
_SKIP_FSTYPES = frozenset(
    {
        "tmpfs",
        "devtmpfs",
        "proc",
        "sysfs",
        "cgroup2",
        "cgroup",
        "overlay",
        "squashfs",
        "overlayfs",
        "autofs",
    }
)
_MOBILE_FS = frozenset(
    {"vfat", "msdos", "exfat", "ntfs", "fuseblk", "iso9660", "udf"}
)


def parse_lsblk_pair_line(line: str) -> dict[str, str]:
    line = line or ""
    try:
        return dict(re.findall(r'([A-Za-z0-9_]+)="([^"]*)"', line))
    except Exception:
        return {}


def _mount_path_is_ugos_usb_storage(mp: str) -> bool:
    s = str(mp or "").strip().lower()
    return "@usb" in s or s.startswith("/mnt/@usb")


def _split_proc_mount_line(line: str) -> list[str]:
    line = (line or "").strip()
    if not line:
        return []
    parts: list[str] = []
    cur: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == " ":
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        if c == "\\" and i + 1 < n and line[i + 1] in "01234567":
            j = i + 1
            octs = ""
            while j < n and len(octs) < 3 and line[j] in "01234567":
                octs += line[j]
                j += 1
            if octs:
                cur.append(chr(int(octs, 8)))
                i = j
                continue
        cur.append(c)
        i += 1
    parts.append("".join(cur))
    return parts if len(parts) >= 3 else []


def _run_text(cmd: list[str], timeout: float = 20.0) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            return ""
        return proc.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _read_proc_mounts() -> str:
    try:
        return Path("/proc/mounts").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _norm_mount(mp: str) -> str:
    return posixpath.normpath(str(mp or "").strip().rstrip("/") or "/")


def _mount_under_usb_root(mount: str, usb_root: Path) -> bool:
    mp = _norm_mount(mount)
    root = _norm_mount(str(usb_root))
    return mp == root or mp.startswith(root + "/")


def _is_block_usb_device(dev: str) -> bool:
    dev = (dev or "").strip()
    return bool(dev.startswith("/dev/") and not _USB_DEV_SKIP.match(dev))


def _path_is_mountpoint(path: Path) -> bool:
    """True when path is its own mount (st_dev differs from parent)."""
    try:
        if not path.is_dir():
            return False
        parent = path.parent
        if parent == path:
            return False
        return os.stat(path, follow_symlinks=False).st_dev != os.stat(
            parent, follow_symlinks=False
        ).st_dev
    except OSError:
        return False


def _findmnt_target(path: Path) -> dict[str, str] | None:
    out = _run_text(
        ["findmnt", "-Pno", "SOURCE,TARGET,FSTYPE", str(path)],
        timeout=8.0,
    )
    for raw in (out or "").replace("\r", "").splitlines():
        ln = raw.strip()
        if not ln or "TARGET=" not in ln:
            continue
        kv = parse_lsblk_pair_line(ln)
        tgt = _norm_mount(kv.get("TARGET") or "")
        if tgt != _norm_mount(str(path)):
            continue
        src = (kv.get("SOURCE") or "").strip()
        if not _is_block_usb_device(src):
            return None
        fst = (kv.get("FSTYPE") or "").strip().lower()
        if fst in _SKIP_FSTYPES:
            return None
        return {"device": src, "target": tgt, "fstype": fst, "source": "findmnt"}
    return None


def _lsblk_by_mountpoint() -> dict[str, dict[str, str]]:
    """Map normalized mountpoint -> lsblk metadata."""
    text = _run_text(
        ["lsblk", "-P", "-o", "NAME,MODEL,SIZE,MOUNTPOINT,TRAN,HOTPLUG"],
        timeout=15.0,
    )
    out: dict[str, dict[str, str]] = {}
    for raw in (text or "").replace("\r", "").splitlines():
        ln = raw.strip()
        if not ln or "MOUNTPOINT=" not in ln:
            continue
        kv = parse_lsblk_pair_line(ln)
        mp = _norm_mount(kv.get("MOUNTPOINT") or "")
        if mp == "/" or not mp:
            continue
        out[mp] = {
            "size": (kv.get("SIZE") or "").strip(),
            "model": (kv.get("MODEL") or "").strip(),
            "tran": (kv.get("TRAN") or "").strip().lower(),
        }
    return out


def _collect_active_usb_mounts(usb_root: Path) -> dict[str, dict[str, str]]:
    """
    Only kernel-active mounts under ``usb_root`` (ignores leftover empty dirs
    UGOS sometimes keeps after swapping USB sticks).
    """
    root = _norm_mount(str(usb_root))
    active: dict[str, dict[str, str]] = {}

    for line in _read_proc_mounts().splitlines():
        sp = _split_proc_mount_line(line)
        if len(sp) < 3:
            continue
        dev, mp, fst = sp[0], sp[1], sp[2]
        mp_n = _norm_mount(mp)
        if mp_n == root or not _mount_under_usb_root(mp_n, usb_root):
            continue
        if not _is_block_usb_device(dev):
            continue
        if fst.lower() in _SKIP_FSTYPES:
            continue
        active[mp_n] = {
            "mount": mp_n,
            "device": dev,
            "fstype": fst.lower(),
            "source": "proc_mounts",
        }

    findmnt = _run_text(
        ["findmnt", "-Pnr", "-R", "-o", "SOURCE,TARGET,FSTYPE", str(usb_root)],
        timeout=12.0,
    )
    for raw in (findmnt or "").replace("\r", "").splitlines():
        ln = raw.strip()
        if not ln or "TARGET=" not in ln:
            continue
        kv = parse_lsblk_pair_line(ln)
        tgt = _norm_mount(kv.get("TARGET") or "")
        src = (kv.get("SOURCE") or "").strip()
        fst = (kv.get("FSTYPE") or "").strip().lower()
        if tgt == root or not _mount_under_usb_root(tgt, usb_root):
            continue
        if not _is_block_usb_device(src) or fst in _SKIP_FSTYPES:
            continue
        prev = active.get(tgt)
        if prev is None:
            active[tgt] = {
                "mount": tgt,
                "device": src,
                "fstype": fst,
                "source": "findmnt",
            }

    # Fallback: directory is a mountpoint but missing from proc (rare bind edge cases).
    if usb_root.is_dir():
        try:
            children = sorted(usb_root.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            children = []
        for child in children:
            if not child.is_dir() or child.name.startswith("."):
                continue
            mp_n = _norm_mount(str(child))
            if mp_n in active:
                continue
            if not _path_is_mountpoint(child):
                continue
            row = _findmnt_target(child)
            if not row:
                continue
            active[mp_n] = {
                "mount": mp_n,
                "device": row["device"],
                "fstype": row["fstype"],
                "source": row["source"],
            }

    return active


def _df_size_human(mount: Path) -> str:
    proc = _run_text(["df", "-hP", str(mount)], timeout=10.0)
    mp = str(mount)
    for line in proc.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[-1] == mp:
            fs = parts[0]
            if fs.startswith("/dev/"):
                return parts[1]
    return "—"


def _mount_is_live(path: Path) -> bool:
    """Reject stale directories: must answer df with a block device."""
    proc = _run_text(["df", "-P", str(path)], timeout=8.0)
    mp = str(path)
    for line in proc.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[-1] == mp:
            return parts[0].startswith("/dev/")
    return False


def discover_usb_mounts(usb_root: Path | None = None) -> list[dict[str, Any]]:
    """Return actively mounted USB volumes under ``/mnt/@usb/…``."""
    root = usb_root or Path(os.environ.get("NAS_USB_MOUNT", "/mnt/@usb"))
    if not root.is_dir():
        return []

    active = _collect_active_usb_mounts(root)
    if not active:
        return []

    lsblk_map = _lsblk_by_mountpoint()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for mp_n in sorted(active.keys(), key=str.casefold):
        path = Path(mp_n)
        if not path.is_dir():
            continue
        try:
            if not os.access(path, os.R_OK | os.X_OK):
                continue
        except OSError:
            continue
        if not _mount_is_live(path):
            continue
        try:
            key = str(path.resolve())
        except OSError:
            key = mp_n
        if key in seen:
            continue
        seen.add(key)

        meta = active[mp_n]
        blk = lsblk_map.get(mp_n, {})
        size = (blk.get("size") or "").strip() or _df_size_human(path)
        model = (blk.get("model") or "").strip()
        if not model:
            model = Path(meta.get("device") or path.name).name or path.name
        if model in ("", "—"):
            model = path.name

        out.append(
            {
                "mount": str(path),
                "host_mount": mp_n,
                "size": size or "—",
                "model": model,
                "device": meta.get("device") or "",
                "fstype": meta.get("fstype") or "",
                "source": meta.get("source") or "",
            }
        )
    return out
