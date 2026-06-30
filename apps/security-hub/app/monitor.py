# -*- coding: utf-8 -*-
"""
Login-Track-Logik wie ugreen_app/mixin_login_track.py — nur ohne SSH (NAS-Log-Mounts).
"""
from __future__ import annotations

import threading
import time
from typing import Any

from access_collect import (
    LoginEvent,
    collect_has_payload,
    is_login_track_live_event,
    is_login_track_noise_event,
    live_line_event_key,
    login_event_key,
    parse_collect_delta,
    parse_collect_output,
    sort_login_events,
    summarize_collect_sections,
)
from access_display import format_access_target
from collect_local import local_collect_shell, local_collect_shell_live, probe_mounts, run_bash
from store import append_log, load_settings, save_settings

MAX_EVENTS = 2500
LIVE_INTERVAL_SEC = 4
HISTORY_DAYS_DEFAULT = 30


class AccessMonitor:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: list[LoginEvent] = []
        self._section_prev: dict[str, str] = {}
        self._seen_lines: set[tuple[str, str]] = set()
        self._needs_baseline = True
        self._live_since_epoch = 0.0
        self._busy = False
        self._last_error = ""
        self._diag_lines: list[str] = []
        self._watch_active = False
        self._live_enabled = True
        self._hide_pings = False
        self._days = HISTORY_DAYS_DEFAULT
        self._sort_by = "time"
        self._sort_desc = True
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._load_prefs()

    def _load_prefs(self) -> None:
        s = load_settings()
        self._live_enabled = bool(s.get("live_enabled", True))
        self._hide_pings = bool(s.get("hide_pings", False))
        self._days = int(s.get("history_days", HISTORY_DAYS_DEFAULT) or HISTORY_DAYS_DEFAULT)
        self._sort_by = str(s.get("sort_by", "time") or "time")
        self._sort_desc = bool(s.get("sort_desc", True))

    def _save_prefs(self) -> None:
        save_settings(
            {
                "live_enabled": self._live_enabled,
                "hide_pings": self._hide_pings,
                "history_days": self._days,
                "sort_by": self._sort_by,
                "sort_desc": self._sort_desc,
            }
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="security-hub-monitor", daemon=True)
        self._thread.start()
        append_log("Access monitor started")

    def _loop(self) -> None:
        time.sleep(1.0)
        self.on_enter()
        while not self._stop.is_set():
            if self._watch_active:
                self._poll_watch()
            self._stop.wait(LIVE_INTERVAL_SEC)

    def is_busy(self) -> bool:
        with self._lock:
            return self._busy

    def _visible_events(self, events: list[LoginEvent]) -> list[LoginEvent]:
        since = float(self._live_since_epoch or 0)
        out: list[LoginEvent] = []
        for ev in events:
            if self._hide_pings and is_login_track_noise_event(ev):
                continue
            if self._live_enabled and since > 0 and not is_login_track_live_event(ev, since_epoch=since):
                continue
            out.append(ev)
        return out

    def _diag_from_raw(self, raw: str, stats: dict[str, int] | None = None) -> list[str]:
        lines: list[str] = []
        if not collect_has_payload(raw):
            return lines
        sections = summarize_collect_sections(raw)
        if not sections:
            lines.append("no_sections")
        else:
            parts = [f"{name}={count}" for name, count in sorted(sections.items())]
            lines.append("sections:" + ", ".join(parts))
        stats = stats or {}
        if stats.get("baseline"):
            lines.append("baseline")
        elif stats:
            lines.append(
                f"delta:raw={int(stats.get('raw_lines', 0) or 0)},parsed={int(stats.get('parsed', 0) or 0)}"
            )
        return lines

    def _reset_watch_state(self, *, clear_events: bool) -> None:
        if clear_events:
            self._events = []
            self._last_error = ""
        self._section_prev = {}
        self._seen_lines = set()
        self._needs_baseline = True
        self._diag_lines = []

    def _append_delta(self, raw: str) -> dict[str, int]:
        with self._lock:
            baseline = self._needs_baseline
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            live_only = self._live_enabled
            since = float(self._live_since_epoch or 0)
            delta, new_prev, stats = parse_collect_delta(
                raw,
                self._section_prev,
                baseline=baseline,
                observed_at=stamp,
                since_epoch=since if live_only else 0.0,
            )
            self._section_prev = new_prev
            if baseline:
                self._needs_baseline = False
                self._live_since_epoch = time.time()
                since = self._live_since_epoch
            existing = {login_event_key(ev) for ev in self._events}
            for section, line, ev in delta:
                key = live_line_event_key(section, line, ev)
                if key in self._seen_lines:
                    continue
                if self._hide_pings and is_login_track_noise_event(ev):
                    self._seen_lines.add(key)
                    continue
                if live_only and since > 0 and not is_login_track_live_event(ev, since_epoch=since):
                    self._seen_lines.add(key)
                    continue
                ev_key = login_event_key(ev)
                if ev_key in existing:
                    self._seen_lines.add(key)
                    continue
                self._seen_lines.add(key)
                existing.add(ev_key)
                self._events.append(ev)
            if len(self._events) > MAX_EVENTS:
                self._events = self._events[-MAX_EVENTS:]
            self._diag_lines = self._diag_from_raw(raw, stats)
            return stats

    def on_enter(self) -> None:
        """Entspricht login_track_on_tab_enter."""
        if self.is_busy():
            return
        if self._live_enabled:
            if not self._watch_active:
                self._live_since_epoch = time.time()
                self._reset_watch_state(clear_events=True)
                self._watch_active = True
            return
        if not self._events:
            self.refresh(start_watch_after=True)
        else:
            with self._lock:
                self._needs_baseline = True
                self._watch_active = True

    def refresh(self, *, start_watch_after: bool = True) -> bool:
        """Entspricht login_track_refresh."""
        if self.is_busy():
            return False
        if self._live_enabled:
            with self._lock:
                self._live_since_epoch = time.time()
                self._reset_watch_state(clear_events=True)
                self._watch_active = True
            append_log("refresh: live mode reset")
            return True

        mount_issues = probe_mounts()
        if mount_issues:
            msg = "; ".join(mount_issues)
            with self._lock:
                self._last_error = msg
            append_log(f"history collect mount error: {msg}")
            return False

        with self._lock:
            self._busy = True
        try:
            script = local_collect_shell(days=self._days)
            raw, err = run_bash(script, timeout=120)
            events: list[LoginEvent] = []
            if not collect_has_payload(raw):
                with self._lock:
                    self._last_error = (raw.strip()[:2000] or err[:2000] or "collect failed")
                    self._events = []
                    self._diag_lines = []
            else:
                events = parse_collect_output(raw)
                with self._lock:
                    self._last_error = err[:2000] if err else ""
                    self._events = events[-MAX_EVENTS:]
                    self._needs_baseline = True
                    self._diag_lines = self._diag_from_raw(raw)
            append_log(f"history refresh: {len(events)} events")
            if start_watch_after:
                with self._lock:
                    self._watch_active = True
            return True
        except Exception as ex:
            with self._lock:
                self._last_error = str(ex)
                self._events = []
            append_log(f"history refresh failed: {ex}")
            return False
        finally:
            with self._lock:
                self._busy = False

    def _poll_watch(self) -> None:
        """Entspricht _login_track_poll_watch (immer remote_collect_shell_live)."""
        if self.is_busy():
            return
        with self._lock:
            self._busy = True
        try:
            script = local_collect_shell_live(since_minutes=5)
            raw, err = run_bash(script, timeout=45)
            if not collect_has_payload(raw):
                with self._lock:
                    self._last_error = raw.strip()[:2000] or err[:500]
                return
            self._append_delta(raw)
            with self._lock:
                if err:
                    self._last_error = err[:500]
        except Exception as ex:
            with self._lock:
                self._last_error = str(ex)[:500]
        finally:
            with self._lock:
                self._busy = False

    def set_live(self, enabled: bool) -> None:
        """Entspricht _login_track_toggle_live."""
        with self._lock:
            self._live_enabled = enabled
            if enabled:
                self._live_since_epoch = time.time()
                self._reset_watch_state(clear_events=True)
                self._watch_active = True
            else:
                self._live_since_epoch = 0.0
                self._reset_watch_state(clear_events=False)
                if self._watch_active:
                    self._needs_baseline = True
        self._save_prefs()

    def set_hide_pings(self, hide: bool) -> None:
        with self._lock:
            self._hide_pings = hide
        self._save_prefs()

    def set_days(self, days: int) -> None:
        self._days = max(7, min(90, int(days)))
        self._save_prefs()

    def set_sort(self, sort_by: str, sort_desc: bool) -> None:
        with self._lock:
            self._sort_by = sort_by if sort_by in ("time", "ip", "user", "source", "outcome") else "time"
            self._sort_desc = sort_desc
        self._save_prefs()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            visible = self._visible_events(list(self._events))
            sorted_ev = sort_login_events(
                visible,
                self._sort_by,
                reverse=self._sort_desc,
            )
            live_waiting = self._live_enabled and not sorted_ev and self._needs_baseline
            ugos_model = ""
            ugos_ok = False
            try:
                from store import DATA_DIR, append_log
                from ugos_support import fetch_metrics

                metrics = fetch_metrics(DATA_DIR, log=append_log)
                if metrics and metrics.get("ok"):
                    ugos_ok = True
                    ugos_model = str(metrics.get("model") or "")
            except Exception:
                pass
            return {
                "events": [_event_dict(ev) for ev in sorted_ev],
                "count": len(sorted_ev),
                "busy": self._busy,
                "live_enabled": self._live_enabled,
                "hide_pings": self._hide_pings,
                "days": self._days,
                "sort_by": self._sort_by,
                "sort_desc": self._sort_desc,
                "error": self._last_error,
                "diag": list(self._diag_lines),
                "live_waiting": live_waiting,
                "ugos_ok": ugos_ok,
                "ugos_model": ugos_model,
            }


def _event_dict(ev: LoginEvent) -> dict[str, str]:
    access = format_access_target(ev)
    return {
        "timestamp": ev.timestamp or "",
        "ip": ev.ip or "",
        "source": ev.source or "",
        "outcome": ev.outcome or "",
        "user": ev.user or "",
        "access": access,
        "detail": ev.detail or "",
    }


_monitor: AccessMonitor | None = None


def get_monitor() -> AccessMonitor:
    global _monitor
    if _monitor is None:
        _monitor = AccessMonitor()
    return _monitor
