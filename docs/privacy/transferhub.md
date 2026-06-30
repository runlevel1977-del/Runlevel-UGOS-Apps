> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Transfer Hub — Privacy & Security Summary

**App ID:** `com.runlevel.transferhub`  
**Publisher:** Runlevel  
**Version:** 0.6.10  

## Data stored locally (on the NAS)

Under the user-chosen **Data directory** (`DATA_PATH`, mounted as `/data` in the container):

| File | Content |
|------|---------|
| `profiles.json` | Transfer profiles (source/destination paths, schedule, options) |
| `devices.json` | Saved devices including **SMB username and password** |
| `hub.log` | Application log (transfer start/end, errors) |

No other persistent user data is collected by Transfer Hub.

## Network behavior

- Connections are **local/LAN only**: SMB to PCs or other NAS devices, local filesystem paths (Volume 1/2, UGOS folder, USB under `/mnt/@usb`).
- Transfer Hub does **not** send data to external servers, analytics, or cloud services operated by Runlevel.
- Optional link in the UI points to **Ugreen NAS Admin** on GitHub (Windows companion tool); opening that link is user-initiated in the browser.

## Access control

- App is **admin-only** (`only_admin: true` in `project.yaml`).
- SMB credentials are stored in plain JSON on the NAS data path — users should use a dedicated data folder with restricted permissions and strong SMB passwords.

## Recommendations for users

- Choose a dedicated `DATA_PATH` (e.g. `/volume1/docker/transfer-hub/data`), not a public share.
- Do not expose port 29100 to the internet without additional protection.
- Use separate SMB accounts with minimal required permissions where possible.

## Data retention

- Data remains until the user deletes profiles/devices or removes the app data folder.
- Uninstalling the Docker app typically leaves `DATA_PATH` intact on the NAS (user data preserved).

## Contact

Developer contact for privacy inquiries: runlevel1977@posteo.de (Ivica Kampic, Runlevel)
