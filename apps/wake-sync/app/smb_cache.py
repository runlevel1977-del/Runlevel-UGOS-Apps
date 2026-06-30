# -*- coding: utf-8 -*-
"""Offline SMB folder tree — built while target NAS is online."""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from store import DATA_DIR, append_log

CACHE_DIR = DATA_DIR / "smb_cache"
DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_NODES = 400
DEFAULT_MAX_SECONDS = 90.0

_status_lock = threading.Lock()
_build_status: dict[str, dict[str, Any]] = {}
_build_threads: dict[str, threading.Thread] = {}


def _cache_file(device_id: str) -> Path:
    return CACHE_DIR / f"{device_id}.json"


def load_smb_cache(device_id: str) -> dict[str, Any] | None:
    path = _cache_file(device_id)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else None


def save_smb_cache(device_id: str, data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _cache_file(device_id).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def delete_smb_cache(device_id: str) -> None:
    try:
        _cache_file(device_id).unlink()
    except OSError:
        pass
    clear_build_status(device_id)


def cache_key(share: str, subpath: str) -> str:
    share = (share or "").strip()
    sub = (subpath or "").strip().strip("/")
    return share if not sub else f"{share}/{sub}"


def cache_summary(device_id: str) -> dict[str, Any]:
    cache = load_smb_cache(device_id)
    status = get_build_status(device_id)
    if not cache:
        return {
            "ready": False,
            "cached_at": "",
            "share_count": 0,
            "dir_levels": 0,
            "building": status.get("state") == "building",
            "partial": False,
        }
    dirs = cache.get("dirs") or {}
    return {
        "ready": bool(cache.get("shares")),
        "cached_at": cache.get("cached_at") or "",
        "share_count": len(cache.get("shares") or []),
        "dir_levels": len(dirs),
        "building": status.get("state") == "building",
        "partial": bool(cache.get("partial")),
    }


def get_build_status(device_id: str) -> dict[str, Any]:
    with _status_lock:
        st = _build_status.get(device_id)
        if st:
            return dict(st)
    summary = load_smb_cache(device_id)
    if summary and summary.get("shares"):
        return {"state": "ready", "error": "", "dir_levels": len(summary.get("dirs") or {})}
    return {"state": "idle", "error": "", "dir_levels": 0}


def clear_build_status(device_id: str) -> None:
    with _status_lock:
        _build_status.pop(device_id, None)
        _build_threads.pop(device_id, None)


def _set_build_status(device_id: str, **fields: Any) -> None:
    with _status_lock:
        cur = dict(_build_status.get(device_id) or {})
        cur.update(fields)
        _build_status[device_id] = cur


def new_cache() -> dict[str, Any]:
    return {
        "cached_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "shares": [],
        "dirs": {},
    }


def update_cache_shares(device_id: str, share_names: list[str]) -> None:
    cache = load_smb_cache(device_id) or new_cache()
    cache["shares"] = sorted({s for s in share_names if s}, key=str.lower)
    cache["cached_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    save_smb_cache(device_id, cache)


def update_cache_dirs(device_id: str, share: str, subpath: str, dir_names: list[str]) -> None:
    cache = load_smb_cache(device_id) or new_cache()
    key = cache_key(share, subpath)
    cache["dirs"][key] = sorted({n for n in dir_names if n}, key=str.lower)
    cache["cached_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    save_smb_cache(device_id, cache)


def shares_from_cache(cache: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"name": name, "path": name, "kind": "share"}
        for name in (cache.get("shares") or [])
    ]


def dirs_from_cache(cache: dict[str, Any], share: str, subpath: str) -> list[dict[str, str]]:
    key = cache_key(share, subpath)
    names = (cache.get("dirs") or {}).get(key)
    if names is None:
        return []
    rel = (subpath or "").strip().strip("/")
    out: list[dict[str, str]] = []
    for name in names:
        child = f"{rel}/{name}".strip("/") if rel else name
        out.append({"name": name, "path": child, "kind": "dir"})
    return out


def build_smb_cache(
    device: dict[str, Any],
    list_shares_fn,
    list_dirs_fn,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    device_id: str | None = None,
    progress_cb: Callable[[int], None] | None = None,
) -> tuple[bool, str]:
    """Scan SMB tree while NAS is online."""
    device_id = device_id or device.get("id") or ""
    if not device_id:
        return False, "device id missing"

    started = time.monotonic()
    shares, ok = list_shares_fn(device)
    if not ok:
        return False, "SMB unreachable"
    if not shares:
        return False, "no shares"

    cache = new_cache()
    cache["shares"] = [s["name"] for s in shares]
    counter = [0]
    timed_out = [False]

    def scan_share(share_name: str, subpath: str, depth: int) -> None:
        if timed_out[0] or counter[0] >= max_nodes or depth > max_depth:
            return
        if time.monotonic() - started > max_seconds:
            timed_out[0] = True
            return
        dirs, dir_ok = list_dirs_fn(device, share_name, subpath)
        if not dir_ok:
            return
        key = cache_key(share_name, subpath)
        cache["dirs"][key] = [d["name"] for d in dirs]
        counter[0] += 1
        if progress_cb:
            progress_cb(counter[0])
        for d in dirs:
            if timed_out[0]:
                break
            scan_share(share_name, d["path"], depth + 1)

    for share in shares:
        if timed_out[0]:
            break
        scan_share(share["name"], "", 0)

    if not cache["dirs"] and not cache["shares"]:
        return False, "empty cache"

    cache["partial"] = timed_out[0] or counter[0] >= max_nodes
    save_smb_cache(device_id, cache)
    note = "partial" if cache["partial"] else "complete"
    append_log(
        f"Folder cache saved ({note}) for {device.get('name', device_id)}: "
        f"{len(cache['shares'])} share(s), {len(cache['dirs'])} level(s)"
    )
    return True, "partial" if cache["partial"] else "ok"


def start_smb_cache_build(device: dict[str, Any], list_shares_fn, list_dirs_fn) -> bool:
    """Start cache build in a background thread. Returns False if already running."""
    device_id = device.get("id") or ""
    if not device_id:
        return False

    with _status_lock:
        if device_id in _build_threads and _build_threads[device_id].is_alive():
            return False
        _build_status[device_id] = {"state": "building", "error": "", "dir_levels": 0}

    def worker() -> None:
        try:
            ok, msg = build_smb_cache(
                device,
                list_shares_fn,
                list_dirs_fn,
                device_id=device_id,
                progress_cb=lambda n: _set_build_status(device_id, dir_levels=n),
            )
            if ok:
                _set_build_status(device_id, state="ready", error="", dir_levels=0)
            else:
                _set_build_status(device_id, state="failed", error=msg)
        except Exception as e:
            append_log(f"Folder cache build error ({device_id}): {e}")
            _set_build_status(device_id, state="failed", error=str(e))

    thread = threading.Thread(target=worker, daemon=True, name=f"smb-cache-{device_id}")
    with _status_lock:
        _build_threads[device_id] = thread
    thread.start()
    return True
