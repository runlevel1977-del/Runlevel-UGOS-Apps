# Lock & Key — folder encryption with USB key file (NAS USB)
FROM alpine:3.20
RUN apk add --no-cache python3 py3-pip py3-flask bash tzdata util-linux eudev dosfstools \
    && pip3 install --no-cache-dir --break-system-packages cryptography \
    && mkdir -p /data /app
WORKDIR /app
COPY app/ /app/
RUN python3 -m compileall -q /app
ENV RUNLEVEL_APPS_REPO=https://github.com/runlevel1977-del/Runlevel-UGOS-Apps \
    RUNLEVEL_PRIVACY_SLUG=lockandkey \
    RUNLEVEL_CREDENTIAL_CONSENT=0
ENV LOCK_KEY_DATA=/data \
    LOCK_KEY_VERSION=0.1.25 \
    TZ=Europe/Berlin
EXPOSE 8080
VOLUME ["/data"]
CMD ["python3", "main.py"]
