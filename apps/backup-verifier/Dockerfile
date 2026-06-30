# Backup Verifier — read-only compare (rsync dry-run + checksum)
FROM alpine:3.20
RUN apk add --no-cache rsync bash tzdata python3 py3-flask py3-cryptography samba-client rclone cifs-utils util-linux \
    && mkdir -p /data /app
WORKDIR /app
COPY app/ /app/
RUN python3 -m compileall -q /app
ENV RUNLEVEL_APPS_REPO=https://github.com/runlevel1977-del/Runlevel-UGOS-Apps \
    RUNLEVEL_PRIVACY_SLUG=backupverifier \
    RUNLEVEL_CREDENTIAL_CONSENT=1
ENV BACKUP_VERIFIER_DATA=/data \
    BACKUP_VERIFIER_VERSION=0.3.14 \
    TZ=Europe/Berlin
EXPOSE 8080
VOLUME ["/data"]
CMD ["python3", "main.py"]
