# -*- coding: utf-8 -*-
"""Host metrics — same sources as Ugreen NAS Admin dashboard (dash_cmd)."""
from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import signal
import socket
import struct
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

_diskstats_lock = threading.Lock()
_prev_diskstats: dict[str, tuple[int, int]] = {}

_USB_HINT = re.compile(
    r"@usb|volumeusb|/media/|/run/media/|[/]usb|removabledisk|externaldisk",
    re.I,
)
_VOL_ROOT = re.compile(r"^/volume\d+$", re.I)


def _run(cmd: str, timeout: int = 30) -> str:
    """Run shell cmd; on timeout kill the whole process group (not only the shell)."""
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            executable="/bin/bash",
            errors="replace",
            start_new_session=True,
        )
    except OSError:
        return ""
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        return ""
    except Exception:
        return ""
    return (stdout or "") + (stderr or "")


def is_dashboard_mount(mp: str) -> bool:
    raw = str(mp or "").strip()
    if not raw.startswith("/"):
        return False
    p = posixpath.normpath(raw.rstrip("/") or "/")
    if p == "/":
        return True
    if _VOL_ROOT.match(p):
        return True
    if p.startswith("/mnt/dm-"):
        return False
    if p.startswith("/mnt/@usb"):
        return True
    return bool(_USB_HINT.search(p))


def mount_sort_key(mp: str) -> tuple:
    if mp == "/":
        return (-1,)
    m = re.match(r"^/volume(\d+)$", mp, re.I)
    if m:
        return (0, int(m.group(1)))
    return (9,) + tuple(ord(c) for c in mp.casefold())


def fmt_size_1k(blocks_1024: int) -> str:
    nbytes = max(0, int(blocks_1024)) * 1024
    if nbytes <= 0:
        return "0 B"
    for unit, dv in ("TiB", 2**40), ("GiB", 2**30), ("MiB", 2**20), ("KiB", 1024):
        if nbytes >= dv:
            q = nbytes / dv
            s = f"{q:.2f}" if dv >= 2**30 else (f"{q:.1f}" if dv >= 2**20 else f"{int(q)}")
            return f"{s.rstrip('0').rstrip('.')} {unit}"
    return "0 B"


def fmt_rate(bps: float) -> str:
    bps = max(0.0, float(bps))
    for u, div in (("GB/s", 1e9), ("MB/s", 1e6), ("KB/s", 1024)):
        if bps >= div:
            return f"{bps / div:.2f} {u}"
    return f"{bps:.0f} B/s"


def parse_cpu_line(line: str) -> tuple[int, int] | None:
    sp = line.strip().split()
    if len(sp) < 5 or not sp[0].startswith("cpu"):
        return None
    nums = list(map(int, sp[1:]))
    return nums[3], sum(nums)


def cpu_pct(prev: tuple[int, int] | None, cur: tuple[int, int] | None) -> float | None:
    if not prev or not cur:
        return None
    idle_d = cur[0] - prev[0]
    total_d = cur[1] - prev[1]
    if total_d <= 0 or prev[1] <= 0:
        return None
    return 100.0 * (1.0 - idle_d / total_d)


def parse_ram_pct(mem_line: str) -> float | None:
    toks = mem_line.strip().split()
    if len(toks) < 3:
        return None
    try:
        total, used = int(toks[1]), int(toks[2])
        return 100.0 * used / max(1, total)
    except (ValueError, ZeroDivisionError):
        return None


