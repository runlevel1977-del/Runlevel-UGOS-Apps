# -*- coding: utf-8 -*-
"""Live monitor — same tick logic as NAS Admin dashboard_monitor_loop."""
from __future__ import annotations

import threading
import time
from typing import Any

from collect import (
    collect_df_block,
    collect_disk_temps,
    collect_docker,
    collect_light_tick,
    collect_os_info,
    collect_raid,
    collect_top_processes,
    cpu_pct,
    fmt_rate,
    parse_cpu_line,
    parse_cpu_temp_c,
    parse_default_route_dev,
    parse_fan_rpms,
    parse_ip_addr,
    parse_ram_pct,
    parse_volumes,
    physical_ifaces,
)
from runlevel_apps import collect_runlevel_apps
from settings import get_disk_poll_interval_sec, load_settings
from store import append_log
from ugos_poll import (
    fetch_ugos_metrics,
    last_ugos_status,
    last_ugos_volumes,
    merge_disk_temps,
    merge_ifaces,
    merge_volumes,
    set_last_ugos_volumes,
    ugos_disks_to_temps,
    ugos_volumes_to_snapshot,
)

_HISTORY = 90
# Main loop: light tick every TICK_SEC; heavy work on separate counters.
ACTIVE_TICK_SEC = 3.0
IDLE_TICK_SEC = 30.0
IDLE_AFTER_SEC = 45.0  # no visible browser tab polling this long → pause background work
DF_EVERY_N = 20          # ~60 s active
HW_SENSORS_EVERY_N = 10  # ~30 s (CPU temp, fan RPM)
DOCKER_LIST_EVERY_N = 20  # ~60 s container list
DOCKER_STATS_EVERY_N = 40  # ~120 s docker stats + system df
SLOW_EVERY_N = 40        # ~120 s top processes + runlevel apps

_lock = threading.Lock()
_client_wake = threading.Event()
_wake_refresh_lock = threading.Lock()
_wake_refresh_running = False
_last_client_at = 0.0
_state: dict[str, Any] = {
    "ok": False,
    "cpu": None,
    "ram": None,
    "cpu_temp_c": None,
    "load": "",
    "fans": [],
    "volumes": [],
    "ifaces": [],
    "docker": [],
    "docker_df": {},
    "raid": {},
    "disk_temps": [],
    "disk_temps_updated": None,
    "processes": [],
    "runlevel_apps": [],
    "os": {},
    "history": {"cpu": [], "ram": [], "ts": []},
    "top_folders": [],
    "top_scanning": False,
    "top_updated": None,
    "data_source": "host",
    "ugos_ok": False,
    "ugos_error": "",
    "ugos_model": "",
    "ugos_pools": [],
    "ugos_disks": [],
}
_prev_cpu: tuple[int, int] | None = None
_prev_net: dict[str, tuple[int, int]] = {}
_running = False


def touch_client_activity() -> None:
    """Browser tab visible and polling — keep full monitor rate."""
    global _last_client_at
    was_active = _clients_active()
    _last_client_at = time.time()
    _client_wake.set()
    if not was_active:
        def _wake_worker() -> None:
            global _wake_refresh_running
            with _wake_refresh_lock:
                if _wake_refresh_running:
                    return
                _wake_refresh_running = True
            try:
                _run_full_refresh()
            finally:
                _wake_refresh_running = False

        threading.Thread(target=_wake_worker, daemon=True, name="stats-wake").start()


def _clients_active() -> bool:
    # Like 0.2.25 until we have seen UI polls; idle only after they stop.
    if _last_client_at <= 0:
        return True
    return (time.time() - _last_client_at) < IDLE_AFTER_SEC


def _wait_while_idle() -> None:
    """Block until UI activity or idle sleep slice ends."""
    while _running and not _clients_active():
        _client_wake.wait(timeout=IDLE_TICK_SEC)
        _client_wake.clear()


