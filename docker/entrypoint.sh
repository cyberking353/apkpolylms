#!/usr/bin/env sh
set -e

# Runs as the web container entrypoint. Ensures the DB schema and static files
# are ready, then hands off to the CMD (gunicorn).

echo "==> Applying database migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Starting: $@"
exec "$@"