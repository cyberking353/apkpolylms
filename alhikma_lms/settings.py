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

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')

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

DEBUG = True

ALLOWED_HOSTS = ['*']

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
    'django.middleware.security.SecurityMiddleware',
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

# PythonAnywhere doesn't have Postgres on free tier — fall back to SQLite there.
if os.environ.get('PYTHONANYWHERE_DOMAIN'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'alhikma_lms',
            'USER': 'salim',
            'PASSWORD': '',
            'HOST': '',
            'PORT': '',
        }
    }

AUTH_USER_MODEL = 'accounts.Student'

LOGIN_URL           = '/accounts/login/'
LOGIN_REDIRECT_URL  = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

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
