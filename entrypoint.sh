#!/bin/sh
set -e

# --- PostgreSQL бэлэн болтол хүлээх ---
if [ -n "$POSTGRES_HOST" ]; then
  echo "PostgreSQL хүлээж байна ($POSTGRES_HOST:${POSTGRES_PORT:-5432})..."
  while ! nc -z "$POSTGRES_HOST" "${POSTGRES_PORT:-5432}"; do
    sleep 1
  done
  echo "PostgreSQL бэлэн."
fi

# --- Миграци (эх өгөгдөл: 0006_load_full_data 200 хүнийг ачаална) ---
python manage.py migrate --noinput

# --- Static файлууд (nginx үзүүлнэ) ---
python manage.py collectstatic --noinput

# --- Админ superuser (DJANGO_SUPERUSER_* env байвал, байхгүй бол алгасна) ---
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput 2>/dev/null || true
fi

# --- Gunicorn ---
exec gunicorn familytree.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 120
