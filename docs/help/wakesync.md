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
3. Set **UGOS folder shortcut** (source picker). App password, plans, and credentials are stored in the app package directory and are **removed on uninstall**.
4. Optional: **WoL broadcast** / **WoL source IP** (not passwords).
5. Open the app. First screen: **privacy consent** (Agree and Decline). Then set an app password.
6. Telegram / SMTP: configure **inside the app** after Agree (not in App Center install fields).
7. On the **target** device: enable Wake-on-LAN / magic packet.

## Core usage

1. Open Wake & Sync, confirm privacy, sign in.
2. Add **target device** (IP, MAC, SMB credentials). The password is sent encrypted (`password_enc`), not as HTTP plaintext.
3. Create a **plan**: sources → destination, schedule, wait timeout.
4. Enable the plan or run once.
5. Watch job progress; use **Stop** if needed.

## Tips

- Direct cable UGREEN↔target: set source IP to UGREEN’s link IP and broadcast to that subnet.
- Same LAN via router: UGREEN LAN IP + `x.x.x.255` broadcast is usually enough.
- Incremental sync copies only new/changed files.
- Uninstalling the app clears app password and plans. After reinstall you set a new password and see the privacy dialog again.
- Footer: Help, Privacy, Support.
