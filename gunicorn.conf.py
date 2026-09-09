"""Gunicorn configuration for the Dockerized web service."""
import multiprocessing
import os

bind = "0.0.0.0:8000"

# Tunable so small dev machines / low-RAM containers can cap worker count:
#   GUNICORN_WORKERS=3
# Defaults to `2*CPU+1` (5 workers on a 2-CPU box).
_default_workers = max(3, multiprocessing.cpu_count() * 2 + 1)
workers = int(os.environ.get('GUNICORN_WORKERS', _default_workers))
threads = 2

# Generous timeouts: sync webhooks and report exports can be slow.
timeout = 120
graceful_timeout = 30

# Log to stdout/stderr so Docker captures logs via `docker logs`.
accesslog = "-"
errorlog = "-"

# Let Nginx handle client body limits — keep gunicorn permissive.
limit_request_field_size = 16384