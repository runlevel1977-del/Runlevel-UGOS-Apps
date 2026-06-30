# Security Hub

**App ID:** `com.runlevel.securityhub`  
**Publisher:** Runlevel

## Overview

Source code for the **Security Hub** UGOS Docker application. Install via UGREEN App
Center after official listing, or build the Docker image from this directory.

## Build

```bash
docker build -t runlevel/security-hub:local .
```

## Configuration

Installation parameters are defined in the UGOS app package (`project.yaml` in the
private developer tree). Runtime data is stored under the user-chosen `DATA_PATH`
on the NAS.

## Documentation

- [Help index](../../docs/help/README.md)
- [Privacy policy](../../docs/privacy/securityhub.md)
- [Third-party licenses](../../THIRD_PARTY_LICENSES.md)

## Support

- Email: runlevel1977@posteo.de
- Issues: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues
