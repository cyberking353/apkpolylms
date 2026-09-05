"""Gunicorn configuration for the Dockerized web service."""
import multiprocessing

bind = "0.0.0.0:8000"

# Docker container CPUs, not host CPUs — an integer so it's well-defined.
# `max(2, cpu*2+1)` gives 5 workers on a 2-CPU box.
workers = max(3, multiprocessing.cpu_count() * 2 + 1)
threads = 2

# Generous timeouts: sync webhooks and report exports can be slow.
timeout = 120
graceful_timeout = 30

# Log to stdout/stderr so Docker captures logs via `docker logs`.
accesslog = "-"
errorlog = "-"

# Let Nginx handle client body limits — keep gunicorn permissive.
limit_request_field_size = 16384