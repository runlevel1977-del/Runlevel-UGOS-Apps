> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Moving Files — Privacy & Security Summary

**App ID:** `com.runlevel.movingfiles`  
**Publisher:** Runlevel  
**Version:** 0.2.0  

Full policy: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/privacy/movingfiles.md

## Data stored locally (on the NAS)

In the app data directory (removed on uninstall):

| File | Content |
|------|---------|
| `state.json` | Devices, jobs, schedules, logs (SMB username/password, optional backup password) |
| `privacy_consent.json` | Agree / Decline for storing credentials |

GET `/api/state` does **not** return plaintext passwords (`hasPassword` only).

## Network behavior

- **SMB:** connections to hosts the administrator saved (LAN / chosen NAS).
- **Wake-on-LAN:** UDP magic packet to the stored MAC.
- **No** analytics or cloud backend operated by Runlevel.
- Help / privacy / GitHub links open only when the user clicks them.

## Access control

- App is **admin-only** (`only_admin: true`).
- Folder access is limited to paths granted at install / Settings (`allow_add_access_path`).
- Privacy dialog: Decline keeps local copies working but does not store SMB or archive passwords.
- Do not expose port 21010 to the public internet.

## Contact

runlevel1977@posteo.de (Ivica Kampic, Runlevel)
