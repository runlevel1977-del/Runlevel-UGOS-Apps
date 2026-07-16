# Transfer Hub — User Guide

**App ID:** `com.runlevel.transferhub`  
**Port:** 29100  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Copy or sync folders between local volumes, USB, and SMB devices on the LAN. Profiles, schedules, and live job progress.

## Install / configure

1. Install **Docker** suite.
2. Install **Transfer Hub**.
3. Set **Data directory** (e.g. `/volume1/docker/transfer-hub/data`).
4. Optional: **UGOS folder** shortcut, home network / extra hosts for LAN scan, UGOS API credentials.
5. Accept privacy consent when storing SMB credentials (first use).

## Core usage

1. Open Transfer Hub.
2. Add a **device** (local path or SMB host + credentials).
3. Create a **profile**: source → destination, options (copy/sync).
4. Run once (**Start**) or enable a schedule.
5. Watch job progress (bytes, speed, ETA) and stop if needed.
6. Check the log under the data directory on failure.

## Tips

- Use a dedicated data folder (credentials are stored locally as JSON).
- Prefer dedicated SMB accounts with minimal share rights.
- LAN only — no cloud upload by Runlevel.
