# Al-Hikma LMS — VPS Deployment Plan
**Dev:** Salim  ·  **Stack:** Django 5.2 / Python 3.11 / PostgreSQL 16 / Gunicorn / Nginx / Redis / Let's Encrypt / Docker Compose
**Hosting:** OVHcloud  ·  **Runtime:** Docker Compose  ·  **Domain:** TBD (decides ALLOWED_HOSTS / TLS / cookie flags later)

---

## 1. Current reality & gaps (audit)

The app today runs on PythonAnywhere free tier (SQLite, DEBUG=True, `ALLOWED_HOSTS=['*']`). Before any VPS move, these are the things that must change regardless of infra:

| Gap | Current | Required for VPS |
|---|---|---|
| Database | SQLite (roundabout, single-writer) | PostgreSQL 16 (concurrency) |
| `DEBUG` | hardcoded `True` (settings.py:52) | `False`, from `.env` |
| `ALLOWED_HOSTS` | `['*']` (settings.py:54) | explicit real domain(s) from `.env` |
| `SECRET_KEY` | weak fallback string | strong 50+ char, env-only |
| Sessions | DB-backed (settings.py:143) | Redis-backed (fast, scales) |
| Cache | `LocMemCache` (per-process, useless across workers) | Redis |
| Static | local `staticfiles/` | served by Nginx |
| Media (course content) | local `media/` | Nginx + planned S3/object-storage |
| Migrations | applied manually | automated deploy step |
| Sync/cron | none in prod (run locally) | systemd timer / Celery beat |
| Background jobs | none | Celery + Redis (nudges, sync, exports, media processing) |
| Reverse proxy / TLS | PythonAnywhere | Nginx + Let's Encrypt |
| Watchdog | none | systemd restart-on-fail + monitoring |

---

## 2. Recommended architecture

```
                        Internet
                           │  :443 (HTTPS)
                     ┌─────▼─────┐
                     │  Nginx    │  TLS terminate, serve /static & /media,
                     │  (Caddy   │  reverse-proxy gunicorn, rate-limit,
                     │   alt)    │  gzip, security headers, cache static
                     └─────┬─────┘
                           │  :8000 (unix socket)
                  ┌────────▼────────┐
                  │  Gunicorn       │  app workers (e.g. 3–6 workers,
                  │  (Django WSGI)  │  1 thread, worker_class=sync/gevent)
                  └───┬──────┬──────┘
               DB  ┌───▼──┐ ┌▼──────┐ ┌──────────────┐
                PG │Redis │ │ Celery│ │  Celery Beat │
              16   └──────┘ │worker │ │  (scheduler) │
                  (volume)  └───────┘ └──────────────┘
            Backups / Restic / pg_dump  ──  S3/MinIO (media, optional)
```

One VPS can host all of it initially. As traffic grows, split Celery/Redis/DB onto separate nodes.

---

## 3. Recommended server sizing

### Rationale from code
- Sync/SSO webhooks are **bursty and blocking** — the sync webhook views do DB upserts inline, so the web worker is occupied during a pull/push burst.
- Progress monitor, dashboard KPIs, and portal lists do moderately heavy queries (aggregation over `Result`/`QuizAttempt`/`LectureProgress`).
- `nudge` sends Notification rows per flagged student; `activity feed` aggregates last 14 days.
- PWA is client-side only — no server cost.
- **Est. DB growth:** students ~1–5k, results ~10k×(attempts×students), quizzes ~dozens×MCQ. Total tiny (a few hundred MB for years).

### Phase 1 — launch (up to ~2k active users, ~5–10k students)
| Resource | Size |
|---|---|
| vCPU | 2 |
| RAM | 4 GB |
| Disk | 40 GB SSD |
| Bandwidth | 2–4 TB/mo |
| Node count | 1 |
| Gunicorn workers | `2*CPU+1 = 5` |
| Postgres | single instance, default tuning |
| Redis | single instance, 256 MB maxmemory |
| Cost class | ~$20–30/mo (Hetzner/DO/Vultr) |

### Phase 2 — growth (5k–15k students, heavy exam season)
| Resource | Size |
|---|---|
| vCPU | 4 |
| RAM | 8 GB |
| Storage | 75 GB (more media) |
| Workers | 9 |
| Split out | Redis → separate node (or add Celery on same) |
| DB | keep single PG, add index review |
| Cost | ~$50/mo |

### Scale triggers (monitor)
- Gunicorn queue time > 500 ms, or 429s / 5xx rising
- Postgres CPU sustained > 60%
- Concurrency > ~500 open connections
- Token auth endpoint latency rising

