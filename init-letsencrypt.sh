#!/bin/sh
# Let's Encrypt SSL сертификатыг АНХ УДАА автоматаар авах скрипт.
# Ашиглах: .env дотор DOMAIN, EMAIL-ээ бөглөөд:  ./init-letsencrypt.sh
set -e

if [ -f .env ]; then
  # .env-ээс DOMAIN, EMAIL уншина
  export $(grep -E '^(DOMAIN|EMAIL|STAGING)=' .env | xargs)
fi

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "❌ .env дотор DOMAIN болон EMAIL-ээ бөглөнө үү."
  exit 1
fi

DC="docker compose"
DATA_PATH="./certbot"
RSA_KEY_SIZE=4096
STAGING=${STAGING:-0}   # 1 бол туршилтын (staging) сертификат

domains="$DOMAIN www.$DOMAIN"
echo "### Домэйн: $domains"

# 1) Түр (dummy) сертификат үүсгэх — nginx эхлэхийн тулд
echo "### Түр сертификат үүсгэж байна ..."
CERT_PATH="/etc/letsencrypt/live/$DOMAIN"
$DC run --rm --entrypoint "\
  sh -c 'mkdir -p $CERT_PATH \
    && openssl req -x509 -nodes -newkey rsa:1024 -days 1 \
       -keyout $CERT_PATH/privkey.pem -out $CERT_PATH/fullchain.pem -subj /CN=localhost'" certbot

# 2) nginx-г асаах
echo "### nginx асааж байна ..."
$DC up --force-recreate -d nginx web db

# 3) Түр сертификатыг устгах
echo "### Түр сертификатыг устгаж байна ..."
$DC run --rm --entrypoint "\
  sh -c 'rm -Rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf'" certbot

# 4) Жинхэнэ Let's Encrypt сертификат авах
echo "### Let's Encrypt сертификат хүсэж байна ..."
domain_args=""
for d in $domains; do domain_args="$domain_args -d $d"; done

staging_arg=""
if [ "$STAGING" != "0" ]; then staging_arg="--staging"; fi

$DC run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg $domain_args \
    --email $EMAIL --rsa-key-size $RSA_KEY_SIZE \
    --agree-tos --no-eff-email --force-renewal" certbot

# 5) nginx-г reload хийх
echo "### nginx reload ..."
$DC exec nginx nginx -s reload

echo "✅ Дууслаа! https://$DOMAIN нээгдэх ёстой."
