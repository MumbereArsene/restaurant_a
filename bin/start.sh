#!/usr/bin/env bash
set -euo pipefail

echo "==> Running migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Ensuring restaurant profile"
python manage.py bootstrap_prod

echo "==> Starting Gunicorn"
# Northflank (and most PaaS) provide $PORT
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
