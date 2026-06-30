# Security Hub — NAS access history + live monitoring (host logs)
FROM alpine:3.20
RUN apk add --no-cache bash coreutils tzdata python3 py3-flask py3-cryptography util-linux \
    && mkdir -p /data /app
WORKDIR /app
COPY app/ /app/
RUN python3 -m compileall -q /app
ENV RUNLEVEL_APPS_REPO=https://github.com/runlevel1977-del/Runlevel-UGOS-Apps \
    RUNLEVEL_PRIVACY_SLUG=securityhub \
    RUNLEVEL_CREDENTIAL_CONSENT=0
ENV SECURITY_HUB_DATA=/data \
    SECURITY_HUB_VERSION=0.1.11 \
    HOST_VAR_LOG=/host/var/log \
    HOST_UGREEN_LOG=/host/ugreen/log \
    TZ=Europe/Berlin
EXPOSE 8080
VOLUME ["/data"]
CMD ["python3", "main.py"]
