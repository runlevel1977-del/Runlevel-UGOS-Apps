# Security Hub — User Guide

**App ID:** `com.runlevel.securityhub`  
**Port:** 29130  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Read-only security overview for administrators: login/auth activity from system and UGOS logs (SSH, web/app logins, SMB audit where available). Does not change firewall or block lists.

## Install / configure

1. Install **Docker** suite.
2. Install **Security Hub**.
3. Set **Data directory** (empty folder after a reinstall if you want the first-launch privacy dialog again).
4. Open the app. First screen: **privacy consent** (Agree and Decline). Then set an app password.
5. The app password is not sent as HTTP plaintext (`password_enc`).

## Core usage

1. Open Security Hub, confirm privacy, sign in.
2. Review recent login / auth events.
3. Filter or refresh as needed.
4. Footer: Help, Privacy, Support.

## Tips

- Display may include client IPs and usernames — admin eyes only.
- Read-only: no modifications to logs or firewall.
- Do not expose port 29130 to the internet.
