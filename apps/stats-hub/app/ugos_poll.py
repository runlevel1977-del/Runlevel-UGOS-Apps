# -*- coding: utf-8 -*-
"""UGOS Web-API polling for Stats Hub (same client as Ugreen NAS Admin)."""
from __future__ import annotations

import posixpath
import re
import threading
import time
from typing import Any

from collect import fmt_rate, fmt_size_1k, mount_sort_key
from settings import load_ugos_api_settings
from store import append_log
from ugos_api_client import UgosApiClient, UgosApiError
from ugos_metrics import parse_dashboard_metrics

_client_lock = threading.Lock()
_client: UgosApiClient | None = None
_client_key: tuple[Any, ...] = ()
_last_error = ""
_last_ok_at = 0.0
_MIN_INTERVAL_SEC = 2.5
_last_ugos_volumes: list[dict[str, Any]] = []
_VOL_NAME = re.compile(r"^volume(\d+)$", re.I)


def normalize_volume_path(path: str, name: str = "") -> str:
    """UGOS names like ``volume1`` → ``/volume1`` (same keys as host df)."""
    raw = (path or name or "").strip()
    if not raw:
        return ""
    if raw.isdigit():
        return f"/volume{raw}"
    m = _VOL_NAME.match(raw)
    if m:
        return f"/volume{m.group(1)}"
    p = posixpath.normpath(raw)
    if not p.startswith("/"):
        m2 = _VOL_NAME.match(p)
        if m2:
            return f"/volume{m2.group(1)}"
    return p


def last_ugos_volumes() -> list[dict[str, Any]]:
    return list(_last_ugos_volumes)


def set_last_ugos_volumes(rows: list[dict[str, Any]]) -> None:
    global _last_ugos_volumes
    _last_ugos_volumes = list(rows)


def _client_fingerprint(cfg: dict[str, Any]) -> tuple[Any, ...]:
    return (
        cfg.get("host"),
        int(cfg.get("port") or 9443),
        cfg.get("username"),
        cfg.get("password"),
        bool(cfg.get("use_https", True)),
        bool(cfg.get("verify_ssl", False)),
    )


def _get_client(cfg: dict[str, Any]) -> UgosApiClient:
    global _client, _client_key
    fp = _client_fingerprint(cfg)
    with _client_lock:
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


def last_ugos_status() -> dict[str, Any]:
    return {
        "ugos_ok": bool(_last_ok_at),
        "ugos_error": _last_error,
        "ugos_last_ok": int(_last_ok_at) if _last_ok_at else None,
    }


