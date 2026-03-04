#!/bin/sh
set -e

CERT=/etc/nginx/certs/cert.pem
KEY=/etc/nginx/certs/key.pem

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "[nginx-entrypoint] No certificate found — generating self-signed certificate..."
    apk add --no-cache openssl >/dev/null 2>&1
    mkdir -p /etc/nginx/certs
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "$KEY" \
        -out  "$CERT" \
        -subj "/CN=localhost/O=ForensicArtifacts" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
    echo "[nginx-entrypoint] Self-signed certificate generated (valid 10 years)."
else
    echo "[nginx-entrypoint] Certificate found — skipping generation."
fi

exec nginx -g 'daemon off;'
