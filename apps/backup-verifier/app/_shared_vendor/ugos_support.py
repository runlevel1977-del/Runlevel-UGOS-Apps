# -*- coding: utf-8 -*-
"""Shared UGOS Web-API helpers for Runlevel Docker apps (same client as NAS Admin)."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ugos_api_client import UgosApiClient, UgosApiError
from ugos_metrics import _pool_list, parse_dashboard_metrics

_cache_lock = threading.Lock()
_cache_at = 0.0
_cache_metrics: dict[str, Any] | None = None
_client: UgosApiClient | None = None
_client_key: tuple[Any, ...] = ()
_CACHE_SEC = 45.0


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _detect_lan_host() -> str:
    """Best-effort NAS IP when container uses bridge network."""
    try:
        proc = subprocess.run(
            ["ip", "-4", "route", "get", "1.1.1.1"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for tok in (proc.stdout or "").split():
            if tok.count(".") == 3 and tok[0].isdigit():
                return tok
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def default_ugos_host() -> str:
    explicit = (os.environ.get("UGOS_API_HOST") or "").strip()
    if explicit:
        return explicit
    if _env_bool("UGOS_API_USE_LOCALHOST", default=False):
        return "127.0.0.1"
    detected = _detect_lan_host()
    return detected or "127.0.0.1"


def normalize_ugos_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {})
    try:
        port = int(data.get("port") or os.environ.get("UGOS_API_PORT") or 9443)
    except (TypeError, ValueError):
        port = 9443
    port = max(1, min(65535, port))
    user = str(data.get("username") or os.environ.get("UGOS_API_USER") or "").strip()
    pw = str(data.get("password") or os.environ.get("UGOS_API_PASSWORD") or "")
    host = str(data.get("host") or default_ugos_host()).strip() or default_ugos_host()
    enabled = data.get("enabled")
    if enabled is None:
        enabled = _env_bool("UGOS_API_ENABLED", default=True)
    return {
        "enabled": bool(enabled),
        "host": host,
        "port": port,
        "username": user,
        "password": pw,
        "use_https": bool(data.get("use_https", _env_bool("UGOS_API_HTTPS", True))),
        "verify_ssl": bool(data.get("verify_ssl", _env_bool("UGOS_API_VERIFY_SSL", False))),
    }


def load_ugos_config(data_dir: Path, embedded: dict[str, Any] | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    cfg_file = data_dir / "ugos_api.json"
    if cfg_file.is_file():
        try:
            raw = json.loads(cfg_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                merged.update(raw)
        except (OSError, json.JSONDecodeError):
            pass
    if isinstance(embedded, dict):
        merged = {**merged, **embedded}
    return normalize_ugos_config(merged)


def save_ugos_config(data_dir: Path, updates: dict[str, Any], *, embedded: dict[str, Any] | None = None) -> dict[str, Any]:
    data_dir.mkdir(parents=True, exist_ok=True)
    cur = load_ugos_config(data_dir, embedded)
    patch = updates or {}
    if "enabled" in patch:
        cur["enabled"] = bool(patch["enabled"])
    if "host" in patch:
        cur["host"] = str(patch["host"] or default_ugos_host()).strip() or default_ugos_host()
    if "port" in patch:
        try:
            cur["port"] = max(1, min(65535, int(patch["port"])))
        except (TypeError, ValueError):
            pass
    if "username" in patch:
        cur["username"] = str(patch["username"] or "").strip()
    if "password" in patch and str(patch["password"] or "").strip():
        cur["password"] = str(patch["password"])
    if "use_https" in patch:
        cur["use_https"] = bool(patch["use_https"])
    if "verify_ssl" in patch:
        cur["verify_ssl"] = bool(patch["verify_ssl"])
    cur = normalize_ugos_config(cur)
    (data_dir / "ugos_api.json").write_text(
        json.dumps(cur, indent=2) + "\n", encoding="utf-8"
    )
    return public_ugos_config(cur)


def public_ugos_config(cfg: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in cfg.items() if k != "password"}
    out["password_set"] = bool(str(cfg.get("password") or ""))
    return out


def _client_for(cfg: dict[str, Any]) -> UgosApiClient:
    global _client, _client_key
    fp = (
        cfg.get("host"),
        int(cfg.get("port") or 9443),
        cfg.get("username"),
        cfg.get("password"),
        bool(cfg.get("use_https", True)),
        bool(cfg.get("verify_ssl", False)),
    )
    with _cache_lock:
        if _client is None or fp != _client_key:
            _client = UgosApiClient(
                host=str(cfg.get("host") or "127.0.0.1"),
                port=int(cfg.get("port") or 9443),
                username=str(cfg.get("username") or ""),
                password=str(cfg.get("password") or ""),
                use_https=bool(cfg.get("use_https", True)),
                verify_ssl=bool(cfg.get("verify_ssl", False)),
            )
            _client_key = fp
        return _client


def fetch_metrics(
    data_dir: Path,
    *,
    embedded: dict[str, Any] | None = None,
    log: Callable[[str], None] | None = None,
    force: bool = False,
) -> dict[str, Any] | None:
    global _cache_at, _cache_metrics, _client
    cfg = load_ugos_config(data_dir, embedded)
    if not cfg.get("enabled"):
        return None
    if not (cfg.get("username") and cfg.get("password")):
        return None
    now = time.time()
    with _cache_lock:
        if not force and _cache_metrics and (now - _cache_at) < _CACHE_SEC:
            return dict(_cache_metrics)
    try:
        client = _client_for(cfg)
        raw = client.fetch_snapshot()
        metrics = parse_dashboard_metrics(raw)
    except UgosApiError as ex:
        if log:
            log(f"UGOS API: {ex}")
        with _cache_lock:
            _client = None
        return None
    except Exception as ex:
        if log:
            log(f"UGOS API error: {ex}")
        return None
    if not metrics.get("ok"):
        return None
    with _cache_lock:
        _cache_metrics = dict(metrics)
        _cache_at = now
    return dict(metrics)


def _host_path_for_volume(vol: dict[str, Any]) -> str:
    mnt = str(vol.get("mntpath") or "").strip().rstrip("/")
    if mnt:
        return mnt
    name = str(vol.get("name") or "").strip()
    if name.isdigit():
        return f"/volume{name}"
    return ""


def enrich_volume_rows(
    rows: list[dict[str, Any]],
    metrics: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not metrics:
        return rows
    by_host: dict[str, dict[str, Any]] = {}
    for pool in metrics.get("pools") or []:
        if not isinstance(pool, dict):
            continue
        for vol in pool.get("volumes") or []:
            if not isinstance(vol, dict):
                continue
            hp = _host_path_for_volume(vol)
            if not hp:
                continue
            by_host[hp.rstrip("/")] = {
                "ugos_name": str(vol.get("name") or "").strip(),
                "ugos_label": str(vol.get("name") or pool.get("name") or "").strip(),
                "used_pct": vol.get("used_pct"),
                "pool": str(pool.get("name") or "").strip(),
            }
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        hint = str(item.get("host_path") or "").strip().rstrip("/")
        meta = by_host.get(hint)
        if meta:
            pct = meta.get("used_pct")
            extra = meta.get("ugos_label") or meta.get("ugos_name")
            if extra and extra not in str(item.get("label") or ""):
                item["label"] = f"{item.get('label', '')} · {extra}".strip(" ·")
            if pct is not None:
                item["ugos_used_pct"] = round(float(pct), 1)
            pool = meta.get("pool")
            if pool:
                item["ugos_pool"] = pool
            item["ugos_ok"] = True
        out.append(item)
    return out


def list_volumes_with_ugos(
    base_fn: Callable[[], list[dict[str, Any]]],
    data_dir: Path,
    *,
    embedded: dict[str, Any] | None = None,
    log: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    rows = base_fn()
    metrics = fetch_metrics(data_dir, embedded=embedded, log=log)
    return enrich_volume_rows(rows, metrics)
