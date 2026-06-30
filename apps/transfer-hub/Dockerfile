# Transfer Hub — Web-UI + rsync
FROM alpine:3.20
RUN apk add --no-cache rsync bash tzdata python3 py3-flask py3-cryptography samba-client rclone cifs-utils util-linux \
    && mkdir -p /data /app /mnt/nas /mnt/work
WORKDIR /app
COPY app/ /app/
RUN python3 -m compileall -q /app
ENV RUNLEVEL_APPS_REPO=https://github.com/runlevel1977-del/Runlevel-UGOS-Apps \
    RUNLEVEL_PRIVACY_SLUG=transferhub \
    RUNLEVEL_CREDENTIAL_CONSENT=1
ENV TRANSFER_HUB_DATA=/data \
    NAS_MOUNT=/mnt/nas \
    TRANSFER_HUB_VERSION=0.6.21 \
    TZ=Europe/Berlin
EXPOSE 8080
VOLUME ["/data"]
CMD ["python3", "main.py"]
