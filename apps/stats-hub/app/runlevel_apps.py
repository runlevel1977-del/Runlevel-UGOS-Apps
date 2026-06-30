# -*- coding: utf-8 -*-
"""Probe Runlevel UGOS apps on localhost (host network)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

# All six Runlevel Docker apps — ports match project.yaml / compose.
RUNLEVEL_APPS: list[dict[str, Any]] = [
    {
        "id": "com.runlevel.statshub",
        "name": "Stats Hub",
        "port": 29125,
        "summary_path": "/api/snapshot",
        "kind": "snapshot",
        "self": True,
    },
    {
        "id": "com.runlevel.backupverifier",
        "name": "Backup Verifier",
        "port": 29110,
        "summary_path": "/api/jobs",
        "kind": "jobs",
    },
    {
        "id": "com.runlevel.transferhub",
        "name": "Transfer Hub",
        "port": 29100,
        "summary_path": "/api/profiles",
        "kind": "profiles",
    },
    {
        "id": "com.runlevel.securityhub",
        "name": "Security Hub",
        "port": 29130,
        "summary_path": "/api/events",
        "kind": "security",
    },
    {
        "id": "com.runlevel.wakesync",
        "name": "Wake & Sync",
        "port": 29120,
        "summary_path": "/api/plans",
        "kind": "plans",
    },
    {
        "id": "com.runlevel.lockandkey",
        "name": "Lock & Key",
        "port": 29135,
        "summary_path": "/api/vaults",
        "kind": "vaults",
    },
]


def _http_json(port: int, path: str, timeout: float = 2.5) -> tuple[bool, Any]:
    url = f"http://127.0.0.1:{port}{path}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return True, json.loads(raw) if raw.strip() else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return False, None


def _pick_latest(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_ts = ""
    for it in items:
        lr = str(it.get("last_run") or it.get("last_run_date") or "")
        if lr >= best_ts:
            best_ts = lr
            best = it
    return best


def _status_from_last(st: str | None) -> str:
    s = (st or "").strip().lower()
    if not s or s in ("ok", "success", "done", "skipped"):
        return "ok"
    if s in ("running", "pending", "busy"):
        return "warn"
    return "bad"


def _as_float(val: object) -> float | None:
    try:
        if val is None:
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _summarize_snapshot(data: Any) -> tuple[str, str, str]:
    if not isinstance(data, dict):
        return "—", "", "ok"
    snap = data.get("snapshot") if isinstance(data.get("snapshot"), dict) else data
    if not isinstance(snap, dict):
        return "—", "", "ok"
    parts: list[str] = []
    cpu = _as_float(snap.get("cpu"))
    ram = _as_float(snap.get("ram"))
    if cpu is not None:
        parts.append(f"CPU {cpu:.1f}%")
    if ram is not None:
        parts.append(f"RAM {ram:.1f}%")
    docker_n = len(snap.get("docker") or [])
    if docker_n:
        parts.append(f"{docker_n} Docker")
    vol_n = len(snap.get("volumes") or [])
    if vol_n:
        parts.append(f"{vol_n} volumes")
    src = str(snap.get("data_source") or "host")
    detail = f"source: {src}"
    if not snap.get("ok"):
        return (parts[0] if parts else "degraded"), detail, "warn"
    return (" · ".join(parts) if parts else "live metrics"), detail, "ok"


def _summarize_vaults(data: Any) -> tuple[str, str, str]:
    if not isinstance(data, dict):
        return "—", "", "ok"
    vaults = data.get("vaults")
    if not isinstance(vaults, list):
        return "—", "", "ok"
    if not vaults:
        return "0 vaults", "", "ok"
    sealed = unlocked = usb = 0
    names: list[str] = []
    for v in vaults:
        if not isinstance(v, dict):
            continue
        st = str(v.get("status") or "").strip().lower()
        if st in ("sealed", "locked"):
            sealed += 1
        elif st in ("unlocked", "open"):
            unlocked += 1
        if v.get("bind_label") or v.get("bind_serial"):
            usb += 1
        name = str(v.get("name") or "").strip()
        if name:
            names.append(name)
    bits = [f"{len(vaults)} vaults"]
    if sealed:
        bits.append(f"{sealed} sealed")
    if unlocked:
        bits.append(f"{unlocked} open")
    if usb:
        bits.append(f"{usb} USB")
    detail = ", ".join(names[:3])
    if len(names) > 3:
        detail += f" +{len(names) - 3}"
    return " · ".join(bits), detail, "ok"


def _summarize_security(data: Any) -> tuple[str, str, str]:
    if not isinstance(data, dict):
        return "—", "", "ok"
    events = data.get("events") or []
    n = len(events) if isinstance(events, list) else 0
    live = "on" if data.get("live_enabled") else "off"
    days = data.get("days")
    summary = f"{n} events · live {live}"
    if days is not None:
        summary += f" · {days}d"
    return summary, "", "ok"


def _summarize_list(kind: str, data: Any) -> tuple[str, str, str]:
    """Return (summary, detail, status)."""
    if kind == "snapshot":
        return _summarize_snapshot(data)
    if kind == "vaults":
        return _summarize_vaults(data)
    if kind == "security":
        return _summarize_security(data)

    items = data
    if isinstance(data, dict):
        for key in ("profiles", "jobs", "plans", "items", "list"):
            if isinstance(data.get(key), list):
                items = data[key]
                break

    if not isinstance(items, list):
        return "—", "", "ok"
    if not items:
        return "0 configured", "", "ok"

    running = sum(1 for x in items if isinstance(x, dict) and x.get("running"))
    latest = _pick_latest([x for x in items if isinstance(x, dict)])
    latest_st = latest.get("last_status") if latest else None
    status = _status_from_last(latest_st)
    if running:
        status = "warn"

    if kind == "profiles":
        auto = sum(1 for x in items if isinstance(x, dict) and x.get("auto_sync"))
        summary = f"{len(items)} profiles"
        if auto:
            summary += f" · {auto} auto-sync"
    elif kind == "jobs":
        auto = sum(1 for x in items if isinstance(x, dict) and x.get("auto_verify"))
        summary = f"{len(items)} jobs"
        if auto:
            summary += f" · {auto} scheduled"
    else:
        en = sum(1 for x in items if isinstance(x, dict) and x.get("enabled", True))
        summary = f"{len(items)} plans · {en} enabled"

    if running:
        summary += f" · {running} running"

    detail = ""
    if latest:
        name = str(latest.get("name") or "")
        lr = str(latest.get("last_run") or latest.get("last_run_date") or "")
        msg = str(latest.get("last_message") or "").strip()
        bits = [b for b in (name, latest_st, lr, msg[:80] if msg else "") if b]
        detail = " · ".join(bits)

    return summary, detail, status


def collect_runlevel_apps() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in RUNLEVEL_APPS:
        port = int(spec["port"])
        ok_h, health = _http_json(port, "/health")
        row: dict[str, Any] = {
            "id": spec["id"],
            "name": spec["name"],
            "port": port,
            "online": ok_h,
            "version": "",
            "summary": "",
            "detail": "",
            "status": "offline",
            "is_self": bool(spec.get("self")),
        }
        if ok_h and isinstance(health, dict):
            row["version"] = str(health.get("version") or "")
            row["status"] = "ok"
        if ok_h:
            ok_s, payload = _http_json(port, str(spec["summary_path"]))
            if ok_s:
                summary, detail, st = _summarize_list(str(spec["kind"]), payload)
                row["summary"] = summary
                row["detail"] = detail
                if st == "bad":
                    row["status"] = "bad"
                elif st == "warn" and row["status"] == "ok":
                    row["status"] = "warn"
            elif not row["summary"]:
                row["summary"] = "UI online"
        else:
            row["summary"] = "not reachable"
        rows.append(row)
    return rows
