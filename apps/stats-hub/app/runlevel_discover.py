# -*- coding: utf-8 -*-
"""Discover installed Runlevel UGOS apps from /var/packages (same idea as NAS Admin)."""
from __future__ import annotations

import glob
import json
import os
import subprocess
from typing import Any

from i18n import get_lang

_PACKAGES_GLOB = "/var/packages/com.runlevel.*"
_CONFIG_REL = (
    "config.json",
    "rootfs/config.json",
    "target/config.json",
    "target/rootfs/config.json",
)

# Optional API probe hints — unknown installed apps still appear with generic /health.
APP_PROBES: dict[str, dict[str, Any]] = {
    "com.runlevel.statshub": {"summary_path": "/api/snapshot", "kind": "snapshot", "self": True},
    "com.runlevel.transferhub": {"summary_path": "/api/profiles", "kind": "profiles"},
    "com.runlevel.backupverifier": {"summary_path": "/api/jobs", "kind": "jobs"},
    "com.runlevel.wakesync": {"summary_path": "/api/plans", "kind": "plans"},
    "com.runlevel.securityhub": {"summary_path": "/api/events", "kind": "security"},
    "com.runlevel.lockandkey": {"summary_path": "/api/vaults", "kind": "vaults"},
    "com.runlevel.icloudpull": {"summary_path": "/api/status", "kind": "icloud_sync"},
}

_DEFAULT_PROBE = {"summary_path": "/api/status", "kind": "generic"}

# Fallback when host-network containers have no published port in docker inspect.
_KNOWN_PORTS: dict[str, int] = {
    "com.runlevel.transferhub": 29100,
    "com.runlevel.backupverifier": 29110,
    "com.runlevel.wakesync": 29120,
    "com.runlevel.statshub": 29125,
    "com.runlevel.securityhub": 29130,
    "com.runlevel.lockandkey": 29135,
    "com.runlevel.icloudpull": 29140,
}


def _run(cmd: list[str], *, timeout: int = 8) -> str:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        return ((proc.stdout or "") + (proc.stderr or "")).strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _config_path(pkg: str) -> str:
    for rel in _CONFIG_REL:
        path = os.path.join(pkg, rel)
        if os.path.isfile(path):
            return path
    return ""


def _load_config(pkg: str) -> dict[str, Any]:
    path = _config_path(pkg)
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _display_name(cfg: dict[str, Any], *, app_id: str) -> str:
    lang = get_lang()
    prefer = "de-DE" if lang.startswith("de") else "en-US"
    i18n = cfg.get("i18n")
    if isinstance(i18n, list):
        for item in i18n:
            if isinstance(item, dict) and item.get("langName") == prefer and item.get("name"):
                return str(item["name"]).strip()
        for item in i18n:
            if isinstance(item, dict) and item.get("name"):
                return str(item["name"]).strip()
    if isinstance(i18n, dict):
        block = i18n.get(prefer)
        if isinstance(block, dict) and block.get("name"):
            return str(block["name"]).strip()
        for block in i18n.values():
            if isinstance(block, dict) and block.get("name"):
                return str(block["name"]).strip()
    return (str(cfg.get("appId") or app_id) or app_id).strip()


def _version_label(cfg: dict[str, Any]) -> str:
    ver = cfg.get("version")
    if isinstance(ver, dict):
        v = str(ver.get("version") or "").strip()
        if v:
            return v
    return ""


def _web_port(cfg: dict[str, Any]) -> int:
    base = cfg.get("baseAccessInfo")
    if isinstance(base, dict):
        port_info = base.get("portInfo")
        if isinstance(port_info, dict):
            raw = str(port_info.get("port") or "").strip()
            if raw.isdigit():
                return int(raw)
    checker = cfg.get("checkParameter")
    if isinstance(checker, dict):
        pc = checker.get("portChecker")
        if isinstance(pc, dict):
            flag = pc.get("portFlag")
            if isinstance(flag, int) and flag > 0:
                return flag
    return 0


