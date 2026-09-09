# Al-Hikma LMS — VPS Deployment Guide

**What:** A Django web app (Al-Hikma LMS) that also exposes sync + SSO endpoints used by an external Portal/SMS system.

**How it's shipped:** As a self-contained Docker Compose stack. Deploying = clone the repo, set a few environment variables, run one command.

**You (the deploying programmer) need:** a Linux VPS (this guide targets OVHcloud), SSH access to it, and nothing else — Docker is installed automatically by the script below.

---

## 1. Tech stack at a glance

Everything runs in containers. There are only four:

| Service | What it does | Image |
|---|---|---|
| `nginx` | Public entry point on port 80. Serves static/media, proxies everything else to the app. | nginx:1.27-alpine |
| `web` | The Django app itself, served by Gunicorn. Runs `migrate` + `collectstatic` on startup, then boots. | built from this repo |
| `db` | PostgreSQL 16 — the database. Data survives container restarts (named volume). | postgres:16-alpine |
| `redis` | Cache + user sessions. | redis:7-alpine |

**Key versions:** Django 4.2 · Python 3.11 (in the image) · PostgreSQL 16 · Debian/Docker host.

There is **no** Celery, no separate beat, no extra services — just these four. The app uses Redis only for cache and sessions.

---

## 2. What the code already handles (you won't need to touch it)

All production hardening is already implemented in `alhikma_lms/settings.py`:

- **`DEBUG`** comes from `.env` (`DJANGO_DEBUG`). With `false`, the app **refuses to boot** unless `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` are set — fail-fast so a misconfigured server can't run silently.
- **`ALLOWED_HOSTS`** and **`SECRET_KEY`** come from `.env` (see section 4).
- **Redis** is used automatically for cache + sessions when `REDIS_URL` is set (the stack sets it).
- **PostgreSQL** is the default database choice on a VPS (SQLite is only for local/PA dev).
- `/healthz` endpoint exists for uptime checks (returns 200 only if connected to DB).
- Sync/SSO endpoints verify tokens with constant-time comparison and reject oversized request bodies (HTTP 413).
- Uploads are validated (size + type) in the app.
- Request bodies (tokens/JWTs) are never written to logs.

So deploying is mostly **configuration, not code changes**.

---

## 3. One-time VPS setup (about 30 minutes)

### 3.1 Provision the VPS
- OVHcloud **VPS-2** (2 vCPU / 4 GB RAM / 40 GB NVMe) is enough to launch. ~€5–7/mo.
- Pick a region close to your users (e.g. EU).

### 3.2 First login + basic hardening
```bash
ssh root@YOUR_SERVER_IP

# update packages
apt update && apt upgrade -y

# create a non-root deploy user
adduser deploy
usermod -aG sudo deploy

# lock down SSH: keys only, no passwords, no root login
mkdir -p /home/deploy/.ssh
# ... copy your public key into /home/deploy/.ssh/authorized_keys ...
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

**Firewall** — allow only SSH, HTTP, HTTPS:
```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 3.3 Install Docker (as `deploy`)
```bash
apt install -y docker.io docker-compose-v2
# or the official one-liner:  curl -fsSL https://get.docker.com | sh
```
Verify:
```bash
docker --version && docker compose version
```

> **Note for this dev machine's flaky network:** if `apt`/`pip` fail with `Connection reset by peer`
> against PyPI, `requirements.txt` documents a working mirror:
> `pip install -r requirements.txt -i https://mirrors.cloud.tencent.com/pypi/simple/`
> (the `Dockerfile` accepts it as a build arg: `--build-arg PIP_INDEX_URL=...`).

### 3.4 Get the code + secrets
```bash
# as deploy, in the home directory
cd ~
git clone https://github.com/cyberking353/apkpolylms.git app
cd app
cp .env.example .env
```

---

## 4. Configure `.env` (the only real work)

Edit `~/app/.env`. Fill in at least this much to boot in production:

```bash
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<server-ip-or-domain>
DJANGO_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(64))">
DB_PASSWORD=<strong-random-password>

PORTAL_BACKEND_URL=https://api-demo.auxilax.com
LMS_API_TOKEN=<token-the-portal-sends>
PORTAL_SSO_SECRET=<same-secret-as-the-portal>
```

`DB_NAME`, `DB_USER`, `DB_HOST`, `DB_PORT`, `REDIS_URL` are optional — the stack supplies sane defaults and **overrides the host/port to talk to its own Postgres/Redis containers automatically**.

### About TLS / HTTPS (important)
The stack currently serves **plain HTTP on port 80**. Until you install Let's Encrypt certificates, keep these **unset or `false`** in `.env`:

```bash
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_SECURE_COOKIES=false
```

Once HTTPS is live (section 7), set them to `true` (or delete the lines) so Django enforces secure cookies + HTTPS redirect.

