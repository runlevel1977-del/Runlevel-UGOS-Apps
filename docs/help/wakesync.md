# Wake & Sync — User Guide

**App ID:** `com.runlevel.wakesync`  
**Port:** 29120  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

On a schedule: Wake-on-LAN a second NAS/PC, wait until SMB is reachable, then run a one-way incremental sync (rclone). Optional Telegram/email alerts.

## Install / configure

1. Install **Docker** suite.
2. Install **Wake & Sync**.
3. Set **Data directory** (e.g. `/volume1/docker/wake-sync/data`).
4. Optional Docker parameters:
   - **WoL broadcast** — subnet broadcast (e.g. `192.168.2.255`), **not** the target NAS IP.
   - **WoL source IP** — **this UGREEN NAS** IP on the link used to send the magic packet (not the QNAP/target IP).
5. Optional: Telegram/SMTP for alerts.
6. Accept privacy consent when storing SMB credentials.
7. On the **target** device: enable Wake-on-LAN / magic packet.

## Core usage

1. Open Wake & Sync.
2. Add **target device** (IP, MAC, SMB credentials).
3. Create a **plan**: sources (one or more folders) → destination base, schedule, wait timeout.
4. Enable the plan or run once.
5. Watch job progress; use **Stop** if needed.
6. Confirm sync completed and alerts (if configured).

## Tips

- Direct cable UGREEN↔target: set source IP to UGREEN’s link IP and broadcast to that subnet.
- Same LAN via router: UGREEN LAN IP + `x.x.x.255` broadcast is usually enough.
- Incremental sync copies only new/changed files.
