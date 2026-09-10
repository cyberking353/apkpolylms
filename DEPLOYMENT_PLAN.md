# Al-Hikma LMS — Deployment Guide (Dokploy / Traefik)

**What:** A Django web app (Al-Hikma LMS) that exposes sync + SSO endpoints used by an external Portal/SMS system.

**How it's shipped:** As a Docker Compose stack deployed on **Dokploy** (a Docker PaaS). Dokploy runs **Traefik** as the reverse proxy/load balancer, and provides PostgreSQL as an external managed database.

**You (the deploying programmer) need:** a Dokploy project, a managed PostgreSQL database, and the secrets below. No VPS sysadmin work required — no nginx, no local Postgres, no firewall setup.

---

## 1. Tech stack at a glance

| Service | What it does | Image |
|---|---|---|
| `backend` | The Django app (Gunicorn). Runs `migrate` + `collectstatic` on startup, then boots. Serves static files itself (WhiteNoise — no nginx). | built from this repo |
| `redis` | Cache + user sessions. | redis:7-alpine |

**Database:** PostgreSQL, provisioned externally by the PaaS, connected via one `DATABASE_URL`.
**Proxy/TLS:** Traefik (managed by Dokploy) routes traffic to the `backend` service and terminates TLS.

**Key versions:** Django 4.2 · Python 3.11 (in the image) · Django serves static via WhiteNoise.

There is **no** Celery, no nginx, no postgres container — just the two services above.

---

## 2. What the code already handles (you won't need to touch it)

All production hardening is implemented in `alhikma_lms/settings.py`:

- **`DEBUG`** comes from env (`DJANGO_DEBUG`). With `false`, the app **refuses to boot** unless `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` are set.
- **Database** is read from a single `DATABASE_URL` connection string (no `DB_*` vars needed).
- **Redis** is used automatically for cache + sessions (`REDIS_URL`).
- `/healthz` endpoint for uptime checks (200 only if connected to DB).
- Sync/SSO endpoints use constant-time token verification and reject oversized bodies (413).
- Uploads are validated (size + type) in the app; request bodies (tokens/JWTs) never logged.
- Static files served by Django directly via Whitenoise; media served via Django.

So deploying is **configuration, not code changes**.

---

## 3. Deploy on Dokploy

### 3.1 Project + network
1. In Dokploy, create a project for this app (e.g. `alhikma-lms`).
2. Dokploy attaches each project's services to the external `dokploy-network` automatically — the compose file already declares it (`external: true`), so no extra setup.
3. Traefik (managed by Dokploy) discovers the `backend` service and routes to it on port `8000`.

### 3.2 Database
Provision PostgreSQL in Dokploy / your DB provider and copy the connection string. It looks like:
```
postgres://user:password@host:5432/dbname?sslmode=require
```

### 3.3 Environment variables (set in the Dokploy UI)
From repo → `.env.example` (committed). Values to set:

```bash
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<your-domain-or-ip>
DJANGO_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(64))">
DATABASE_URL=postgres://...          # your managed Postgres connection string
PORTAL_BACKEND_URL=https://api-demo.auxilax.com
LMS_API_TOKEN=<token-the-portal-sends>
PORTAL_SSO_SECRET=<same-secret-as-the-portal>
```

Optional: `GUNICORN_WORKERS` (default 3), `PORT` (default 8000).

### About TLS / HTTPS
Traefik + Dokploy handle HTTPS certificates for you. After the domain routes over HTTPS, set:

```bash
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_COOKIES=true
```

(Leave them `false` while still serving plain HTTP so login doesn't silently break.)

---

## 4. Deploy — first time

In Dokploy, point the project at this repo and deploy (or deploy the compose file). Equivalently, from a machine with Docker + access to the network:

```bash
git clone https://github.com/saaleem353/apkpolylms.git
cd apkpolylms
cp .env.example .env        # fill in values, or rely on the PaaS env vars
docker compose up -d --build
```

On startup the `backend` container:
1. **Waits for the database** to be reachable (retry loop in `docker/entrypoint.sh`).
2. Runs `python manage.py migrate --noinput`.
3. Runs `python manage.py collectstatic --noinput` (served by Whitenoise).
4. Boots Gunicorn on `0.0.0.0:8000` (workers from `GUNICORN_WORKERS`).

## 5. Verify it works

```bash
docker compose ps
#  alhikma_lms_backend  Up (healthy)
#  alhikma_lms_redis    Up (health: starting → healthy)

curl https://YOUR_DOMAIN/healthz       -> {"status": "ok", "db": "ok"}
curl -I https://YOUR_DOMAIN/           -> HTTP/1.1 200
curl -I https://YOUR_DOMAIN/static/css/main.css   -> HTTP/1.1 200
```

Create an admin account and log in:
```bash
docker compose exec backend python manage.py createsuperuser
# open https://YOUR_DOMAIN/portal-admin/ in a browser
```

**Import existing course data?** The repo ships management commands:
```bash
docker compose exec backend python manage.py create_crypto_course   # demo course
docker compose exec backend python manage.py sync_portal            # pull data from the Portal
```

---

## 6. Day-to-day operations

| Task | Command |
|---|---|
| Deploy new code (via Dokploy) | re-deploy from the repo / `docker compose up -d --build` |
| See logs | `docker compose logs -f backend` |
| Restart | `docker compose restart` |
| Stop (data kept) | `docker compose down` |
| Open a shell | `docker compose exec backend bash` |
| Backup the database | use your managed DB provider's backup; or `pg_dump` against `DATABASE_URL` |

**Automatic restarts:** `restart: always` — the stack comes back on crashes/reboots.

**Persistent data:** only `redis_data` (Redis cache) lives in a Docker volume. The **database is external** and managed by the PaaS, so app data survives any container/lifecycle changes.

---

## 7. Backups & monitoring (do these early)

- **DB backups** — use your managed PostgreSQL provider's automated backups (nightly, tested restores). For extra safety, an offsite `pg_dump` via cron.
- **Uptime check** on `https://YOUR_DOMAIN/healthz` with UptimeRobot (free).
- **Error tracking:** add Sentry (free tier) when you want Python exceptions surfaced automatically.

---

## 8. Scaling later (when it matters, not now)

1. **Vertical first** — a bigger PaaS plan is the cheapest fix for a long time.
2. Redis is already used for cache/sessions; enable caching for expensive dashboard/progress queries when needed.
3. If uploads grow huge, move `media` storage to object storage (S3-compatible). Not a launch concern.

---

## 9. Integrating with the Portal (SSO / sync)

- **SSO:** lecturer accounts are created by the Portal's staff-sync, **not** auto-provisioned at SSO. Confirm the Portal points its SSO callback at this app's `/sso/callback`.
- **Sync:** the Portal sends webhooks to `/api/v1/sync/*` using `LMS_API_TOKEN`; `sync_portal` pulls data using `PORTAL_BACKEND_URL`. Keep `LMS_API_TOKEN` and `PORTAL_SSO_SECRET` identical to the Portal's config.