def _run_full_refresh() -> None:
    """Immediate collect when UI opens after idle — temps/fans/disks without waiting."""
    append_log("Monitor wake — full refresh")
    try:
        bundle = collect_light_tick(include_hw_sensors=True)
        df_text = collect_df_block()
        _apply_tick(bundle, df_text=df_text, update_hw=True)
    except Exception as ex:
        append_log(f"Wake host refresh error: {ex}")
    try:
        raid = collect_raid()
        disks = collect_disk_temps()
        with _lock:
            ug_disks = list(_state.get("ugos_disks") or [])
        if ug_disks:
            disks = merge_disk_temps(disks, ug_disks)
        with _lock:
            _state["raid"] = raid
            _state["disk_temps"] = disks
            _state["disk_temps_updated"] = int(time.time())
    except Exception as ex:
        append_log(f"Wake storage refresh error: {ex}")
    try:
        with _lock:
            host_ifaces = list(_state.get("ifaces") or [])
        ugos = fetch_ugos_metrics(force=True)
        if ugos and ugos.get("ok"):
            _apply_ugos(ugos, host_ifaces)
        else:
            _mark_ugos_fallback()
    except Exception as ex:
        append_log(f"Wake UGOS error: {ex}")
    try:
        dk = collect_docker(live_stats=True)
        with _lock:
            _state["docker"] = dk.get("containers", [])
            _state["docker_df"] = dk.get("system_df", {})
    except Exception as ex:
        append_log(f"Wake docker error: {ex}")
    try:
        with _lock:
            _state["processes"] = collect_top_processes(5)
            _state["runlevel_apps"] = collect_runlevel_apps()
    except Exception as ex:
        append_log(f"Wake slow tick error: {ex}")
    try:
        os_info = collect_os_info()
        with _lock:
            _state["os"] = os_info
    except Exception as ex:
        append_log(f"Wake os info error: {ex}")


def _push_hist(key: str, val: float | None) -> None:
    hist = _state["history"]
    if val is None:
        return
    arr = hist.setdefault(key, [])
    arr.append(round(float(val), 1))
    if len(arr) > _HISTORY:
        del arr[: len(arr) - _HISTORY]
    ts = hist.setdefault("ts", [])
    ts.append(int(time.time()))
    if len(ts) > _HISTORY:
        del ts[: len(ts) - _HISTORY]


def _apply_tick(
    bundle: dict[str, str],
    *,
    df_text: str | None = None,
    update_hw: bool = False,
) -> None:
    global _prev_cpu, _prev_net
    cur_cpu = parse_cpu_line(bundle.get("cpu", ""))
    cpu = cpu_pct(_prev_cpu, cur_cpu)
    if cur_cpu:
        _prev_cpu = cur_cpu
    ram = parse_ram_pct(bundle.get("mem", ""))
    volumes = parse_volumes(df_text) if df_text else None
    phys = physical_ifaces(bundle.get("net", ""))
    ip_info = parse_ip_addr(bundle.get("ipj", ""), phys)
    _gw, def_dev = parse_default_route_dev(bundle.get("rtj", ""))
    ifaces_out: list[dict[str, Any]] = []
    for ifn, (rx, tx) in phys.items():
        pr = _prev_net.get(ifn)
        rx_bps = tx_bps = None
        if pr is not None:
            rx_bps = max(0.0, float(rx - pr[0]))
            tx_bps = max(0.0, float(tx - pr[1]))
        _prev_net[ifn] = (rx, tx)
        meta = ip_info.get(ifn, {})
        ifaces_out.append({
            "name": ifn,
            "rx_bps": rx_bps,
            "tx_bps": tx_bps,
            "rx_h": fmt_rate(rx_bps or 0) if rx_bps is not None else "—",
            "tx_h": fmt_rate(tx_bps or 0) if tx_bps is not None else "—",
            "state": meta.get("state", ""),
            "mac": meta.get("mac", ""),
            "addrs": meta.get("addrs", []),
            "default_route": ifn == def_dev,
            "gateway": _gw if ifn == def_dev else "",
        })
    load_parts = bundle.get("load", "").strip().split()
    load_s = f"{load_parts[0]} {load_parts[1]} {load_parts[2]}" if len(load_parts) >= 3 else ""
    cpu_temp = parse_cpu_temp_c(bundle.get("temp", "")) if update_hw else None
    fans = parse_fan_rpms(bundle.get("fan", "")) if update_hw else None
    with _lock:
        _state["ok"] = True
        _state["cpu"] = round(cpu, 1) if cpu is not None else None
        _state["ram"] = round(ram, 1) if ram is not None else None
        if update_hw and cpu_temp is not None:
            _state["cpu_temp_c"] = cpu_temp
        if update_hw and fans is not None:
            _state["fans"] = [{"label": a, "rpm": b} for a, b in fans]
            _state["fan_count"] = len(fans)
        _state["load"] = load_s
        if volumes is not None:
            _state["volumes"] = merge_volumes(volumes, last_ugos_volumes())
        _state["ifaces"] = ifaces_out
        _push_hist("cpu", cpu)
        _push_hist("ram", ram)


def _safe_float(val: object) -> float | None:
    try:
        if val is None:
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val: object) -> int | None:
    f = _safe_float(val)
    if f is None:
        return None
    return int(round(f))


def _apply_ugos(ugos: dict[str, Any], host_ifaces: list[dict[str, Any]]) -> None:
    try:
        with _lock:
            cpu = _safe_float(ugos.get("cpu"))
            if cpu is not None:
                cpu = round(cpu, 1)
                _state["cpu"] = cpu
                _push_hist("cpu", cpu)
            ram = _safe_float(ugos.get("ram"))
            if ram is not None:
                ram = round(ram, 1)
                _state["ram"] = ram
                _push_hist("ram", ram)
            temp = _safe_float(ugos.get("cpu_temp_c"))
            if temp is not None:
                _state["cpu_temp_c"] = round(temp, 1)
            rpm = _safe_int(ugos.get("fan_rpm"))
            if rpm is not None:
                _state["fans"] = [{"label": "Fan", "rpm": rpm}]
                _state["fan_count"] = 1
            vols = ugos_volumes_to_snapshot(list(ugos.get("volume_usage") or []))
            set_last_ugos_volumes(vols)
            if vols:
                host_vols = list(_state.get("volumes") or [])
                _state["volumes"] = merge_volumes(host_vols, vols)
            if ugos.get("net_ifaces"):
                _state["ifaces"] = merge_ifaces(host_ifaces, list(ugos["net_ifaces"]))
            _state["ugos_ok"] = True
            _state["data_source"] = "ugos"
            _state["ugos_model"] = str(ugos.get("model") or "")
            _state["ugos_pools"] = list(ugos.get("pools") or [])
            ug_disks = list(ugos.get("disks") or [])
            _state["ugos_disks"] = ug_disks
            host_temps = list(_state.get("disk_temps") or [])
            if host_temps and ug_disks:
                _state["disk_temps"] = merge_disk_temps(host_temps, ug_disks)
            elif not host_temps and ug_disks:
                ug_t = ugos_disks_to_temps(ug_disks)
                if ug_t:
                    _state["disk_temps"] = ug_t
            st = last_ugos_status()
            _state["ugos_error"] = str(st.get("ugos_error") or "")
    except Exception as ex:
        append_log(f"UGOS apply error: {ex}")


def _mark_ugos_fallback() -> None:
    with _lock:
        _state["ugos_ok"] = False
        _state["data_source"] = "host"
        st = last_ugos_status()
        _state["ugos_error"] = str(st.get("ugos_error") or "")