**Load tests / dev data already in the repo?** No conflict: `db.sqlite3` and `staticfiles/` are gitignored and never deployed; the app creates everything fresh on the server.

---

## 5. Deploy — first time

```bash
cd ~/app
docker compose up -d --build
```

What happens next (watch it): `docker compose logs -f web`

1. The `web` container **waits for Postgres to be reachable** (retry loop in `docker/entrypoint.sh`).
2. It runs `python manage.py migrate --noinput` (creates the schema).
3. It runs `python manage.py collectstatic --noinput` (builds static files into a shared volume Nginx serves).
4. Gunicorn boots with `2*CPU+1` workers (override with `GUNICORN_WORKERS` in `.env`).
5. `nginx` starts serving on port 80.

## 6. Verify it works

```bash
# are all 4 containers up and healthy?
docker compose ps
#  x  db    Up (healthy)
#  x  redis Up (healthy)
#  x  web   Up (healthy)
#  x  nginx Up (0.0.0.0:80->80/tcp)

# from your own computer:
curl http://YOUR_SERVER_IP/healthz        -> {"status": "ok", "db": "ok"}
curl -I http://YOUR_SERVER_IP/            -> HTTP/1.1 200
curl -I http://YOUR_SERVER_IP/static/css/main.css   -> HTTP/1.1 200
```

Create an admin account and log in:
```bash
docker compose exec web python manage.py createsuperuser
# then open http://YOUR_SERVER_IP/admin/ in a browser
```

**Import existing course data?** The repo ships a seed command:
```bash
docker compose exec web python manage.py create_crypto_course   # demo course
docker compose exec web python manage.py sync_portal            # pull data from the Portal
```

## 7. After you have a real domain (recommended, not required to launch)

1. Point the domain's `A` record at the server IP.
2. Install certbot on the host and issue a cert for the nginx vhost, or add TLS to `docker/nginx.conf`. OVH's DNS panel can do wildcard, but a single `www` cert is easiest.
3. Update `.env`:
   ```bash
   DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   DJANGO_SECURE_SSL_REDIRECT=true
   DJANGO_SECURE_COOKIES=true
   ```
4. `docker compose up -d` (rebuild is not needed) to pick up the new env.
5. Test the whole flow: HTTPS + SSO + sync webhooks against the new host.

---

## 8. Day-to-day operations

| Task | Command |
|---|---|
| Deploy new code | `cd ~/app && git pull && docker compose up -d --build` |
| See logs | `docker compose logs -f web` |
| Restart everything | `docker compose restart` |
| Stop everything (data kept) | `docker compose down` |
| Wipe everything (DB + uploads) | `docker compose down -v` |
| Open a shell in the app | `docker compose exec web bash` |
| Backup the database | `docker compose exec db pg_dump -U alhikma alhikma_lms > backup.sql` |
| Restore a backup | `cat backup.sql \| docker compose exec -T db psql -U alhikma alhikma_lms` |

**Automatic restarts:** every container has `restart: unless-stopped`, so the stack comes back on server reboots and after crashes, no systemd unit needed.

**Data lives in named volumes** (`pg_data`, `redis_data`, `static_volume`, `media_volume`), so `docker compose down` + `up` does not lose anything except during an explicit `down -v`.

---

## 9. Backups & monitoring (do these early)

- **Nightly DB dump** to off-VPS storage (OVH Object Storage, Backblaze B2, Rclone to anywhere). Test a restore before you trust it.
  ```bash
  # cron (root): 0 2 * * * docker compose -f /home/deploy/app/docker-compose.yml exec -T db pg_dump -U alhikma alhikma_lms | gzip > /var/backups/lms-$(date +\%F).sql.gz
  ```
- **Uptime check** on `http://YOUR_SERVER_IP/healthz` with UptimeRobot (free) or OVH monitoring.
- **Error tracking:** add Sentry (free tier) when you want Python exceptions surfaced automatically.

---

## 10. Scaling later (when it matters, not now)

1. **Vertical first** — a bigger VPS is the cheapest fix for this app for a long time.
2. Redis is already used for cache/sessions; enable it for expensive dashboard/progress queries via the Django cache API when needed.
3. Split Postgres/Redis onto their own nodes once the single box is genuinely overloaded.
4. If uploads grow huge, move `media_volume` to object storage (S3-compatible). Not a launch concern.

---

## 11. Open questions that affect prod (need an answer before switchover)

1. **Domain name(s)** — still TBD. Needed for `ALLOWED_HOSTS`, TLS certs, and to point the Portal's SSO callback at the right URL.
2. **SSO staff login** — lecturer accounts are created by the Portal's staff-sync, *not* auto-provisioned at SSO. Confirm the Portal has been pointed at this host's `/api/v1/sync` endpoints (sync already tested working) + keep `LMS_API_TOKEN` / `PORTAL_SSO_SECRET` identical to the Portal's config.
3. **Backup destination** — where nightly dumps should go (S3/B2/OVH Object Storage).