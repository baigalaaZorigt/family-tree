#!/bin/sh
# app.conf.template-г envsubst-оор бодит DOMAIN-той болгож бичээд nginx-г эхлүүлнэ.
# Тусдаа файл ашигласны шалтгаан: docker-compose.yml дахь command: мөрөнд шууд бичвэл
# $DOMAIN нь compose болон sh хоёулаа өөр өөрөөр escape хийж мөргөлддөг.
set -e

envsubst '$DOMAIN' < /etc/nginx/templates/app.conf.template > /etc/nginx/conf.d/app.conf
rm -f /etc/nginx/conf.d/default.conf

# 6 цаг тутам reload (шинэчилсэн SSL сертификатыг арын дэвсгэрт ачаалахаар)
( while :; do sleep 6h; nginx -s reload; done ) &

exec nginx -g 'daemon off;'
