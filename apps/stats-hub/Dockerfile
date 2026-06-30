# Stats Hub — live NAS metrics (NAS Admin dashboard sources)
FROM alpine:3.20
RUN apk add --no-cache bash coreutils tzdata python3 py3-flask py3-cryptography iproute2 util-linux docker-cli smartmontools procps \
    && mkdir -p /data /app
WORKDIR /app
COPY app/ /app/
RUN python3 -m compileall -q /app
ENV RUNLEVEL_APPS_REPO=https://github.com/runlevel1977-del/Runlevel-UGOS-Apps \
    RUNLEVEL_PRIVACY_SLUG=statshub \
    RUNLEVEL_CREDENTIAL_CONSENT=0
ENV STATS_HUB_DATA=/data \
    STATS_HUB_VERSION=0.2.22 \
    STATS_HUB_PORT=29125 \
    TZ=Europe/Berlin
EXPOSE 8080
VOLUME ["/data"]
CMD ["python3", "main.py"]
