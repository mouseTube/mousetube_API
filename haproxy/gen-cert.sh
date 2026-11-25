#!/bin/sh
# Makes the self-signed certificate of the local HAProxy: haproxy/certs/mousetube.pem (key + certificate).
# Usage: haproxy/gen-cert.sh [domain]   (default: mousetube.ifb.local)
# The certificate is not in git. Browsers warn about it until it is accepted once.
set -e
DOMAIN="${1:-mousetube.ifb.local}"
DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$DIR"
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -subj "/CN=$DOMAIN" -addext "subjectAltName=DNS:$DOMAIN" \
    -keyout "$DIR/key.pem" -out "$DIR/cert.pem"
cat "$DIR/cert.pem" "$DIR/key.pem" > "$DIR/mousetube.pem"
rm "$DIR/key.pem" "$DIR/cert.pem"
chmod 644 "$DIR/mousetube.pem"
echo "Certificate for $DOMAIN written to $DIR/mousetube.pem"