def parse_volumes(df_text: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for raw in df_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("Filesystem"):
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        mp = posixpath.normpath((parts[-1] or "/").rstrip("/") or "/")
        if not is_dashboard_mount(mp):
            continue
        try:
            total_1k = int(parts[-5])
            used_1k = int(parts[-4])
        except (ValueError, IndexError):
            continue
        pct_s = str(parts[-2] or "").strip()
        if pct_s.endswith("%"):
            try:
                p = float(pct_s[:-1])
            except ValueError:
                p = 100.0 * used_1k / max(1, total_1k)
        else:
            p = 100.0 * used_1k / max(1, total_1k)
        found[mp] = {
            "path": mp,
            "pct": round(p, 1),
            "used_1k": used_1k,
            "total_1k": total_1k,
            "used_h": fmt_size_1k(used_1k),
            "total_h": fmt_size_1k(total_1k),
        }
    return sorted(found.values(), key=lambda r: mount_sort_key(str(r["path"])))


_nsenter_ok: bool | None = None


def _netns_link(path: str) -> str:
    try:
        return os.readlink(path)
    except OSError:
        return ""


def _use_host_netns() -> bool:
    """True when pid:host but the container still has its own Docker netns."""
    host = _netns_link("/proc/1/ns/net")
    self = _netns_link("/proc/self/ns/net")
    return bool(host and self and host != self)


def _host_netns_run(cmd: str, timeout: int = 2) -> str:
    """Optional nsenter helper. Never used on the live tick path (it can hang)."""
    global _nsenter_ok
    if _nsenter_ok is False:
        return ""
    out = _run(f"nsenter -t 1 -n -- {cmd}", timeout)
    stripped = (out or "").strip()
    if stripped and stripped not in ("[]",):
        _nsenter_ok = True
        return out
    _nsenter_ok = False
    return ""


def _net_proc_file(name: str) -> str:
    if _use_host_netns() and os.path.isfile(f"/proc/1/net/{name}"):
        return f"/proc/1/net/{name}"
    return f"/proc/net/{name}"


def _read_text_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _sys_net_field(ifn: str, rel: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", ifn):
        return ""
    # Do not read /proc/1/root — that path can hang in Docker and stall the UI.
    return _read_text_file(f"/sys/class/net/{ifn}/{rel}").strip()


def _proc_hex_ipv4(h: str) -> str:
    try:
        return socket.inet_ntoa(struct.pack("<I", int(h, 16)))
    except (ValueError, OSError, struct.error):
        return ""


def parse_proc_default_route(text: str = "") -> tuple[str, str]:
    """IPv4 default route from /proc/net/route: (gateway, iface)."""
    raw = text or _read_text_file(_net_proc_file("route"))
    for line in raw.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 8:
            continue
        if parts[1] != "00000000":
            continue
        gw = _proc_hex_ipv4(parts[2])
        if gw and gw != "0.0.0.0":
            return gw, parts[0]
    return "", ""


def _local_ipv4s_from_fib(text: str) -> list[str]:
    ips: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^\s+\|--\s+(\d+\.\d+\.\d+\.\d+)\s*$", line)
        if not m:
            continue
        window = "\n".join(lines[i : i + 4])
        if "host LOCAL" not in window:
            continue
        ip = m.group(1)
        if ip.startswith("127.") or ip.startswith("255."):
            continue
        ips.append(ip)
    return ips


def _assign_ipv4_to_ifaces(ifaces: list[str], fib: str, route: str) -> dict[str, list[str]]:
    """Map local IPv4 addresses onto iface names via the route table."""
    out: dict[str, list[str]] = {k: [] for k in ifaces}
    nets: list[tuple[str, int, int]] = []
    for line in route.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 8:
            continue
        ifn = parts[0]
        if ifn not in out:
            continue
        dest = int(parts[1], 16)
        mask = int(parts[7], 16)
        if mask == 0:
            continue
        nets.append((ifn, dest, mask))
    nets.sort(key=lambda t: t[2], reverse=True)
    for ip in _local_ipv4s_from_fib(fib):
        try:
            ip_le = int.from_bytes(socket.inet_aton(ip), "little")
        except OSError:
            continue
        placed = False
        for ifn, dest, mask in nets:
            if (ip_le & mask) == dest:
                plen = bin(mask).count("1")
                addr = f"{ip}/{plen}"
                if addr not in out[ifn]:
                    out[ifn].append(addr)
                placed = True
                break
        if placed:
            continue
        if len(ifaces) == 1:
            out[ifaces[0]].append(f"{ip}/32")
    return out


def fill_iface_meta(info: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Fill MAC / operstate / IPv4 when `ip` cannot see the host netns (no nsenter)."""
    names = list(info.keys())
    if not names:
        return info
    fib = _read_text_file(_net_proc_file("fib_trie"))
    route = _read_text_file(_net_proc_file("route"))
    assigned = _assign_ipv4_to_ifaces(names, fib, route) if fib else {}
    for ifn, meta in info.items():
        if not meta.get("mac"):
            mac = _sys_net_field(ifn, "address")
            if mac and mac != "00:00:00:00:00:00":
                meta["mac"] = mac
        if not meta.get("state"):
            st = _sys_net_field(ifn, "operstate")
            if st:
                meta["state"] = st
        if not meta.get("addrs") and assigned.get(ifn):
            meta["addrs"] = list(assigned[ifn])
        if not meta.get("state") and (meta.get("addrs") or meta.get("mac")):
            meta["state"] = "up"
    return info


def is_docker_bridge_iface(meta: dict[str, Any]) -> bool:
    """Container veth on docker0 (MAC 02:42:… + 172.17/172.18) — not the NAS LAN NIC."""
    mac = str(meta.get("mac") or "").lower().replace("-", ":")
    if not mac.startswith("02:42:"):
        return False
    for addr in meta.get("addrs") or []:
        a = str(addr)
        if a.startswith("172.17.") or a.startswith("172.18."):
            return True
    return False


def physical_ifaces(net_text: str) -> dict[str, tuple[int, int]]:
    """Non-virtual NICs from /proc/net/dev — also at 0 B/s (inactive link still listed)."""
    badpfx = (
        "docker",
        "br-",
        "veth",
        "virbr",
        "lxc",
        "ovs-system",
        "sit",
        "tun",
        "tap",
        "wg",
        "zt",
        "tailscale",
    )
    out: dict[str, tuple[int, int]] = {}
    for line in net_text.splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        ifn = iface.strip()
        if (
            not ifn
            or ifn == "lo"
            or "." in ifn
            or "@" in ifn
            or any(ifn.lower().startswith(p) for p in badpfx)
        ):
            continue
        nums = rest.split()
        if len(nums) < 16:
            continue
        try:
            rx = int(nums[0])
            tx = int(nums[8])
        except ValueError:
            continue
        out[ifn] = (rx, tx)
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def parse_ip_addr(ipj: str, ifaces: dict[str, tuple[int, int]]) -> dict[str, dict[str, Any]]:
    info: dict[str, dict[str, Any]] = {
        k: {"addrs": [], "state": "", "mac": "", "default_gw": False} for k in ifaces
    }
    try:
        rows = json.loads(ipj.strip() or "[]")
    except json.JSONDecodeError:
        return info
    if not isinstance(rows, list):
        return info
    for row in rows:
        if not isinstance(row, dict):
            continue
        ifn = str(row.get("ifname") or "")
        if ifn not in info:
            continue
        info[ifn]["state"] = str(row.get("operstate") or "")
        info[ifn]["mac"] = str(row.get("address") or "")
        for addr in row.get("addr_info") or []:
            if not isinstance(addr, dict):
                continue
            if addr.get("family") == "inet":
                info[ifn]["addrs"].append(
                    f"{addr.get('local', '')}/{addr.get('prefixlen', '')}"
                )
    return info


def parse_default_route_dev(rtj: str) -> tuple[str, str]:
    """First IPv4 default route: (gateway, device)."""
    try:
        rows = json.loads(rtj.strip() or "[]")
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(rows, list):
        return "", ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        dst = str(row.get("dst") or "")
        if dst not in ("default", "0.0.0.0"):
            continue
        fam = row.get("family")
        if fam is not None and str(fam) not in ("inet", ""):
            continue
        gw = row.get("gateway") or row.get("nexthop")
        dev = row.get("dev")
        if gw and dev:
            gs = str(gw)
            if ":" in gs:
                continue
            return gs, str(dev)
    return "", ""


def parse_cpu_temp_c(raw: str) -> float | None:
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.isdigit():
            continue
        v = int(line)
        if v > 1000:
            v //= 1000
        if 0 < v < 200:
            return float(v)
    return None


def parse_fan_rpms(raw: str) -> list[tuple[str, int]]:
    """UGOS it86: ``sysfan1 speed:482``; hwmon: ``fan1_input 1200`` or ``it87/fan1 900``."""
    out: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for ln in (raw or "").splitlines():
        s = (ln or "").strip()
        if not s or "__UG_" in s or s.startswith("#"):
            continue
        m = re.search(r"(?i)^\s*(\S+)\s+speed:\s*(\d+)", s)
        if m:
            pair = (m.group(1), int(m.group(2)))
            if pair not in seen:
                seen.add(pair)
                out.append(pair)
            continue
        m = re.search(r"(?i)^\s*(\S+)\s+rpm[:\s,]+\s*(\d+)", s)
        if m:
            pair = (m.group(1), int(m.group(2)))
            if pair not in seen:
                seen.add(pair)
                out.append(pair)
            continue
        parts = s.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            try:
                rpm = int(parts[-1])
            except ValueError:
                continue
            if not (0 <= rpm < 50000):
                continue
            name = parts[0]
            nl = name.lower()
            if "fan" in nl or nl.startswith("fan") or "/" in name:
                pair = (name, rpm)
                if pair not in seen:
                    seen.add(pair)
                    out.append(pair)
    return out


_REMOTE_FAN = r"""if [ -e /proc/it86/fan ]; then cat /proc/it86/fan 2>/dev/null; fi
for d in /sys/class/hwmon/hwmon*; do
  [ -d "$d" ] || continue
  chip=$(cat "$d/name" 2>/dev/null || basename "$d")
  for f in "$d"/fan*_input; do
    [ -r "$f" ] || continue
    base=$(basename "$f")
    lbl="$chip/$base"
    lf="${f%_input}_label"
    if [ -r "$lf" ]; then
      ln=$(cat "$lf" 2>/dev/null)
      [ -n "$ln" ] && lbl="$chip/$ln"
    fi
    echo "$lbl $(cat "$f" 2>/dev/null)"
  done
done 2>/dev/null
"""


def collect_df_block() -> str:
    """Same df logic as NAS Admin dashboard_monitor_loop."""
    cmd = (
        "df -P 2>/dev/null | tail -n +2\n"
        "[ -d /mnt/@usb ] && df -P /mnt/@usb 2>/dev/null | tail -n +2 || true\n"
        'for _ug_x in /mnt/@usb/*; do [ -e "$_ug_x" ] || continue; '
        'df -P "$_ug_x" 2>/dev/null | tail -n +2 || true; done\n'
        "PATH=/usr/bin:/bin:/usr/sbin:/sbin; "
        "command -v findmnt >/dev/null 2>&1 && findmnt -rn -o TARGET 2>/dev/null | "
        'while IFS= read -r _ug_m; do '
        '[ -z "$_ug_m" ] && continue; '
        'case "$_ug_m" in /|/mnt/dm-*|/volume[0-9]) continue ;; esac; '
        'printf %s "$_ug_m" | grep -Eqi \'@usb|volumeusb|/media/|usb|removabledisk\' || continue; '
        'df -P "$_ug_m" 2>/dev/null | tail -n +2 || true; '
        "done\n"
        "df -P /volume1 /volume2 2>/dev/null | tail -n +2 || true\n"
    )
    # Keep short: during Transfer Hub / heavy I/O, long df can stall the monitor.
    return _run(cmd, timeout=8)


def _docker_health_from_status(status: str) -> str:
    s = (status or "").lower()
    if "(healthy)" in s:
        return "healthy"
    if "(unhealthy)" in s:
        return "unhealthy"
    if "health: starting" in s:
        return "starting"
    return ""


def _is_runlevel_image(image: str) -> bool:
    return "runlevel/" in (image or "").lower()


_DOCKER_CPU_LOCK = threading.Lock()
_prev_docker_cpu: dict[str, tuple[int, float]] = {}


def _docker_container_dirs() -> list[str]:
    extra = (os.environ.get("STATS_HUB_DOCKER_CONTAINERS_DIR") or "").strip()
    roots: list[str] = []
    if extra:
        roots.append(extra)
    roots.extend(("/volume1/@docker/containers", "/volume2/@docker/containers"))
    return [p for p in roots if os.path.isdir(p)]


def _read_json_file(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _docker_name(cfg: dict[str, Any], folder: str) -> str:
    name = str(cfg.get("Name") or "").strip()
    if name.startswith("/"):
        name = name[1:]
    return name or folder[:12]


def _docker_image(cfg: dict[str, Any]) -> str:
    config = cfg.get("Config")
    if isinstance(config, dict):
        img = str(config.get("Image") or "").strip()
        if img:
            return img
    return str(cfg.get("Image") or "").strip()


def _docker_env_lines(cfg: dict[str, Any]) -> list[str]:
    config = cfg.get("Config")
    if not isinstance(config, dict):
        return []
    env = config.get("Env")
    if isinstance(env, list):
        return [str(x) for x in env]
    return []


def _is_runlevel_container(image: str, cfg: dict[str, Any]) -> bool:
    if _is_runlevel_image(image):
        return True
    return any(line.startswith("UGOS_APP_ID=com.runlevel.") for line in _docker_env_lines(cfg))


def _docker_status_text(state: dict[str, Any]) -> str:
    status = str(state.get("Status") or "").strip()
    if not status:
        status = "running" if state.get("Running") else "exited"
    health = ""
    raw_health = state.get("Health")
    if isinstance(raw_health, dict):
        health = str(raw_health.get("Status") or "").strip().lower()
    if health in ("healthy", "unhealthy", "starting"):
        return f"{status} ({health})"
    return status


def _cgroup_dir(cid: str) -> str:
    cid = (cid or "").strip()
    if not cid:
        return ""
    for path in (
        f"/sys/fs/cgroup/system.slice/docker-{cid}.scope",
        f"/sys/fs/cgroup/docker/{cid}",
        f"/sys/fs/cgroup/memory/docker/{cid}",
    ):
        if os.path.isdir(path):
            return path
    return ""


def _read_int_file(path: str) -> int | None:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read().strip()
    except OSError:
        return None
    if not raw or raw in ("max", "-1"):
        return None
    try:
        return int(raw.split()[0])
    except ValueError:
        return None


def _cgroup_cpu_pct(cid: str, cg: str) -> str:
    usage: int | None = None
    try:
        with open(os.path.join(cg, "cpu.stat"), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("usage_usec"):
                    usage = int(line.split()[1])
                    break
    except (OSError, ValueError, IndexError):
        usage = None
    if usage is None:
        usage_ns = _read_int_file(os.path.join(cg, "cpuacct.usage"))
        if usage_ns is not None:
            usage = usage_ns // 1000
    if usage is None:
        return ""
    now = time.monotonic()
    with _DOCKER_CPU_LOCK:
        prev = _prev_docker_cpu.get(cid)
        _prev_docker_cpu[cid] = (usage, now)
    if not prev:
        return ""
    prev_u, prev_t = prev
    dt = now - prev_t
    du = usage - prev_u
    if dt <= 0.05 or du < 0:
        return ""
    pct = (du / (dt * 1_000_000.0)) * 100.0
    return f"{pct:.1f}%"


def _cgroup_mem(cg: str) -> str:
    cur = _read_int_file(os.path.join(cg, "memory.current"))
    if cur is None:
        cur = _read_int_file(os.path.join(cg, "memory.usage_in_bytes"))
    if cur is None:
        return ""
    lim = _read_int_file(os.path.join(cg, "memory.max"))
    if lim is None:
        lim = _read_int_file(os.path.join(cg, "memory.limit_in_bytes"))
    used = fmt_size_1k(max(0, cur) // 1024)
    if lim and lim > 0:
        return f"{used} / {fmt_size_1k(lim // 1024)}"
    return used


def parse_docker_system_df(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (raw or "").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        key = parts[0].rstrip(":").lower()
        if key in ("images", "containers", "local volumes", "build cache"):
            out[key.replace(" ", "_")] = " ".join(parts[3:])
    return out


def parse_mdstat(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    arrays: list[dict[str, Any]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln.startswith("md") and " :" in ln:
            name = ln.split(":", 1)[0].strip()
            state = ln.split(":", 1)[1].strip()
            status_line = ""
            health = "ok"
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("["):
                status_line = lines[i + 1].strip()
                if "_" in status_line and "bitmap" not in ln.lower():
                    health = "warn"
                if "UU" in status_line.replace(" ", ""):
                    health = "ok"
            low = (state + " " + status_line).lower()
            if "degraded" in low or "fault" in low or "failed" in low or "recover" in low:
                health = "bad"
            arrays.append({
                "name": name,
                "state": state,
                "status": status_line,
                "health": health,
            })
            i += 2
            continue
        i += 1
    overall = "unknown"
    if not text:
        overall = "unknown"
    elif not arrays:
        overall = "ok"
    elif any(a["health"] == "bad" for a in arrays):
        overall = "bad"
    elif any(a["health"] == "warn" for a in arrays):
        overall = "warn"
    else:
        overall = "ok"
    low = text.lower()
    if "degraded" in low or "faulty" in low:
        overall = "bad"
    return {"raw": text, "arrays": arrays, "overall": overall}


def _disk_temp_health(temp: float) -> str:
    if temp >= 55:
        return "bad"
    if temp >= 45:
        return "warn"
    return "ok"


def _is_physical_disk_name(name: str) -> bool:
    if not name or name.startswith(("md", "dm-", "loop", "ram", "zram", "sr", "mmcblk")):
        return False
    if re.fullmatch(r"nvme\d+", name):
        return False  # controller char-dev, not namespace (nvme0n1 is the disk)
    if re.fullmatch(r"sd[a-z]+\d+", name):
        return False  # partition
    if re.fullmatch(r"nvme\d+n\d+p\d+", name):
        return False  # partition
    return bool(re.fullmatch(r"sd[a-z]+", name) or re.fullmatch(r"nvme\d+n\d+", name))


def _smartctl_bin() -> str:
    for cand in ("/usr/sbin/smartctl", "/sbin/smartctl", "smartctl"):
        if cand.startswith("/"):
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
        elif _run(f"command -v {shlex.quote(cand)} 2>/dev/null", 3).strip():
            return cand
    return ""


def _scsi_generic_for_block(name: str) -> str:
    if not re.fullmatch(r"sd[a-z]+", name):
        return ""
    sg_name = _run(
        f"ls /sys/block/{name}/device/scsi_generic 2>/dev/null | head -1",
        3,
    ).strip()
    if sg_name and re.fullmatch(r"sg\d+", sg_name):
        dev = f"/dev/{sg_name}"
        if os.path.exists(dev):
            return dev
    for sg_path in _run("ls -d /sys/class/scsi_generic/sg* 2>/dev/null", 5).split():
        sg_path = sg_path.strip()
        if not sg_path:
            continue
        sg_name = os.path.basename(sg_path)
        blk = _run(
            f"readlink -f {sg_path}/device/block/{name} 2>/dev/null",
            3,
        ).strip()
        if blk and os.path.exists(f"/dev/{sg_name}"):
            return f"/dev/{sg_name}"
    return ""


def _smartctl_targets(name: str) -> list[tuple[str, str]]:
    """UGOS SATA: -d sat on /dev/sgN works; scsi alone has no temp (probe confirmed)."""
    dev = f"/dev/{name}"
    if name.startswith("nvme"):
        return [(dev, "nvme"), (dev, "")]
    sg = _scsi_generic_for_block(name)
    targets: list[tuple[str, str]] = []
    if sg:
        targets.append((sg, "sat"))
    targets.append((dev, "sat"))
    targets.append((dev, ""))
    return targets


_STANDBY_SKIP_RE = re.compile(r"in\s+(STANDBY|SLEEP)\s+mode", re.I)


def _smartctl_skipped_standby(raw: str) -> bool:
    return bool(_STANDBY_SKIP_RE.search(raw or ""))


def _is_rotational_disk(name: str) -> bool:
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", name):
        return False
    rot = _run(f"cat /sys/block/{name}/queue/rotational 2>/dev/null", 2).strip()
    return rot == "1"


def _diskstats_map() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for line in _run("cat /proc/diskstats 2>/dev/null", 5).splitlines():
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            out[parts[2]] = (int(parts[5]), int(parts[9]))
        except ValueError:
            continue
    return out


def _diskstats_sectors(name: str) -> tuple[int, int] | None:
    return _diskstats_map().get(name)


def refresh_disk_io_flags(names: list[str]) -> dict[str, bool]:
    """True if read/write sectors changed since the previous collect_disk_temps run."""
    flags: dict[str, bool] = {}
    cur_map = _diskstats_map()
    with _diskstats_lock:
        for name in names:
            cur = cur_map.get(name)
            if cur is None:
                flags[name] = False
                continue
            prev = _prev_diskstats.get(name)
            _prev_diskstats[name] = cur
            flags[name] = bool(prev and (cur[0] > prev[0] or cur[1] > prev[1]))
    return flags


def disks_io_busy(*, min_sectors: int = 4096, sample_sec: float = 0.45) -> bool:
    """True if any disk has significant IO in a short window (Transfer Hub, scrub).

    Does not mutate ``_prev_diskstats`` used by SMART collection. The old
    implementation compared against the last 2-minute SMART sample and treated
    almost every poll as busy, so temperatures never refreshed.
    """
    disks = _list_lsblk_disks()
    names = [d["name"] for d in disks]
    if not names:
        return False
    first = _diskstats_map()
    time.sleep(max(0.15, float(sample_sec)))
    second = _diskstats_map()
    for name in names:
        prev = first.get(name)
        cur = second.get(name)
        if prev is None or cur is None:
            continue
        delta = (cur[0] - prev[0]) + (cur[1] - prev[1])
        if delta >= min_sectors:
            return True
    return False


def _skip_standby_for_disk(name: str, skip_standby: bool) -> bool:
    """-n standby only for HDD (rotational). NVMe/SSD: flag is unreliable or breaks reads."""
    if not skip_standby:
        return False
    if name.startswith("nvme"):
        return False
    if name.startswith("sd"):
        return _is_rotational_disk(name)
    return False


def _smartctl_query(
    sc: str,
    dev: str,
    dtype: str,
    *,
    permissive: bool,
    skip_standby: bool = False,
) -> tuple[float | None, str, str, str, bool]:
    pfx = "-T permissive " if permissive else ""
    dflag = f"-d {dtype} " if dtype else ""
    nflag = "-n standby,q " if skip_standby else ""
    info_raw = _run(f"{sc} {pfx}{nflag}-i {dflag}{shlex.quote(dev)} 2>&1", 5)
    json_raw = _run(f"{sc} {pfx}{nflag}-A -j {dflag}{shlex.quote(dev)} 2>&1", 6)
    skipped = skip_standby and _smartctl_skipped_standby(info_raw + json_raw)
    temp = _smartctl_temp_from_json(json_raw)
    attr_raw = json_raw if temp is not None else ""
    if temp is None and not skipped:
        attr_raw = _run(f"{sc} {pfx}{nflag}-A {dflag}{shlex.quote(dev)} 2>&1", 6)
        skipped = skip_standby and _smartctl_skipped_standby(attr_raw)
        if not skipped:
            temp = _smartctl_temp_from_text(attr_raw)
    serial, model = _parse_smartctl_identity(info_raw)
    if not serial and not model:
        serial, model = _parse_smartctl_identity(attr_raw)
    return temp, serial, model, attr_raw[:500], skipped


def _parse_smartctl_identity(raw: str) -> tuple[str, str]:
    serial = model = ""
    for line in (raw or "").splitlines():
        s = line.strip()
        if re.match(r"(?i)serial number:", s):
            serial = s.split(":", 1)[-1].strip()
        elif re.match(r"(?i)(device model|model number|product):", s):
            model = s.split(":", 1)[-1].strip()
    return serial, model


def _read_sysfs_model(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", name):
        return ""
    return _run(f"cat /sys/block/{name}/device/model 2>/dev/null", 3).strip()


def _read_sysfs_serial(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", name):
        return ""
    for rel in ("device/serial", "device/wwn", "serial"):
        v = _run(f"cat /sys/block/{name}/{rel} 2>/dev/null", 3).strip()
        if v and v not in ("0", "none"):
            return v
    return ""


def _nvme_ctrl_name(name: str) -> str:
    m = re.fullmatch(r"(nvme\d+)n\d+", name)
    return m.group(1) if m else ""


def _hwmon_temp_from_file(path: str) -> float | None:
    if not path:
        return None
    raw = _run(f"cat {shlex.quote(path)} 2>/dev/null", 3).strip()
    if not raw.isdigit():
        return None
    v = int(raw)
    if v > 1000:
        v //= 1000
    if 0 < v < 120:
        return float(v)
    return None


def _read_hwmon_block_temp(name: str) -> float | None:
    """NVMe/SATA temps from sysfs (works with /sys:ro, no SMART ioctl)."""
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", name):
        return None
    globs = [
        f"/sys/block/{name}/device/hwmon/hwmon*/temp*_input",
        f"/sys/block/{name}/device/device/hwmon/hwmon*/temp*_input",
    ]
    ctrl = _nvme_ctrl_name(name)
    if ctrl:
        globs.extend(
            [
                f"/sys/class/nvme/{ctrl}/hwmon*/temp*_input",
                f"/sys/class/nvme/{ctrl}/device/hwmon/hwmon*/temp*_input",
            ]
        )
    for pattern in globs:
        for hz in _run(f"ls {pattern} 2>/dev/null", 3).strip().split():
            temp = _hwmon_temp_from_file(hz)
            if temp is not None:
                return temp
    blk_dev = _run(f"readlink -f /sys/block/{name}/device 2>/dev/null", 3).strip()
    for hm in _run("ls -d /sys/class/hwmon/hwmon* 2>/dev/null", 5).split():
        hm = hm.strip()
        if not hm:
            continue
        link = _run(f"readlink -f {hm}/device 2>/dev/null", 3).strip()
        if not link:
            continue
        matched = False
        if blk_dev and (link == blk_dev or blk_dev in link or link in blk_dev):
            matched = True
        if ctrl and ctrl in link.split("/"):
            matched = True
        if not matched:
            continue
        for hz in _run(f"ls {hm}/temp*_input 2>/dev/null", 3).split():
            temp = _hwmon_temp_from_file(hz.strip())
            if temp is not None:
                return temp
    return None


def _list_lsblk_disks() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    raw = _run("lsblk -J -d -o NAME,TYPE,MODEL,TRAN,SERIAL 2>/dev/null", 12)
    try:
        data = json.loads(raw or "{}")
        for ent in data.get("blockdevices") or []:
            if not isinstance(ent, dict):
                continue
            if str(ent.get("type") or "") != "disk":
                continue
            name = str(ent.get("name") or "")
            if not _is_physical_disk_name(name):
                continue
            rows.append({
                "name": name,
                "model": str(ent.get("model") or "").strip(),
                "tran": str(ent.get("tran") or "").strip(),
                "serial": str(ent.get("serial") or "").strip(),
            })
        if rows:
            return rows
    except json.JSONDecodeError:
        pass
    for line in _run("lsblk -d -n -o NAME,TYPE,MODEL,TRAN 2>/dev/null", 10).splitlines():
        parts = line.split(None, 3)
        if len(parts) < 2 or parts[1] != "disk":
            continue
        name = parts[0]
        if not _is_physical_disk_name(name):
            continue
        rows.append({
            "name": name,
            "model": parts[2].strip() if len(parts) > 2 else "",
            "tran": parts[3].strip() if len(parts) > 3 else "",
            "serial": "",
        })
    return rows


def _dedupe_disk_temps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = (row.get("serial") or row.get("name") or row.get("device") or "").strip().lower()
        if not key:
            key = str(row.get("device") or "")
        prev = best.get(key)
        if prev is None:
            best[key] = row
            continue
        # Prefer namespace block device (nvme0n1) over controller (/dev/nvme0).
        score = len(str(row.get("name") or ""))
        prev_score = len(str(prev.get("name") or ""))
        if score > prev_score:
            best[key] = row
    out = list(best.values())
    out.sort(key=lambda r: (0 if str(r.get("tran", "")).lower() == "nvme" else 1, str(r.get("name", ""))))
    return out


def parse_top_processes(raw: str, limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("pid"):
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            cpu = float(parts[0])
            mem = float(parts[1])
            pid = int(parts[2])
        except ValueError:
            continue
        cmd = parts[3].strip()
        rows.append({
            "pid": pid,
            "cpu": round(cpu, 1),
            "mem": round(mem, 1),
            "cmd": cmd[:120],
        })
        if len(rows) >= limit:
            break
    return rows


_TEMP_ATTR_IDS = frozenset({190, 194, 202, 231, 233})


def _plausible_drive_temp_c(v: float) -> bool:
    return 0 < v < 120


def _smart_attr_line_temp_c(line: str) -> float | None:
    """SMART table: use RAW_VALUE (last number), not VALUE — Crucial VALUE can be 63 at 34 °C."""
    s = line.strip()
    if not s or s.startswith("ID#"):
        return None
    m = re.match(r"^\s*(\d+)\s+(\S+)", s)
    if not m:
        return None
    aid = int(m.group(1))
    name = m.group(2).lower()
    if aid not in _TEMP_ATTR_IDS and "temp" not in name:
        return None
    nums: list[int] = []
    for tok in s.split()[3:]:
        if tok.startswith("0x") or tok in ("-", "Always", "Offline"):
            continue
        if tok in ("Old_age", "Pre-fail", "Pre-fail_always"):
            continue
        if re.fullmatch(r"\d+", tok):
            nums.append(int(tok))
    if not nums:
        return None
    raw = float(nums[-1])
    if _plausible_drive_temp_c(raw):
        return raw
    # Some drives only encode temp in VALUE; pick a mid-range column if RAW is bogus.
    for n in reversed(nums[:-1]):
        if 15 <= n <= 70:
            return float(n)
    return None


def _smartctl_temp_from_json(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    temp = data.get("temperature")
    if isinstance(temp, dict):
        cur = temp.get("current")
        if cur is not None:
            v = float(cur)
            if _plausible_drive_temp_c(v):
                return v
    ata = data.get("ata_smart_attributes")
    if isinstance(ata, dict):
        table = ata.get("table") or []
        for ent in table:
            if not isinstance(ent, dict):
                continue
            if ent.get("id") not in _TEMP_ATTR_IDS:
                continue
            raw_obj = ent.get("raw")
            if isinstance(raw_obj, dict) and raw_obj.get("value") is not None:
                v = float(raw_obj["value"])
                if _plausible_drive_temp_c(v):
                    return v
            val = ent.get("value")
            if val is not None:
                v = float(val)
                if 15 <= v <= 70:
                    return v
    return None


def _smartctl_temp_from_text(raw: str) -> float | None:
    if not raw or raw.lstrip().startswith("{"):
        return None
    m = re.search(r"Temperature:\s*(\d+(?:\.\d+)?)\s*Celsius", raw, re.I)
    if m:
        v = float(m.group(1))
        if _plausible_drive_temp_c(v):
            return v
    for line in raw.splitlines():
        t = _smart_attr_line_temp_c(line)
        if t is not None:
            return t
    return None


def collect_raid() -> dict[str, Any]:
    return parse_mdstat(_run("cat /proc/mdstat 2>/dev/null", 8))


def _try_smartctl_disk_temp(
    sc: str, name: str, *, use_skip: bool
) -> tuple[float | None, str, str, bool]:
    temp: float | None = None
    serial = model = ""
    skipped_standby = False
    for target, dtype in _smartctl_targets(name):
        if not os.path.exists(target):
            continue
        t2, si, sm, _raw, skipped = _smartctl_query(
            sc, target, dtype, permissive=False, skip_standby=use_skip
        )
        serial = serial or si
        model = model or sm
        if skipped:
            skipped_standby = True
        if t2 is not None:
            return t2, serial, model, False
        t2, si, sm, _raw, skipped = _smartctl_query(
            sc, target, dtype, permissive=True, skip_standby=use_skip
        )
        serial = serial or si
        model = model or sm
        if skipped:
            skipped_standby = True
        if t2 is not None:
            return t2, serial, model, False
    return temp, serial, model, skipped_standby


def _collect_one_disk_temp(
    disk: dict[str, str],
    sc: str | None,
    *,
    skip_standby: bool = False,
    recent_io: bool = False,
) -> dict[str, Any] | None:
    name = disk["name"]
    dev = f"/dev/{name}"
    if not os.path.exists(dev):
        return None
    model = disk.get("model") or _read_sysfs_model(name)
    serial = disk.get("serial") or _read_sysfs_serial(name)
    tran = (disk.get("tran") or "").lower()
    if name.startswith("nvme"):
        tran = tran or "nvme"
    elif name.startswith("sd"):
        tran = tran or "sata"

    use_skip = _skip_standby_for_disk(name, skip_standby)
    temp: float | None = None
    skipped_standby = False
    # sysfs first — NVMe temps live in hwmon and do not need SMART ioctl (/dev:ro).
    if name.startswith("nvme"):
        temp = _read_hwmon_block_temp(name)
    if temp is None and sc:
        temp, si, sm, skipped_standby = _try_smartctl_disk_temp(sc, name, use_skip=use_skip)
        serial = serial or si
        model = model or sm
        # Disk already had recent I/O → safe to read SMART without waking from sleep.
        # Never retry without -n standby just because the first probe was inconclusive —
        # that would spin sleeping HDDs back up.
        if (
            use_skip
            and temp is None
            and skipped_standby
            and recent_io
        ):
            t2, si2, sm2, _skip2 = _try_smartctl_disk_temp(sc, name, use_skip=False)
            serial = serial or si2
            model = model or sm2
            if t2 is not None:
                temp = t2
                skipped_standby = False
    if temp is None:
        temp = _read_hwmon_block_temp(name)

    label = model or name
    in_standby = use_skip and skipped_standby and temp is None
    return {
        "device": dev,
        "name": name,
        "label": label,
        "model": model,
        "serial": serial,
        "tran": tran.upper() if tran else "",
        "temp_c": round(temp, 1) if temp is not None else None,
        "health": (
            _disk_temp_health(temp)
            if temp is not None
            else ("standby" if in_standby else "unknown")
        ),
        "standby": in_standby,
    }


def collect_disk_temps(*, skip_standby: bool | None = None) -> list[dict[str, Any]]:
    """One row per physical disk (lsblk), deduped by serial — parallel smartctl per disk."""
    if skip_standby is None:
        from settings import get_disk_skip_standby

        skip_standby = get_disk_skip_standby()
    sc = _smartctl_bin()
    disks = _list_lsblk_disks()
    if not disks:
        return []
    io_flags = refresh_disk_io_flags([d["name"] for d in disks])
    rows: list[dict[str, Any]] = []
    workers = min(3, max(1, len(disks)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [
            pool.submit(
                _collect_one_disk_temp,
                d,
                sc,
                skip_standby=skip_standby,
                recent_io=io_flags.get(d["name"], False),
            )
            for d in disks
        ]
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception:
                continue
            if row:
                rows.append(row)
    return _dedupe_disk_temps(rows)


def probe_disk_temps() -> dict[str, Any]:
    """Diagnostic: what smartctl sees per disk (for /api/disk-probe)."""
    from settings import get_disk_skip_standby

    sc = _smartctl_bin()
    skip_sb = get_disk_skip_standby()
    scan = _run(f"{sc} --scan-open 2>&1" if sc else "", 12).strip()
    out_disks: list[dict[str, Any]] = []
    for disk in _list_lsblk_disks():
        name = disk["name"]
        dev = f"/dev/{name}"
        sg = _scsi_generic_for_block(name) if name.startswith("sd") else ""
        entry: dict[str, Any] = {
            "name": name,
            "device": dev,
            "scsi_generic": sg,
            "model": disk.get("model") or _read_sysfs_model(name),
            "tran": disk.get("tran"),
            "exists": os.path.exists(dev),
            "attempts": [],
            "temp_c": None,
        }
        if not sc:
            entry["error"] = "smartctl not found in container"
            out_disks.append(entry)
            continue
        for target, dtype in _smartctl_targets(name):
            if not os.path.exists(target):
                entry["attempts"].append({
                    "target": target,
                    "dtype": dtype or "auto",
                    "missing": True,
                })
                continue
            for permissive in (False, True):
                t2, _si, _sm, snippet, _skipped = _smartctl_query(
                    sc,
                    target,
                    dtype,
                    permissive=permissive,
                    skip_standby=skip_sb,
                )
                entry["attempts"].append({
                    "target": target,
                    "dtype": dtype or "auto",
                    "permissive": permissive,
                    "temp_c": t2,
                    "snippet": snippet,
                })
                if t2 is not None and entry["temp_c"] is None:
                    entry["temp_c"] = t2
        out_disks.append(entry)
    return {
        "smartctl": sc or None,
        "scan_open": scan,
        "disks": out_disks,
    }


def collect_top_processes(limit: int = 5) -> list[dict[str, Any]]:
    raw = _run(
        "ps -eo pcpu,pmem,pid,args --sort=-pcpu 2>/dev/null | head -n 20",
        8,
    )
    return parse_top_processes(raw, limit=limit)


def collect_docker(*, live_stats: bool = True) -> dict[str, Any]:
    """List containers from Docker metadata on the volume (no docker.sock)."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in _docker_container_dirs():
        try:
            folders = os.listdir(root)
        except OSError:
            continue
        for folder in folders:
            if folder in seen or len(folder) < 12:
                continue
            cfg = _read_json_file(os.path.join(root, folder, "config.v2.json"))
            if cfg is None:
                cfg = _read_json_file(os.path.join(root, folder, "config.json"))
            if not cfg:
                continue
            seen.add(folder)
            state = cfg.get("State") if isinstance(cfg.get("State"), dict) else {}
            running = bool(state.get("Running"))
            image = _docker_image(cfg)
            status = _docker_status_text(state)
            row: dict[str, Any] = {
                "name": _docker_name(cfg, folder),
                "status": status,
                "image": image,
                "running": running,
                "health": _docker_health_from_status(status),
                "runlevel": _is_runlevel_container(image, cfg),
                "cpu_live": "",
                "mem_live": "",
            }
            if live_stats and running:
                cid = str(cfg.get("ID") or folder)
                cg = _cgroup_dir(cid) or _cgroup_dir(folder)
                if cg:
                    row["cpu_live"] = _cgroup_cpu_pct(folder, cg)
                    row["mem_live"] = _cgroup_mem(cg)
            rows.append(row)
            if len(rows) >= 64:
                break
        if len(rows) >= 64:
            break
    rows.sort(key=lambda r: (not bool(r.get("running")), str(r.get("name") or "").casefold()))
    return {"containers": rows, "system_df": {}}


def collect_os_info() -> dict[str, str]:
    raw = _run('grep -E "^(PRETTY_NAME|OS_VERSION)=" /etc/os-release 2>/dev/null', 8)
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"')
    out["hostname"] = (_run("hostname 2>/dev/null", 5).strip().splitlines() or ["NAS"])[0]
    out["uptime"] = _run("uptime -p 2>/dev/null", 8).strip().removeprefix("up ")
    return out


def scan_top_folders(bases: list[str] | None = None, depth: int = 2, limit: int = 20) -> list[dict[str, Any]]:
    bases = bases or ["/volume1", "/volume2"]
    existing = [b for b in bases if os.path.isdir(b)]
    if not existing:
        return []
    paths = " ".join(shlex.quote(b) for b in existing)
    cmd = (
        f"timeout 300 sh -c 'du -x --max-depth={depth} {paths} 2>/dev/null "
        f"| sort -nr | head -n {limit + 1}'"
    )
    raw = _run(cmd, timeout=310)
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            kb = int(parts[0])
        except ValueError:
            continue
        path = parts[1].strip()
        if path in existing and depth > 1:
            continue
        rows.append({"path": path, "gb": round(kb / 1024 / 1024, 2), "kb": kb})
        if len(rows) >= limit:
            break
    return rows


_REMOTE_CPU_TEMP = """max=0
for z in /sys/class/thermal/thermal_zone*/temp; do
  [ ! -r "$z" ] && continue
  v=$(cat "$z" 2>/dev/null)
  case "$v" in ""|*[!0-9]*) continue ;; esac
  if [ "$v" -gt 1000 ]; then v=$((v/1000)); fi
  if [ "$v" -gt "$max" ] && [ "$v" -lt 200 ]; then max=$v; fi
done
for f in /sys/class/hwmon/hwmon*/temp*_input; do
  [ ! -r "$f" ] && continue
  case "$f" in *temp*_label*) continue ;; esac
  v=$(cat "$f" 2>/dev/null)
  case "$v" in ""|*[!0-9]*) continue ;; esac
  if [ "$v" -gt 3000 ]; then v=$((v/1000)); fi
  if [ "$v" -gt "$max" ] && [ "$v" -lt 200 ]; then max=$v; fi
done
echo "$max"
"""


def collect_light_tick(*, include_hw_sensors: bool = False) -> dict[str, str]:
    """Fast host read — no df/findmnt (disk I/O), no nsenter (hangs in UGOS Docker)."""
    self_net = _run("cat /proc/net/dev", 5)
    host_net = (
        _run("cat /proc/1/net/dev 2>/dev/null", 5)
        if os.path.exists("/proc/1/net/dev")
        else ""
    )
    use_host = _use_host_netns()
    if not use_host and host_net:
        extra = set(physical_ifaces(host_net)) - set(physical_ifaces(self_net))
        if extra:
            use_host = True
    net = (host_net if use_host else self_net) or self_net
    # Host netns: `ip` in the container is the Docker bridge. IPs come from /proc later.
    if use_host:
        ipj, rtj = "[]", "[]"
    else:
        ipj = _run("ip -j addr 2>/dev/null || echo []", 8)
        rtj = _run("ip -j route 2>/dev/null || echo []", 8)
    out = {
        "cpu": _run("grep '^cpu ' /proc/stat | head -1", 5),
        "mem": _run("free | grep Mem", 5),
        "net": net,
        "ipj": ipj or "[]",
        "rtj": rtj or "[]",
        "load": _run("cat /proc/loadavg", 5),
    }
    if include_hw_sensors:
        out["temp"] = _run(_REMOTE_CPU_TEMP, 8)
        out["fan"] = _run(_REMOTE_FAN, 10)
    return out


def collect_tick_bundle() -> dict[str, str]:
    """Legacy full bundle (tests / manual). Prefer collect_light_tick + collect_df_block."""
    bundle = collect_light_tick(include_hw_sensors=True)
    bundle["df"] = collect_df_block()
    return bundle
