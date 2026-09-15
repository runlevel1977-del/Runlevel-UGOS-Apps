# Moving Files

**App ID:** `com.runlevel.movingfiles`  
**Publisher:** Runlevel  
**Type:** native UGOS app (Go), not Docker

## Overview

Source for the **Moving Files** UGOS application: copy/move jobs, Wake-on-LAN, and password-optional backup archives.

Install via UGREEN App Center after listing, or pack a `.upk` with `ugcli` from the developer tree.

## Layout

- `backend/` — Go service (`movingfiles_serv`)
- `rootfs_common/www/` — HTML/CSS/JS UI
- `rootfs_common/icon.png` — App Center icon
- `project.yaml` — UGOS package metadata

The packaged Linux binary and the bundled `rclone` executable are **not** stored in this folder. `rclone` is fetched at pack time (MIT). SMB fallback is [go-smb2](https://github.com/hirochachacha/go-smb2).

## Documentation

- [User guide](../../docs/help/movingfiles.md)
- [Help index](../../docs/help/README.md)
- [Privacy policy](../../docs/privacy/movingfiles.md)
- [Third-party licenses](../../THIRD_PARTY_LICENSES.md)
- [EULA](../../docs/EULA.md)

## Support

- Email: runlevel1977@posteo.de
- Issues: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues
