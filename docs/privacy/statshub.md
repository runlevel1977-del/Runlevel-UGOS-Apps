> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Stats Hub — Privacy & Security Summary

**App ID:** `com.runlevel.statshub`  
**Publisher:** Runlevel  
**Version:** 0.2.16  

## Data stored locally (on the NAS)

Under the user-chosen **Data directory** (`DATA_PATH`, mounted as `/data` in the container):

| File | Content |
|------|---------|
| `settings.json` | UI preferences (poll interval, language, HDD standby skip) |
| `stats-hub.log` | Application log (errors, collection issues) |

No user credentials are stored. Stats Hub does not persist NAS metrics long-term beyond the in-memory/live dashboard cache.

## Network behavior

- **No outbound connections** to Runlevel or third-party analytics.
- Web UI is served locally on port **29125** (admin access only).
- Optional link in the UI points to **Ugreen NAS Admin** on GitHub (user-initiated).

## Host access (read-only where possible)

- Reads system metrics via local commands and mounts (`/sys`, docker.sock, volume paths).
- **Privileged** container + `/dev` access for **smartctl** disk temperature queries.
- `network_mode: host` so network stats show the NAS LAN address, not Docker bridge.

## Access control

- App is **admin-only** (`only_admin: true`).
- Do not expose port 29125 to the internet without additional protection.

## Data retention

- Settings/log remain until the user deletes the data folder or uninstalls the app.
- Uninstalling typically leaves `DATA_PATH` intact on the NAS.

## Contact

Developer contact for privacy inquiries: runlevel1977@posteo.de (Ivica Kampic, Runlevel)