def _host_port_from_cid(cid: str) -> int:
    if not cid:
        return 0
    raw = _run(["docker", "inspect", cid], timeout=10)
    if not raw.startswith("["):
        return 0
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return 0
    obj = data[0]
    ports = (obj.get("NetworkSettings") or {}).get("Ports") or {}
    if isinstance(ports, dict):
        for key in sorted(ports.keys()):
            bindings = ports.get(key)
            if not bindings or not isinstance(bindings, list):
                continue
            for binding in bindings:
                if isinstance(binding, dict):
                    hp = str(binding.get("HostPort") or "").strip()
                    if hp.isdigit():
                        return int(hp)
    pb = (obj.get("HostConfig") or {}).get("PortBindings") or {}
    if isinstance(pb, dict):
        for key in sorted(pb.keys()):
            bindings = pb.get(key)
            if bindings and isinstance(bindings, list) and isinstance(bindings[0], dict):
                hp = str(bindings[0].get("HostPort") or "").strip()
                if hp.isdigit():
                    return int(hp)
    return 0


def _resolve_port(app_id: str, cfg: dict[str, Any], cid: str) -> int:
    """Host-network apps bind directly — prefer config/known port when inspect has no mapping."""
    port = _host_port_from_cid(cid) if cid else 0
    if port <= 0:
        port = _web_port(cfg)
    if port <= 0:
        port = int(_KNOWN_PORTS.get(app_id) or 0)
    return port


def _container_for(app_id: str, pkg: str) -> tuple[str, bool, str]:
    cid = ""
    state = "stopped"
    running = False

    def _finish(full_cid: str) -> tuple[str, bool, str]:
        nonlocal cid, state, running
        cid = full_cid
        state = (
            _run(["docker", "inspect", "-f", "{{.State.Status}}", full_cid], timeout=5).lower()
            or "stopped"
        )
        running = state == "running"
        return cid, running, state

    for full_cid in _run(["docker", "ps", "-aq"], timeout=8).split():
        if not full_cid:
            continue
        env = _run(
            ["docker", "inspect", "-f", "{{range .Config.Env}}{{println .}}{{end}}", full_cid],
            timeout=5,
        )
        if f"UGOS_APP_ID={app_id}" in env.splitlines():
            return _finish(full_cid)

    for line in _run(
        ["docker", "ps", "-a", "--filter", f"volume={pkg}", "--format", "{{.ID}}|{{.State}}"],
        timeout=8,
    ).splitlines():
        if not line.strip():
            continue
        parts = line.strip().split("|", 1)
        pick = parts[0]
        st = (parts[1] if len(parts) > 1 else "").strip().lower()
        if st == "running":
            return _finish(pick)
        if not cid:
            cid = pick
            state = st or "stopped"
    return cid, running, state


def probe_for(app_id: str) -> dict[str, Any]:
    row = dict(APP_PROBES.get(app_id) or _DEFAULT_PROBE)
    if app_id == os.environ.get("UGOS_APP_ID", "com.runlevel.statshub"):
        row["self"] = True
    return row


def discover_installed_runlevel_apps() -> list[dict[str, Any]]:
    """Installed com.runlevel.* under /var/packages (needs /var/packages mount in compose)."""
    rows: list[dict[str, Any]] = []
    for pkg in sorted(glob.glob(_PACKAGES_GLOB)):
        if not os.path.isdir(pkg):
            continue
        app_id = os.path.basename(pkg)
        cfg = _load_config(pkg)
        cid, running, docker_state = _container_for(app_id, pkg)
        port = _resolve_port(app_id, cfg, cid)
        probe = probe_for(app_id)
        rows.append(
            {
                "id": app_id,
                "name": _display_name(cfg, app_id=app_id),
                "port": port,
                "version": _version_label(cfg),
                "summary_path": str(probe.get("summary_path") or "/api/status"),
                "kind": str(probe.get("kind") or "profiles"),
                "self": bool(probe.get("self")),
            }
        )
    rows.sort(key=lambda r: (str(r.get("name") or "").casefold(), str(r.get("id") or "")))
    return rows


def list_runlevel_app_specs() -> list[dict[str, Any]]:
    """Installed packages on NAS; fall back to built-in list if /var/packages is not visible."""
    rows = discover_installed_runlevel_apps()
    if rows:
        return rows
    from runlevel_registry import RUNLEVEL_APPS

    return RUNLEVEL_APPS