---

## 4. Loop-holes / security hardening (implementation checklist)

1. **`DEBUG=False` + `ALLOWED_HOSTS` from env** — set `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=alhikma.work,www.alhikma.work,api.alhikma.work`. Never `*` in prod.
2. **Secret management** — move all secrets (DB password, `DJANGO_SECRET_KEY`, `LMS_API_TOKEN`, `PORTAL_SSO_SECRET`, Redis password) into `.env` (already gitignored) + a secrets manager later. **Never commit .env.** Add `.env` to `.gitignore` if not already (verify).
3. **TLS everywhere** — Let's Encrypt via certbot (Nginx) or automatic with Caddy; force HTTPS, HSTS, secure+HttpOnly cookies.
4. **Cookie flags** — `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `CSRF_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_HTTPONLY=True` (default).
5. **Rate limiting** — the **SSO callback and sync webhook endpoints are the biggest risk** (public, token-gated only). Add Nginx `limit_req` on `/api/v1/` and `/sso/`, plus brute-force protection on login. Verify the token is compared with `secrets.compare_digest` (constant-time) — check api/views.py.
6. **DB hardening** — dedicated non-root PG user, role-scoped, strong password, `listen_addresses` bound to localhost (not `0.0.0.0`), no TCP exposure to internet.
7. **Firewall** — `ufw`/`nftables`: allow 22 (SSH), 80, 443 only. Disable password auth, SSH keys only, non-root deploy user.
8. **No sensitive data in logs** — ensure sync/SSO request bodies (tokens, JWTs) are never logged.
9. **Dependency pinning** — `requirements.txt` today is unbounded (`Django`, `Pillow>=10`, `openpyxl`). Pin exact versions for reproducible deploy.
10. **Health endpoint** — add `/healthz` (DB + Redis check) for the load balancer / uptime monitor.
11. **Backups** — `pg_dump` nightly + Restic/S3 offsite; test restore. Also dump `.env` and media.
12. **Update strategy** — `pip install --upgrade` on a schedule + `pip-audit`/`safety` for known CVEs.
13. **Log rotation** — `logrotate` for gunicorn/nginx/systemd; ship to a central log (optional).
14. **Media content sanitization** — if lecturers upload course media/files, validate file type + size, serve with restrictive headers, anti-virus scan (ClamAV) on a timer.
15. **Admin panel exposure** — Django admin at `/admin/` should be on a restricted path or only via allow-listed IP.
16. **CSRF/SSO integrity** — re-verify JWT/HMAC signature + `exp` on every SSO callback; ensure clock sync via NTP.
17. **Dependency of NoCache HTML middleware** — keep it (helps fresh deploys) but ensure static media still cache-bust via `?v=` and Nginx caching.

---

## 5. Recommended production settings changes (to implement)

```python
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']   # fail hard if missing in prod

# Postgres always in prod (drop the PYTHONANYWHERE exception or gate on DEBUG)
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.environ.get('DB_NAME', 'alhikma_lms'),
    'USER': os.environ.get('DB_USER', 'alhikma'),
    'PASSWORD': os.environ.get('DB_PASSWORD', ''),
    'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
    'PORT': os.environ.get('DB_PORT', '5432'),
    'CONN_MAX_AGE': 60,           # connection reuse
    'OPTIONS': {'connect_timeout': 5},
}

CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
}}
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'  # Redis + DB fallback

# Celery
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

