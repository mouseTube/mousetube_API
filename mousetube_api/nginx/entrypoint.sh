#!/bin/sh

if [ -z "$DOMAIN" ]; then
    echo "❌ DOMAIN n'est pas défini."
    exit 1
fi

envsubst '$DOMAIN' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'