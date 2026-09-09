#!/usr/bin/env sh
set -e

# Runs as the web container entrypoint. Waits for Postgres to accept
# connections, ensures the schema + static files are ready, then hands off
# to the CMD (gunicorn).

echo "==> Waiting for database..."
python - <<'PY'
import os
import time
import psycopg2

for attempt in range(30):
    try:
        psycopg2.connect(
            dbname=os.environ.get('DB_NAME', 'alhikma_lms'),
            user=os.environ.get('DB_USER', 'alhikma'),
            password=os.environ.get('DB_PASSWORD', ''),
            host=os.environ.get('DB_HOST', 'db'),
            port=int(os.environ.get('DB_PORT', '5432') or 5432),
            connect_timeout=3,
        ).close()
        print('database reachable')
        break
    except Exception as exc:
        time.sleep(2)
else:
    print('WARNING: database not reachable after 60s; trying anyway')
PY

echo "==> Applying database migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Starting: $@"
exec "$@"