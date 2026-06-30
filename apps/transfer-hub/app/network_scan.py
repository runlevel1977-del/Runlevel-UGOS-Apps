# -*- coding: utf-8 -*-
"""Simple LAN scan for SMB (445) and SSH (22)."""
from __future__ import annotations

import ipaddress
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

LAN_SUBNET = os.environ.get("LAN_SUBNET", "").strip()
SCAN_EXTRA_HOSTS = os.environ.get("SCAN_EXTRA_HOSTS", "").strip()
PROBE_TIMEOUT = float(os.environ.get("SCAN_TIMEOUT", "2.0") or "2.0")


def extra_hosts() -> list[str]:
    return [h.strip() for h in SCAN_EXTRA_HOSTS.split(",") if h.strip()]


def scan_config() -> dict[str, Any]:
    return {
        "lan_subnet": LAN_SUBNET,
        "extra_hosts": extra_hosts(),
        "probe_timeout": PROBE_TIMEOUT,
    }


def host_smb_reachable(host: str, timeout: float | None = None) -> bool:
    """Quick TCP check on 445 — avoids full rclone when PC/NAS is off."""
    host = (host or "").strip()
    if not host:
        return False
    return _probe(host, 445, timeout)


def _probe(host: str, port: int, timeout: float | None = None) -> bool:
    t = PROBE_TIMEOUT if timeout is None else timeout
    try:
        with socket.create_connection((host, port), timeout=t):
            return True
    except OSError:
        return False


def _scan_host(ip: str) -> dict[str, Any] | None:
    smb = _probe(ip, 445)
    ssh = _probe(ip, 22)
    if not smb and not ssh:
        return None
    kinds = []
    if smb:
        kinds.append("SMB")
    if ssh:
        kinds.append("SSH")
    return {
        "host": ip,
        "name": ip,
        "services": kinds,
        "smb": smb,
        "ssh": ssh,
    }


def probe_host(host: str) -> dict[str, Any] | None:
    host = host.strip()
    if not host:
        return None
    return _scan_host(host)


def scan_lan(lang: str | None = None) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    from i18n import get_lang, t

    lng = lang or get_lang()
    cfg = scan_config()
    hosts: list[str] = []
    if LAN_SUBNET:
        try:
            net = ipaddress.ip_network(LAN_SUBNET, strict=False)
            hosts = [str(h) for h in net.hosts()]
            if len(hosts) > 512:
                hosts = hosts[:512]
        except ValueError as e:
            return [], t(
                "scan.invalid_subnet", lng, subnet=LAN_SUBNET, err=e
            ), cfg
    for ip in extra_hosts():
        if ip not in hosts:
            hosts.append(ip)

    if not hosts:
        return [], t("scan.no_subnet", lng), cfg

    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(_scan_host, ip): ip for ip in hosts}
        for fut in as_completed(futures):
            row = fut.result()
            if row and row["host"] not in seen:
                seen.add(row["host"])
                found.append(row)
    found.sort(key=lambda x: x["host"])
    if LAN_SUBNET:
        subnet_hint = t("scan.hint_subnet", lng, subnet=LAN_SUBNET)
    elif extra_hosts():
        subnet_hint = t("scan.hint_extra_only", lng)
    else:
        subnet_hint = ""
    if not found:
        msg = t("scan.none_found", lng, hint=subnet_hint)
    else:
        msg = t("scan.found", lng, count=len(found), hint=subnet_hint)
    return found, msg, cfg
