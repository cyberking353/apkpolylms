import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path):
    """
    Minimal .env loader (no third-party dependency). Reads KEY=VALUE lines and
    sets them into os.environ only when not already set. The real secrets live
    in .env, which is gitignored — never hardcode them in code.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(BASE_DIR / '.env')

def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')

# ---------------------------------------------------------------------------
# Environment driven settings (never hardcode prod-sensitive values in code)
# ---------------------------------------------------------------------------

# Read from env at import time. Note: Django's test runner may flip the
# settings.DEBUG flag later, so find-time decisions (secret key, allowed
# hosts) are keyed on the ORIGINAL env value, not the mutable flag.
DJANGO_DEBUG_ENV = _env_bool('DJANGO_DEBUG', default=True)
DEBUG = DJANGO_DEBUG_ENV

# In production DJANGO_ALLOWED_HOSTS MUST be set in .env (comma-separated). If
# you're wondering why requests 400: an ALLOWED_HOSTS mismatch is the culprit.
_ENV_ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').strip()
if _ENV_ALLOWED_HOSTS:
    ALLOWED_HOSTS = [h.strip() for h in _ENV_ALLOWED_HOSTS.split(',') if h.strip()]
elif DJANGO_DEBUG_ENV:
    # Dev/test defaults — includes 'testserver' used by Django's live test client.
    # PythonAnywhere is a transitional host: allow its assigned domain too.
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '::1', 'testserver']
    if os.environ.get('PYTHONANYWHERE_DOMAIN'):
        ALLOWED_HOSTS.append(os.environ['PYTHONANYWHERE_DOMAIN'])
else:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        'DJANGO_ALLOWED_HOSTS is required when DJANGO_DEBUG is false. Set it in .env.'
    )

# Fail hard if we're running in production WITHOUT a real secret key.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DJANGO_DEBUG_ENV:
        SECRET_KEY = 'django-insecure-dev-only-change-me'
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false. Set it in .env.'
        )

# --- Portal <-> LMS integration secrets (server-side only, from .env) ---

# Bearer token the Portal sends on every /api/v1/sync/* request to the LMS.
# Named LMS_API_TOKEN to match the Portal integration guide. SMS_API_TOKEN is
# kept as a fallback for older environments.
LMS_API_TOKEN = (
    os.environ.get('LMS_API_TOKEN') or os.environ.get('SMS_API_TOKEN')
    or 'lms-dev-token-change-me'
)

# HMAC-SHA256 secret used to verify the Portal's SSO JWT assertions
# (POST /api/v1/auth/sso and GET /sso/callback). Must equal the Portal's
# LMS_SSO_SECRET. The guide calls it PORTAL_SSO_SECRET; we accept both names.
PORTAL_SSO_SECRET = (
    os.environ.get('PORTAL_SSO_SECRET') or os.environ.get('LMS_SSO_SECRET')
    or ''
)

# Public base URL of the Portal backend, used by the bootstrap pull command
# (manage.py sync_portal) to hit GET /api/v1/lms/sync/init/*.
PORTAL_BACKEND_URL = os.environ.get('PORTAL_BACKEND_URL', '')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'departments',
    'courses',
    'quizzes',
    'exams',
    'results',
    'portal',
    'announcements',
    'api',
]

MIDDLEWARE = [
    'alhikma_lms.middleware.NoCacheHTMLMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'alhikma_lms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'portal.context_processors.portal_counts',
                'courses.context_processors.message_counts',
            ],
        },
    },
]

WSGI_APPLICATION = 'alhikma_lms.wsgi.application'

# Database: production (PaaS) uses PostgreSQL via a single DATABASE_URL
# connection string provided by the platform. Legacy DB_HOST/DB_NAME/DB_USER/
# DB_PASSWORD env vars are kept as a fallback for local/dev setups.
# PythonAnywhere free tier has no Postgres — fall back to SQLite there.
# DEV_DATABASE=sqlite can also be forced for a no-Postgres local experiment.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

_ENV_DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if _ENV_DATABASE_URL:
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(
        _ENV_DATABASE_URL,
        conn_max_age=int(os.environ.get('DB_CONN_MAX_AGE', '60')),
    )
elif not os.environ.get('DEV_DATABASE', '').lower() == 'sqlite' \
        and not os.environ.get('PYTHONANYWHERE_DOMAIN'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'alhikma_lms'),
        'USER': os.environ.get('DB_USER', 'salim'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': os.environ.get('DB_PORT', ''),
        'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),  # reuse conns
        'OPTIONS': {'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '5'))},
    }

AUTH_USER_MODEL = 'accounts.Student'

LOGIN_URL           = '/accounts/login/'
LOGIN_REDIRECT_URL  = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Cache + sessions. If REDIS_URL is provided we use Redis (fast, multi-worker,
# survives restarts). Otherwise fall back to per-process locmem + DB sessions —
# fine for local dev, but never scale horizontally without Redis.
REDIS_URL = os.environ.get('REDIS_URL', '')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Lagos'
USE_I18N      = True
USE_TZ        = True

STATIC_URL       = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT      = BASE_DIR / 'staticfiles'

# Whitenoise serves collected static files directly from Django (no nginx).
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days for immutable content

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG:   'debug',
    messages.INFO:    'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR:   'error',
}

# ---------------------------------------------------------------------------
# Transport security (only enforced when DEBUG=false / behind TLS)
# ---------------------------------------------------------------------------
if not DJANGO_DEBUG_ENV:
    # Secure cookies default ON in prod, but can be relaxed while testing over
    # plain HTTP before TLS is installed (see DJANGO_SECURE_SSL_REDIRECT too).
    _secure_cookies = _env_bool('DJANGO_SECURE_COOKIES', default=True)
    SESSION_COOKIE_SECURE = _secure_cookies
    CSRF_COOKIE_SECURE = _secure_cookies
    CSRF_COOKIE_HTTPONLY = True
    # SSL redirect defaults ON in prod, but can be switched off while TLS
    # certificates are not yet installed behind the reverse proxy.
    SECURE_SSL_REDIRECT = _env_bool('DJANGO_SECURE_SSL_REDIRECT', default=True)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Trust X-Forwarded-Proto from Nginx/Caddy so SSL redirect works behind TLS.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# CSRF origins. If you run behind a reverse proxy on a custom domain and you
# set DJANGO_ALLOWED_HOSTS, we mirror them onto CSRF_TRUSTED_ORIGINS.
CSRF_TRUSTED_ORIGINS = [
    f'https://{host}' for host in ALLOWED_HOSTS
    if host not in ('localhost', '127.0.0.1', '0.0.0.0', '::1')
]

# ---------------------------------------------------------------------------
# Logging — console buffer for dev, file + console for prod. Request bodies are
# NEVER logged: JWT assertions and sync tokens must not reach log files.
# ---------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / 'logs'
if not DEBUG:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if not DEBUG else 'DEBUG',
    },
}
if not DEBUG:
    LOGGING['handlers']['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': LOGS_DIR / 'app.log',
        'maxBytes': 5 * 1024 * 1024,
        'backupCount': 5,
        'formatter': 'verbose',
    }
    LOGGING['root']['handlers'].append('file')