def ugos_volumes_to_snapshot(volume_usage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for v in volume_usage:
        if not isinstance(v, dict):
            continue
        mnt = str(v.get("mntpath") or v.get("mount") or "").strip()
        name = str(v.get("name") or "").strip()
        path = normalize_volume_path(mnt, name)
        if not path:
            continue
        try:
            pct = float(v.get("used_pct") or 0)
        except (TypeError, ValueError):
            continue
        used_1k = 0
        total_1k = 0
        try:
            used_b = float(v.get("used") or v.get("used_bytes") or 0)
            total_b = float(v.get("total") or v.get("total_bytes") or 0)
            if total_b > 0:
                used_1k = int(used_b / 1024)
                total_1k = int(total_b / 1024)
        except (TypeError, ValueError):
            pass
        rows.append(
            {
                "path": path,
                "pct": round(pct, 1),
                "used_1k": used_1k,
                "total_1k": total_1k,
                "used_h": fmt_size_1k(used_1k) if used_1k else "—",
                "total_h": fmt_size_1k(total_1k) if total_1k else "—",
            }
        )
    return sorted(rows, key=lambda r: mount_sort_key(str(r["path"])))


def merge_volumes(
    host_vols: list[dict[str, Any]], ugos_vols: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Host ``df`` rows are canonical; UGOS only refreshes used % (no extra rows)."""
    if not host_vols:
        return ugos_vols
    if not ugos_vols:
        return host_vols
    by_path: dict[str, dict[str, Any]] = {}
    for v in host_vols:
        key = normalize_volume_path(str(v.get("path") or ""))
        if key:
            by_path[key] = dict(v)
    for u in ugos_vols:
        key = normalize_volume_path(str(u.get("path") or ""))
        if not key:
            continue
        cur = by_path.get(key)
        if not cur:
            continue
        if u.get("pct") is not None:
            cur["pct"] = u["pct"]
        if (cur.get("used_h") or "—") == "—" and (u.get("used_h") or "—") != "—":
            cur["used_h"] = u["used_h"]
            cur["total_h"] = u.get("total_h", "—")
            cur["used_1k"] = u.get("used_1k", 0)
            cur["total_1k"] = u.get("total_1k", 0)
    return sorted(by_path.values(), key=lambda r: mount_sort_key(str(r["path"])))


def merge_ifaces(
    host_ifaces: list[dict[str, Any]], ugos_ifaces: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not ugos_ifaces:
        return host_ifaces
    host_by_name = {str(i.get("name") or ""): i for i in host_ifaces if i.get("name")}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for u in ugos_ifaces:
        if not isinstance(u, dict):
            continue
        name = str(u.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        h = host_by_name.get(name, {})
        rx = u.get("recv_bps")
        tx = u.get("send_bps")
        connected = u.get("connected", True)
        state = h.get("state") or ("up" if connected else "down")
        out.append(
            {
                "name": name,
                "rx_bps": rx,
                "tx_bps": tx,
                "rx_h": fmt_rate(rx) if rx is not None else h.get("rx_h", "—"),
                "tx_h": fmt_rate(tx) if tx is not None else h.get("tx_h", "—"),
                "state": state,
                "mac": h.get("mac", ""),
                "addrs": list(h.get("addrs") or []),
                "default_route": bool(h.get("default_route")),
                "gateway": h.get("gateway", ""),
            }
        )
    for h in host_ifaces:
        name = str(h.get("name") or "")
        if name and name not in seen:
            out.append(h)
    return out


def ugos_disks_to_temps(disks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Supplement SMART temps from UGOS disk list when host smartctl is empty."""
    out: list[dict[str, Any]] = []
    for d in disks:
        if not isinstance(d, dict):
            continue
        temp = d.get("temp_c")
        if temp is None:
            continue
        label = str(d.get("label") or "").strip()
        name = str(d.get("name") or "?").strip()
        out.append(
            {
                "name": name,
                "label": label or name,
                "temp_c": temp,
                "health": "ok",
                "device": "",
                "model": str(d.get("model") or ""),
                "standby": False,
            }
        )
    return out


def fetch_ugos_metrics(*, force: bool = False) -> dict[str, Any] | None:
    """Return parsed dashboard metrics or None if disabled/unconfigured."""
    global _last_error, _last_ok_at
    cfg = load_ugos_api_settings()
    if not cfg.get("enabled"):
        return None
    if not (cfg.get("username") and cfg.get("password")):
        _last_error = "credentials_missing"
        return None
    now = time.time()
    if not force and _last_ok_at and (now - _last_ok_at) < _MIN_INTERVAL_SEC:
        return {"ok": True, "cached": True}

    try:
        client = _get_client(cfg)
        raw = client.fetch_snapshot()
        metrics = parse_dashboard_metrics(raw)
    except UgosApiError as ex:
        _last_error = str(ex)[:200]
        append_log(f"UGOS API: {ex}")
        with _client_lock:
            global _client
            _client = None
        return None
    except Exception as ex:
        _last_error = str(ex)[:200]
        append_log(f"UGOS API error: {ex}")
        return None

    if not metrics.get("ok"):
        _last_error = "no_metrics"
        return None

    _last_error = ""
    _last_ok_at = now
    append_log("UGOS API snapshot OK")
    return metrics
