> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Stats Hub — Privacy & Security Summary

**App ID:** `com.runlevel.statshub`  
**Publisher:** Runlevel  
**Version:** 0.2.54  

See the public policy: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/privacy/statshub.md

## Data stored locally (on the NAS)

Under the user-chosen **Data directory** (`DATA_PATH`, mounted as `/data`):

| File | Content |
|------|---------|
| `settings.json` | UI preferences; optional UGOS API password encrypted at rest |
| `app_auth.json` | Salted app-password hash + 32-character session id (no plaintext password) |
| `privacy_consent.json` | Agree/decline + policy version |
| `stats-hub.log` | Application log (no passwords) |

## Network behavior

- No outbound connections to Runlevel or third-party analytics.
- Web UI on port **29125**, `network_mode: bridge` (not host network).
- App password and optional UGOS passwords are sent as **RSA-OAEP** ciphertext, not HTTP plaintext.

## Host access

- Not privileged. No host network. **No docker.sock.**
- `/sys` and `/dev` read-only for metrics / smartctl temperatures.
- Docker table: read-only names/status from `/volume1/@docker/containers` (same `/volume1` mount). No Docker Engine control.

## Access control

- Admin-only (`only_admin: true`).
- Standalone app password. Unique 32-character session ID after login.
- Headers such as `user_id` / `Ugreen-User-ID` do **not** grant access.
- First launch: privacy consent (Agree and Decline) before login.

## Contact

Ivica Kampic / Runlevel  
Leipziger Str. 33, 89537 Giengen, Deutschland  
runlevel1977@posteo.de