def _disk_raid_loop() -> None:
    """Dedicated loop — smartctl can run longer than the UI poll interval."""
    append_log("Disk/RAID monitor started")
    while _running:
        if not _clients_active():
            _wait_while_idle()
            continue
        try:
            raid = collect_raid()
            disks = collect_disk_temps()
            with _lock:
                ug_disks = list(_state.get("ugos_disks") or [])
            if ug_disks:
                disks = merge_disk_temps(disks, ug_disks)
            with _lock:
                _state["raid"] = raid
                _state["disk_temps"] = disks
                _state["disk_temps_updated"] = int(time.time())
            append_log(f"Storage refresh: {len(disks)} disk temps")
        except Exception as ex:
            append_log(f"Storage refresh error: {ex}")
        interval = get_disk_poll_interval_sec()
        for _ in range(int(interval * 10)):
            if not _running or not _clients_active() or _client_wake.is_set():
                break
            time.sleep(0.1)
        _client_wake.clear()


def _loop() -> None:
    global _running
    append_log(
        f"Monitor started (full rate while UI open, pause after {int(IDLE_AFTER_SEC)}s without poll)"
    )
    tick = 0
    os_once = False
    idle_logged = False
    while _running:
        if not _clients_active():
            if not idle_logged:
                append_log("Monitor paused — UI tab closed or hidden")
                idle_logged = True
            _wait_while_idle()
            tick = 0
            continue
        if idle_logged:
            append_log("Monitor resumed — full polling")
            idle_logged = False

        tick += 1
        host_ok = False
        try:
            hw = tick % HW_SENSORS_EVERY_N == 1
            bundle = collect_light_tick(include_hw_sensors=hw)
            df_text = collect_df_block() if tick % DF_EVERY_N == 1 else None
            _apply_tick(bundle, df_text=df_text, update_hw=hw)
            host_ok = True
        except Exception as ex:
            append_log(f"Monitor host tick error: {ex}")
            with _lock:
                _state["ok"] = False

        if host_ok:
            host_ifaces: list[dict[str, Any]] = []
            with _lock:
                host_ifaces = list(_state.get("ifaces") or [])
            try:
                ugos = fetch_ugos_metrics()
                if ugos and ugos.get("ok") and not ugos.get("cached"):
                    _apply_ugos(ugos, host_ifaces)
                elif ugos and ugos.get("cached"):
                    with _lock:
                        _state["ugos_ok"] = True
                        _state["data_source"] = "ugos"
                else:
                    _mark_ugos_fallback()
            except Exception as ex:
                append_log(f"Monitor UGOS tick error: {ex}")
                _mark_ugos_fallback()

            if tick % DOCKER_LIST_EVERY_N == 1:
                try:
                    live = tick % DOCKER_STATS_EVERY_N == 1
                    dk = collect_docker(live_stats=live)
                    with _lock:
                        _state["docker"] = dk.get("containers", [])
                        if live:
                            _state["docker_df"] = dk.get("system_df", {})
                except Exception as ex:
                    append_log(f"Monitor docker error: {ex}")

            if tick % SLOW_EVERY_N == 1:
                try:
                    procs = collect_top_processes(5)
                    apps = collect_runlevel_apps()
                    with _lock:
                        _state["processes"] = procs
                        _state["runlevel_apps"] = apps
                except Exception as ex:
                    append_log(f"Monitor slow tick error: {ex}")

            if not os_once:
                try:
                    os_info = collect_os_info()
                    with _lock:
                        _state["os"] = os_info
                    os_once = True
                except Exception as ex:
                    append_log(f"Monitor os info error: {ex}")

        time.sleep(ACTIVE_TICK_SEC)


def snapshot() -> dict[str, Any]:
    import copy

    with _lock:
        snap = copy.deepcopy(_state)
    from settings import settings_for_api

    snap["disk_settings"] = settings_for_api()
    return snap


def start_monitor() -> None:
    global _running
    if _running:
        return
    _running = True
    threading.Thread(target=_disk_raid_loop, daemon=True, name="stats-disk").start()
    threading.Thread(target=_loop, daemon=True, name="stats-monitor").start()


def set_top_folders(rows: list[dict[str, Any]], *, scanning: bool) -> None:
    with _lock:
        _state["top_folders"] = rows
        _state["top_scanning"] = scanning
        if not scanning:
            _state["top_updated"] = int(time.time())
