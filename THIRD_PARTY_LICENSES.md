# Third-Party Open-Source Licenses

Runlevel UGOS Docker applications are built on Alpine Linux and include
the components below. This list is not exhaustive for every Alpine package;
see each application's `Dockerfile` for the full `apk` dependency set.

| Component | License | Project |
| --- | --- | --- |
| Alpine Linux | Various (mostly MIT/BSD/GPL) | https://alpinelinux.org/ |
| Python 3 | PSF License | https://www.python.org/ |
| Flask (py3-flask) | BSD-3-Clause | https://flask.palletsprojects.com/ |
| cryptography | Apache-2.0 / BSD | https://cryptography.io/ |
| rclone | MIT | https://rclone.org/ |
| rsync | GPL-3.0 | https://rsync.samba.org/ |
| Samba client tools | GPL-3.0 | https://www.samba.org/ |
| Docker CLI | Apache-2.0 | https://www.docker.com/ |
| smartmontools | GPL-2.0 | https://www.smartmontools.org/ |
| util-linux | GPL-2.0+ | https://github.com/util-linux/util-linux |
| eudev | GPL-2.0 | https://github.com/eudev-project/eudev |
| dosfstools | GPL-3.0 | https://github.com/dosfstools/dosfstools |

## Moving Files (native Go app)

Moving Files (`com.runlevel.movingfiles`) is a native UGOS service. It does not
use Alpine/Python. Packaged builds may bundle **rclone** (MIT).
Source: [apps/moving-files](apps/moving-files/).

| Component | License | Project |
| --- | --- | --- |
| Go | BSD-3-Clause | https://go.dev |
| github.com/hirochachacha/go-smb2 | BSD-2-Clause | https://github.com/hirochachacha/go-smb2 |
| github.com/geoffgarside/ber | MIT | https://github.com/geoffgarside/ber |
| golang.org/x/crypto | BSD-3-Clause | https://pkg.go.dev/golang.org/x/crypto |
| rclone (bundled at pack time) | MIT | https://rclone.org/ |

## Application source code

Runlevel application source (Docker Python apps and native Moving Files): https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

Windows companion tool **Ugreen NAS Admin**: https://github.com/runlevel1977-del/UgreenNASAdmin
