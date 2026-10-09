> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Security Hub — Privacy & Security Summary

**App ID:** `com.runlevel.securityhub`  
**Publisher:** Runlevel  
**Version:** 0.1.10  

## Data stored locally (on the NAS)

Under the user-chosen **Data directory** (`DATA_PATH`, mounted as `/data` in the container):

| File | Content |
|------|---------|
| `settings.json` | UI preferences (language, display options) |
| `security-hub.log` | Application log |

Parsed login events are read from host logs at query time; Security Hub does **not** copy full system logs into `DATA_PATH`.

## Network behavior

- **No outbound connections** to Runlevel or third-party analytics.
- Web UI is served on port **29130** (admin access only).
- Optional link in the UI points to **Ugreen NAS Admin** on GitHub (user-initiated).

## Host access (read-only)

| Mount | Purpose |
|-------|---------|
| `/var/log` (read-only) | SSH/auth, system logs |
| `/var/ugreen/log` (read-only) | UGOS services, SMB audit, app/web logins |

Security Hub does **not** modify logs, firewall rules, or `block_ip_list`.

## Access control

- App is **admin-only** (`only_admin: true`).
- Displayed data may include **client IP addresses** and usernames from auth logs — visible only to NAS administrators.
- Do not expose port 29130 to the internet without additional protection.

## Data retention

- Settings/log remain until the user deletes the data folder.
- Uninstalling typically leaves `DATA_PATH` intact on the NAS.

## Contact

Developer contact for privacy inquiries: runlevel1977@posteo.de (Ivica Kampic, Runlevel)
