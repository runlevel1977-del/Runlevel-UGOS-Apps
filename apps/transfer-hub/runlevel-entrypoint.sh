#!/bin/sh
# UGOS App Center runs "docker compose up" on NAS boot — unlike Docker Projects
# (e.g. MeTube), unless-stopped does not keep manually stopped apps down.
# restart:no + this entrypoint: stay idle after boot when flag=0; App Center
# restart/start sets force flag via SIGTERM while idle.
set -e

DATA_DIR="${RUNLEVEL_DATA_DIR:-/data}"
FLAG="${DATA_DIR}/.runlevel_autostart"
FORCE="${DATA_DIR}/.runlevel_force_start"
GRACE="${RUNLEVEL_BOOT_GRACE_SEC:-120}"
child=""
MODE=run

mkdir -p "$DATA_DIR"
[ ! -f "$FLAG" ] && echo 1 >"$FLAG"

on_term() {
  if [ "$MODE" = "run" ]; then
    echo 0 >"$FLAG"
    rm -f "$FORCE"
    echo "runlevel-entrypoint: manual stop — stays down after NAS boot until App Center start"
    if [ -n "$child" ]; then
      kill -TERM "$child" 2>/dev/null || true
      wait "$child" 2>/dev/null || true
    fi
  else
    echo 1 >"$FORCE"
    echo "runlevel-entrypoint: App Center start requested"
    kill -TERM "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
  exit 0
}

trap on_term TERM INT

if [ "$(cat "$FLAG" 2>/dev/null)" = "0" ]; then
  if [ -f "$FORCE" ] && [ "$(cat "$FORCE" 2>/dev/null)" = "1" ]; then
    rm -f "$FORCE"
    echo 1 >"$FLAG"
    echo "runlevel-entrypoint: resuming after App Center start"
  else
    uptime_sec=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 99999)
    if [ "$uptime_sec" -ge "$GRACE" ]; then
      echo 1 >"$FLAG"
      echo "runlevel-entrypoint: manual start (uptime ${uptime_sec}s) — resuming"
    else
      MODE=idle
      echo "runlevel-entrypoint: autostart disabled — idle until App Center start"
      exec sleep infinity
    fi
  fi
fi

"$@" &
child=$!
wait "$child"
