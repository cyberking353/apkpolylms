FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime dependency for Pillow image handling (keep image slim, no build tools).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps FIRST so Docker layer caching survives code edits.
# Some networks cannot reach pypi.org directly (pip fails with "Connection
# reset by peer"); pass a mirror at build time via:
#   docker compose build --build-arg PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple/
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -i "${PIP_INDEX_URL}"

COPY . /app

RUN mkdir -p /app/logs /app/staticfiles /app/media

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "alhikma_lms.wsgi:application", "-c", "gunicorn.conf.py"]