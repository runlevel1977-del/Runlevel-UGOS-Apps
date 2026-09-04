# Backup Verifier — User Guide

**App ID:** `com.runlevel.backupverifier`  
**Port:** 29110  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Read-only comparison of two folder trees (local or SMB) to verify backups match. Optional Telegram/email alerts on mismatch.

## Install / configure

1. Install **Docker** suite.
2. Install **Backup Verifier**.
3. Set **UGOS folder shortcut** (folder picker). App password, jobs, and credentials are stored in the app package directory and are **removed on uninstall**.
4. Optional: LAN scan CIDR / extra hosts (not passwords).
5. Open the app. First screen: **privacy consent** (Agree and Decline). Then set an app password.
6. Telegram / SMTP: configure **inside the app** after Agree (not in App Center install fields).

## Core usage

1. Open Backup Verifier, confirm privacy, sign in.
2. Add devices if comparing remote SMB shares. The password is sent encrypted (`password_enc`), not as HTTP plaintext.
3. Create a **job**: left path (source/original) vs right path (backup).
4. Run verification (read-only — no writes to compared folders).
5. Review mismatch report / log.
6. Optional: enable schedule + notifications.

## Tips

- Prefer read-only SMB accounts on backup shares.
- Volume mounts in the container are read-only where applicable.
- Uninstalling the app clears the app password and jobs. After reinstall you set a new password and see the privacy dialog again.
- Footer: Help, Privacy, Support.