# Cookies
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Static/Media from env
STATIC_ROOT = os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles')
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', BASE_DIR / 'media')
```

---

## 6. Infrastructure-as-code / deployment automation

### Chosen approach: **Docker Compose** (single VPS on OVHcloud)
`docker-compose.yml` with services:
- `web` — Gunicorn serving the Django WSGI app
- `worker` — Celery worker (async jobs: sync bursts, exports, nudges, media)
- `beat` — Celery Beat scheduler (timed sync, backups triggers)
- `db` — postgres:16 with a named volume
- `redis` — cache + session + Celery broker (with password)
- `nginx` — reverse proxy, TLS terminate, serve `/static` & `/media`, `limit_req` on `/api/` and `/sso/`

Deploy = `docker compose up -d --build`; migrations via `docker compose run --rm web python manage.py migrate`.

**Pros:** one-command atomic deploy, isolated and reproducible across OVH resizes, easy rollback via image tags.
**Cons:** small memory overhead (fine on 4 GB); must manage images/volumes — use named volumes + a backup job for them.

### Deploy steps (atomic & zero-downtime), same for Compose:
```bash
# on server (deploy user, ~/app/apkpolylms)
git pull origin main
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)          # or have Django load .env (already does)
python manage.py migrate --noinput
python manage.py collectstatic --noinput
systemctl restart gunicorn celery celery-beat   # (or: docker compose up -d --build)
systemctl reload nginx
```

---

## 7. Scaling strategy (as user base grows)

1. **Vertical first** — one beefier VPS is simplest and cheap for this app's size.
2. **Add Celery workers** for anything slow: webhook sync bursts, CSV exports, bulk nudges, media processing — move these off the request path.
3. **Add connection pooling** — PgBouncer if Postgres connection count becomes a bottleneck.
4. **Horizontal web** — 2+ Gunicorn nodes behind Nginx (round-robin), shared Redis + Postgres.
5. **CDN** for the static assets + Lucide icons (cloudflare — free) to cut origin load.
6. **Object storage** for media (S3/MinIO) so multiple web nodes share uploads — the **#1 reason single local `media/` breaks multi-node**.
7. **Database read-replica** for the heavy read paths (results gradebook, progress monitor) once writes are fine but reads strain primary.
8. **Query tuning** — add indexes on the hot columns: `Enrollment(student, course)`, `LectureProgress(student, lecture, completed_at)`, `QuizAttempt`, `Result(student, course)`, `Notification` reads. Use `EXPLAIN ANALYZE` on the progress/dashboard queries.
9. **Cache expensive dashboard KPI + progress aggregates** in Redis with short TTL (e.g. 60s) so repeated refreshes don't hammer PG.

---

## 8. Monitoring & alerting
- **Uptime:** UptimeRobot / OVH monitoring on `/healthz`.
- **Metrics:** `prometheus` + `django-prometheus` (Django, Gunicorn, PG, Redis, Nginx exporters) → Grafana dashboards.
- **Errors:** Sentry (free tier) for Python exceptions — invaluable for catching prod-only bugs.
- **Logs:** `logrotate` + optional Loki.
- **Alert thresholds:** 5xx rate, Gunicorn queue, disk > 80%, PG connections > 70%.

---

## 9. Suggested VPS — OVHcloud (start small, launch now)
- **OVHcloud VPS-2 / "Value"** (2 vCPU / 4 GB / ~40 GB NVMe) ≈ €5–7/mo — strong value; OVH has EU/CA/IN regions.
- Or the 3 vCPU / 8 GB tier if you expect heavy exam-season load (~€9–12/mo).
- Use OVH **snapshot backups** (per-VPS) + offsite `pg_dump` via Restic to OVH **Object Storage** (S3-compatible).
- Pick a region close to your users (typically an EU region; choose what gives the best latency for Al-Hikma).

---

## 10. Recommended implementation order (when you say go)
1. Hardening settings changes (section 5) + pin requirements + `/healthz` + `.gitignore` check. *(Domain-agnostic — can start before DNS.)*
2. Provision OVH VPS — region + tier; firewall, non-root deploy user, SSH keys, swap.
3. Install Docker + Docker Compose plugin; set up git clone, `.env`, named volumes.
4. Write `docker-compose.yml`, `Dockerfile`, Nginx conf (TLS once domain known), healthchecks.
5. `migrate` + `collectstatic` + seed `create_crypto_course`; point SSO token/`PORTAL_BACKEND_URL` at new host.
6. Once DNS is set: Let's Encrypt + `ALLOWED_HOSTS` + secure cookie flags; switch DNS.
7. Verify sync webhooks + SSO end-to-end against the VPS.
8. Celery/beat, backups (pg_dump + Restic/OVH object storage), monitoring, Sentry.
9. Phone PWA test against new host, then cut over from PythonAnywhere.

---

## 11. Open questions before implementation
1. **Database choice** — settled: Docker Compose. ✅
2. **Hosting** — settled: OVHcloud (need the concrete VPS tier + region when you order).
3. **Domain(s) — still TBD.** Affects `ALLOWED_HOSTS`, Let's Encrypt TLS, `SESSION_COOKIE_SECURE`, and the SSO callback URL. Need this before switchover.
4. **Media scale** — is object storage (OVH S3) needed now, or is Nginx-served local media (in a named volume) fine for phase 1?
5. **Who runs `sync_portal`** — the VPS has real outbound internet (unlike PA), so a Celery beat job can run it there on a timer. Confirm this is desired.
6. **Budget** — confirm monthly cap for the OVH VPS + any monitoring/Sentry spend.
