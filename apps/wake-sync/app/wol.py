# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import socket
import time

from store import append_log

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")


def normalize_mac(mac: str) -> str:
    m = (mac or "").strip().lower().replace("-", ":")
    if not _MAC_RE.match(m):
        raise ValueError(f"invalid MAC: {mac}")
    return m


def broadcast_for_ip(ip: str) -> str | None:
    parts = (ip or "").strip().split(".")
    if len(parts) != 4:
        return None
    try:
        if not all(0 <= int(p) <= 255 for p in parts):
            return None
    except ValueError:
        return None
    return f"{parts[0]}.{parts[1]}.{parts[2]}.255"


def _looks_like_host_ip(addr: str) -> bool:
    addr = (addr or "").strip()
    if not addr or addr == "255.255.255.255":
        return False
    if addr.endswith(".255"):
        return False
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", addr))


def wol_broadcast() -> str:
    return (os.environ.get("WOL_BROADCAST") or "").strip()


def wol_source_ips() -> list[str]:
    raw = (os.environ.get("WOL_SOURCE_IP") or "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def resolve_wol_targets(broadcast: str | None, target_ip: str | None) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()

    def add(addr: str | None) -> None:
        a = (addr or "").strip()
        if not a or a in seen:
            return
        seen.add(a)
        targets.append(a)

    env_bc = (broadcast or wol_broadcast()).strip()
    tip = (target_ip or "").strip()

    if env_bc and _looks_like_host_ip(env_bc):
        append_log(f"WOL: {env_bc} is host IP — using subnet broadcast")
        add(broadcast_for_ip(env_bc))
        if tip and env_bc != tip:
            add(broadcast_for_ip(tip))
    elif env_bc:
        add(env_bc)

    if tip:
        add(broadcast_for_ip(tip))

    add("255.255.255.255")
    return targets or ["255.255.255.255"]


def _route_source_ip(target_ip: str) -> str | None:
    if not target_ip:
        return None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect((target_ip, 9))
        local = sock.getsockname()[0]
        sock.close()
        return local
    except OSError:
        return None


def _same_subnet_24(a: str, b: str) -> bool:
    pa, pb = a.split(".")[:3], b.split(".")[:3]
    return len(pa) >= 3 and len(pb) >= 3 and pa[:3] == pb[:3]


def resolve_send_attempts(
    broadcast: str | None, target_ip: str | None
) -> list[tuple[str | None, str]]:
    """(source_ip or None, broadcast_dest) pairs — direct link + router paths."""
    broadcasts = resolve_wol_targets(broadcast, target_ip)
    tip = (target_ip or "").strip()

    sources: list[str | None] = []
    for s in wol_source_ips():
        if s not in sources:
            sources.append(s)
    if tip:
        routed = _route_source_ip(tip)
        if routed and routed not in sources:
            sources.append(routed)
    sources.append(None)

    attempts: list[tuple[str | None, str]] = []
    seen: set[tuple[str | None, str]] = set()

    for src in sources:
        for bc in broadcasts:
            if src and bc != "255.255.255.255":
                tip_bc = broadcast_for_ip(tip) if tip else None
                src_bc = broadcast_for_ip(src)
                if tip_bc and bc == tip_bc and not _same_subnet_24(src, tip):
                    continue
                if src_bc and bc == src_bc and _same_subnet_24(src, bc):
                    pass
                elif tip_bc and bc == tip_bc and _same_subnet_24(src, tip):
                    pass
                elif bc != "255.255.255.255":
                    continue
            key = (src, bc)
            if key in seen:
                continue
            seen.add(key)
            attempts.append(key)
    return attempts


def _send_packet(packet: bytes, target: str, source_ip: str | None = None) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if source_ip:
            try:
                sock.bind((source_ip, 0))
            except OSError as ex:
                append_log(f"WOL bind {source_ip} failed: {ex}")
                return False
        sock.sendto(packet, (target, 9))
        return True
    except OSError as ex:
        append_log(f"WOL send to {target} failed: {ex}")
        return False
    finally:
        sock.close()


def send_wol(
    mac: str,
    broadcast: str | None = None,
    *,
    target_ip: str | None = None,
    repeats: int = 3,
) -> tuple[bool, str]:
    try:
        mac_n = normalize_mac(mac)
    except ValueError as ex:
        return False, str(ex)

    attempts = resolve_send_attempts(broadcast, target_ip)
    if not attempts:
        return False, "no send paths"

    try:
        mac_bytes = bytes.fromhex(mac_n.replace(":", ""))
        if len(mac_bytes) != 6:
            return False, "invalid MAC length"
        packet = b"\xff" * 6 + mac_bytes * 16

        ok_count = 0
        log_paths: list[str] = []
        for src, bc in attempts:
            label = f"{src or 'default'}→{bc}"
            sent = 0
            for _ in range(max(1, repeats)):
                if _send_packet(packet, bc, src):
                    sent += 1
                    ok_count += 1
                time.sleep(0.15)
            if sent:
                log_paths.append(label)

        if ok_count == 0:
            hint = ""
            if wol_source_ips() and any(s for s, _ in attempts if s):
                hint = " — WOL_SOURCE_IP bind failed? App uses host network; set e.g. 10.0.0.2"
            return False, f"no packet sent{hint}"

        append_log(f"WOL {ok_count} pkt to {mac_n} via {', '.join(log_paths)}")
        return True, ", ".join(log_paths)
    except OSError as ex:
        return False, str(ex)


def wait_for_host(
    host: str,
    port: int = 445,
    timeout_sec: int = 1200,
    poll_sec: int = 15,
) -> tuple[bool, str]:
    host = (host or "").strip()
    if not host:
        return False, "target IP missing"
    deadline = time.time() + max(30, int(timeout_sec))
    append_log(f"WAIT for {host}:{port} (max {int(timeout_sec)}s)")
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=8):
                append_log(f"WAIT OK — {host}:{port} reachable")
                return True, "reachable"
        except OSError:
            time.sleep(max(5, int(poll_sec)))
    return False, f"timeout waiting for {host}:{port}"
