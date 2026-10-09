> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Wake & Sync — Privacy & Security Summary

**App ID:** `com.runlevel.wakesync`  
**Publisher:** Runlevel  
**Version:** 0.1.16  

## Data stored locally (on the NAS)

Under the user-chosen **Data directory** (`DATA_PATH`, mounted as `/data` in the container):

| File | Content |
|------|---------|
| `plans.json` | Sync plans (schedule, source/target paths, WoL MAC/IP, wait timeout) |
| `devices.json` | Saved SMB devices including **username and password** |
| `notify.json` | Optional Telegram/SMTP settings (if saved via UI) |
| `wake-sync.log` | Application log (WoL, sync start/end, errors) |

No other persistent user data is collected by Wake & Sync.

## Network behavior

- **Wake-on-LAN:** UDP magic packet to configured broadcast/subnet (local LAN or direct link).
- **SMB / sync:** Connections to target NAS/PC on the local network only (`rclone` over SMB).
- **Notifications:** Optional Telegram API or user-configured SMTP — only when the user enables alerts.
- Wake & Sync does **not** send data to external analytics or cloud services operated by Runlevel.
- Optional link in the UI points to **Ugreen NAS Admin** on GitHub (user-initiated in browser).

## Access control

- App is **admin-only** (`only_admin: true` in `project.yaml`).
- SMB credentials stored in plain JSON on the NAS data path — use dedicated folder with restricted permissions.

## Recommendations for users

- Set `WOL_BROADCAST` and `WOL_SOURCE_IP` for direct-cable links if WoL from Docker bridge fails.
- Use strong SMB passwords and minimal share permissions on the target NAS.
- Do not expose port 29120 to the internet without additional protection.

## Contact

Developer contact for privacy inquiries: runlevel1977@posteo.de (Ivica Kampic, Runlevel)
