# Stats Hub — User Guide

**App ID:** `com.runlevel.statshub`  
**Port:** 29125  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Live NAS dashboard: CPU, RAM, network, volumes, Docker, RAID/SMART (where available) via UGOS Web API and host metrics.

## Install / configure

1. Install **Docker** suite on the NAS (required dependency).
2. Install **Stats Hub** from App Center (or manual UPK).
3. Set **Data directory** (e.g. `/volume1/docker/stats-hub/data`).
4. Optional: **UGOS API user / password** for richer live metrics (local API on the NAS).
5. Open the app (admin only).

## Core usage

1. Open Stats Hub from the UGOS desktop.
2. Confirm live widgets update (CPU/RAM/network).
3. Check volume / Docker sections.
4. Adjust poll interval / language in settings if needed.
5. Footer links: Help, Privacy, Support (email / Issues).

## Tips

- Admin-only app — do not expose port 29125 to the internet.
- No outbound analytics; data stays on the NAS.
