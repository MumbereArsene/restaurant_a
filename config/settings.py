"""
Django settings — local (SQLite) + Northflank production (Postgres + Cloudinary).
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-only-key-change-me-in-production",
)

DEBUG = os.getenv("DEBUG", "1") == "1"

# Comma-separated hosts + optional Northflank / public domain
_hosts = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
_public_domain = (
    os.getenv("PUBLIC_DOMAIN", "").strip()
    or os.getenv("NF_HOSTS", "").strip().split(",")[0].strip()
)
if _public_domain and _public_domain not in _hosts:
    _hosts.append(_public_domain)
# Northflank preview / custom hostnames often include these suffixes
if os.getenv("NORTHFLANK") or os.getenv("NF_PROJECT_ID"):
    for suffix in (".northflank.app", ".code.run"):
        if suffix not in _hosts and f".{suffix.lstrip('.')}" not in str(_hosts):
            _hosts.append(suffix)
ALLOWED_HOSTS = _hosts or ["localhost"]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]
if _public_domain:
    for scheme in ("https", "http"):
        origin = f"{scheme}://{_public_domain}"
        if origin not in CSRF_TRUSTED_ORIGINS and scheme == "https":
            CSRF_TRUSTED_ORIGINS.append(origin)
if (os.getenv("NORTHFLANK") or os.getenv("NF_PROJECT_ID")) and not any(
    "northflank" in o or "code.run" in o for o in CSRF_TRUSTED_ORIGINS
):
    CSRF_TRUSTED_ORIGINS.extend(
        [
            "https://*.northflank.app",
            "https://*.code.run",
        ]
    )


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "cloudinary_storage",
    "django.contrib.staticfiles",
    "cloudinary",
    # Local apps
    "accounts",
    "core",
    "tables",
    "menu",
    "orders",
    "reservations",
    "cash",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.restaurant",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database: DATABASE_URL (Northflank Postgres) > explicit PG > SQLite
# ---------------------------------------------------------------------------
_database_url = os.getenv("DATABASE_URL", "").strip()
if _database_url:
    DATABASES = {
        "default": dj_database_url.config(
            default=_database_url,
            conn_max_age=600,
            ssl_require=os.getenv("DB_SSL_REQUIRE", "1") == "1",
        )
    }
elif os.getenv("DB_ENGINE") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "restaurant"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "fr"

LANGUAGES = [
    ("fr", "Français"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = os.getenv("TIME_ZONE", "Africa/Kinshasa")

USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static (WhiteNoise) & media (Cloudinary in prod, local disk in dev)
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))

# Cloudinary credentials: CLOUDINARY_URL or discrete vars
_cloudinary_url = os.getenv("CLOUDINARY_URL", "").strip()
_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
_cloud_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
_cloud_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
USE_CLOUDINARY = bool(_cloudinary_url or (_cloud_name and _cloud_key and _cloud_secret))

if USE_CLOUDINARY:
    if _cloud_name:
        CLOUDINARY_STORAGE = {
            "CLOUD_NAME": _cloud_name,
            "API_KEY": _cloud_key,
            "API_SECRET": _cloud_secret,
        }
    folder = os.getenv("CLOUDINARY_FOLDER", "restaurant").strip()
    if folder:
        CLOUDINARY_STORAGE = {
            **globals().get("CLOUDINARY_STORAGE", {}),
            "PREFIX": folder,
        }
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
    SERVE_MEDIA = False
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
    SERVE_MEDIA = os.getenv("SERVE_MEDIA", "1") == "1"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CURRENCY = os.getenv("CURRENCY", "$")

# Behind Northflank / reverse proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
