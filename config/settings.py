# config/settings.py
from pathlib import Path
from decouple import config
import dj_database_url
import os

PORT = int(os.environ.get("PORT", 8000))

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-mosc2bzzdpp-ci5zxj*0-kwu6&0rw3v_-i-7a^i1(_8aus9=c$"
)
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "192.168.0.17",
    "backendveinviewar-production.up.railway.app",
    "*",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_yasg",
    "placa.apps.PlacaConfig",
    "profesor.apps.ProfesorConfig",
    "estudiantes.apps.EstudiantesConfig",
    "RA.apps.RAConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",   # antes de CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF    = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS":    [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ── Base de datos ─────────────────────────────────────────────────────────────
DATABASE_URL = config("DATABASE_URL", default="sqlite:///db.sqlite3")
if DATABASE_URL.startswith("sqlite"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME":   BASE_DIR / "db.sqlite3",
        }
    }
    print("🔵 Usando SQLite (desarrollo local)")
else:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL, conn_max_age=600, conn_health_checks=True
        )
    }
    print("🟢 Usando PostgreSQL (Railway)")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE     = "America/Bogota"
USE_I18N      = True
USE_TZ        = True

STATIC_URL   = "/static/"
STATIC_ROOT  = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── DRF ───────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE":       20,
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
}

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  False,
    "BLACKLIST_AFTER_ROTATION": True,
    "TOKEN_OBTAIN_SERIALIZER": "config.serializers.CustomTokenObtainPairSerializer",
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOW_CREDENTIALS = True

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    # En Railway definir: CORS_ALLOWED_ORIGINS=https://tudominio.com
    _cors_default = "https://backendveinviewar-production.up.railway.app"
    CORS_ALLOWED_ORIGINS = config(
        "CORS_ALLOWED_ORIGINS", default=_cors_default
    ).split(",")

# CORREGIDO: incluir cabeceras del ESP32 y del dashboard RA
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-api-key",        # Autenticación del ESP32
    "x-session-token",  # Sesión del dashboard RA
]

# ── Seguridad en producción ───────────────────────────────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER     = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST        = True
    USE_X_FORWARDED_PORT        = True
    SECURE_SSL_REDIRECT         = False   # Railway ya maneja la redirección
    SESSION_COOKIE_SECURE       = True
    CSRF_COOKIE_SECURE          = True
    SECURE_BROWSER_XSS_FILTER   = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    "version":                  1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {module} {message}",
            "style":  "{",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django":          {"handlers": ["console"], "level": "INFO",  "propagate": True},
        "placa":           {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO",
                            "propagate": False},
        "RA":              {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO",
                            "propagate": False},
        "gunicorn.error":  {"handlers": ["console"], "level": "INFO",  "propagate": False},
        "gunicorn.access": {"handlers": ["console"], "level": "INFO",  "propagate": False},
    },
}

print("=" * 60)
print("🔧 VeinView AR — Django Configuration")
print(f"   DEBUG:    {DEBUG}")
print(f"   DATABASE: {'PostgreSQL' if not DATABASE_URL.startswith('sqlite') else 'SQLite'}")
print(f"   PORT:     {PORT}")
print(f"   HOSTS:    {ALLOWED_HOSTS}")
print("=" * 60)