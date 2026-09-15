# Moving Files — User Guide

**App ID:** `com.runlevel.movingfiles`  
**Port:** 21010  
**Type:** native UGOS app (not Docker)  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Copy or move folders between this NAS and SMB devices on the LAN. Independent jobs, Wake-on-LAN before a copy, and `.tar.gz` backup archives with an optional password. Restore extracts into the folder you choose (including the original folder name).

## Install / configure

1. Install **Moving Files** from App Center (or the `.upk`). Docker is **not** required.
2. Grant **NAS folders (Volume 1)** — required. Optional: **Volume 2 / HDD** for a second copy.
3. After changing granted folders, **restart the app**.
4. Open Moving Files (desktop window). Admin only. First screen: **privacy consent** (Agree and Decline). The in-app UI is German or English (DE/EN switch).

Uninstall removes the app data directory (`state.json`, schedules, stored credentials).

## Core usage

1. **Connections** — this NAS is already there. Add an SMB device (host, share, user, password) and a MAC address if you want Wake-on-LAN.
2. **Jobs** — source → destination, copy or move, optional schedule. Jobs run independently.
3. **Wake** — if the destination has a MAC and is offline, the app sends a magic packet and waits (5 / 10 / 20 / 40 min) before copying.
4. **Backup** — pick source and destination, keep 7 / 14 / 30 archives. Optional checkbox: protect the archive with a password (min. 4 characters). Encrypted files end with `.tar.gz.enc`. Forgotten password = cannot restore.
5. **Restore** — choose archives and a local destination folder. Encrypted archives require the same password.

## Tips

- Grant only the folders you need (not the whole NAS).
- Prefer a dedicated SMB account with minimal share rights.
- Scheduled backups reuse the stored archive password; leave the fields empty to keep it, uncheck the box to write new archives without a password.
- Older unencrypted `.tar.gz` backups still restore without a password.
- Companion Windows tool: [Ugreen NAS Admin](https://github.com/runlevel1977-del/UgreenNASAdmin).
