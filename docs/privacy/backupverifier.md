> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Backup Verifier — Privacy & Security Summary

**App ID:** `com.runlevel.backupverifier`  
**Publisher:** Runlevel  
**Version:** 0.3.4  

## Data stored locally (on the NAS)

Under the user-chosen **Data directory** (`DATA_PATH`, mounted as `/data` in the container):

| File | Content |
|------|---------|
| `jobs.json` | Verification jobs (endpoints, schedule, options) |
| `devices.json` | Saved SMB devices including **username and password** |
| `notify.json` | Optional Telegram/SMTP settings (if saved via UI) |
| `verifier.log` | Application log (job start/end, mismatch details) |

No other persistent user data is collected by Backup Verifier.

## Network behavior

- **Read-only** access to local paths and SMB shares — no writes to compared folders.
- LAN scan (`LAN_SUBNET`) probes hosts on the local network only.
- Optional Telegram API or user-configured SMTP for alerts — only when enabled.
- Backup Verifier does **not** send data to external analytics or cloud services operated by Runlevel.
- Optional link in the UI points to **Ugreen NAS Admin** on GitHub (user-initiated in browser).

## Access control

- App is **admin-only** (`only_admin: true` in `project.yaml`).
- All volume mounts in `docker-compose.yaml` are **read-only** (`:ro`).
- SMB credentials stored in plain JSON — use dedicated data folder with restricted permissions.

## Recommendations for users

- Run verification against copies or backup shares where possible.
- Use separate SMB accounts with read-only share permissions where supported.
- Do not expose port 29110 to the internet without additional protection.

## Contact

Developer contact for privacy inquiries: runlevel1977@posteo.de (Ivica Kampic, Runlevel)
