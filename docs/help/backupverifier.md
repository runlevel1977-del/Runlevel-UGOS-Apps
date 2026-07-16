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
3. Set **Data directory** (e.g. `/volume1/docker/backup-verifier/data`).
4. Optional: UGOS folder shortcut, LAN scan settings, Telegram/SMTP.
5. Accept privacy consent when storing SMB credentials.

## Core usage

1. Open Backup Verifier.
2. Add devices if comparing remote SMB shares.
3. Create a **job**: left path (source/original) vs right path (backup).
4. Run verification (read-only — no writes to compared folders).
5. Review mismatch report / log.
6. Optional: enable schedule + notifications.

## Tips

- Prefer read-only SMB accounts on backup shares.
- Volume mounts in the container are read-only where applicable.
