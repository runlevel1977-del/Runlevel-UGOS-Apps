# Stats Hub — User Guide

**App ID:** `com.runlevel.statshub`  
**Port:** 29125  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Live NAS dashboard: CPU, RAM, network, volumes, RAID/SMART (where available) via UGOS Web API and host metrics. Docker container listing is not included (the app does not mount `docker.sock`).

## Install / configure

1. Install **Docker** suite on the NAS (required dependency).
2. Install **Stats Hub** from App Center (or manual UPK).
3. Set **Data directory** (e.g. `/volume1/docker/stats-hub/data`). After a reinstall, use an empty folder if you want the first-launch privacy dialog again.
4. Open the app. First screen: **privacy consent** (Agree and Decline, equally visible). Then set an app password.
5. Optional: **UGOS API user / password** in the app (after Agree) for richer live metrics. The password is not sent as HTTP plaintext.

## Core usage

1. Open Stats Hub from the UGOS desktop.
2. Confirm the privacy dialog, then sign in with the app password.
3. Confirm live widgets update (CPU/RAM/network).
4. Check volumes / disks. Docker listing is not available (no `docker.sock`).
5. Footer links: Help, Privacy, Support (email / Issues).

## Tips

- Admin-only app — do not expose port 29125 to the internet.
- No outbound analytics; data stays on the NAS.
- Network widgets read the **NAS** network namespace (not the Docker bridge). You should see LAN interfaces, not `172.17.0.2`.
- Disk temperatures: NVMe from sysfs; HDDs via SMART. With **HDD: do not wake from standby**, sleeping drives stay blank / Standby.
- UGOS API: enter the NAS user **and** password, then **Save**. Browser autofill in the password box is not enough; the status line shows whether a password is stored.
