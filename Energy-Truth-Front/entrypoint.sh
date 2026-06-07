#!/bin/sh

echo "{\"ApiBaseUrl\":\"$BACKEND_URL\"}" > /usr/share/nginx/html/appsettings.json

exec nginx -g 'daemon off;'