"""
Django settings for health_insurance project.
Production-ready configuration using PostgreSQL in production.
"""

from pathlib import Path
import os
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ----------------------------
# Base directory
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ----------------------------
# Security
# ----------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")



# ----------------------------
# Applications
# ----------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "widget_tweaks",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    "accounts",
    "clients",
    "policies",
    "claims",
    "hospitals",
    "django_extensions",
]

# ----------------------------
# Middleware
# ----------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ----------------------------
# URLs and WSGI
# ----------------------------
ROOT_URLCONF = "health_insurance.urls"
WSGI_APPLICATION = "health_insurance.wsgi.application"

# ----------------------------
# Database: PostgreSQL production / SQLite dev
# ----------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES["default"] = dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        ssl_require=True  # Ensure SSL in production
    )

# ----------------------------
# Authentication
# ----------------------------
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

# ----------------------------
# CORS Security
# ----------------------------
CORS_ALLOW_ALL_ORIGINS = DEBUG

if not DEBUG:
    cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS")
    if cors_origins:
        CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins.split(",")]

# ----------------------------
# Password validation
# ----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ----------------------------
# Internationalization
# ----------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ----------------------------
# Static & Media Files
# ----------------------------
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if DEBUG:
    STATICFILES_DIRS = [BASE_DIR / "static"]
else:
    STATIC_ROOT = BASE_DIR / "staticfiles"
    STATICFILES_DIRS = []
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ----------------------------
# Templates
# ----------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

# ----------------------------
# Security for Production
# ----------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ----------------------------
# Logging
# ----------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ----------------------------
# Default primary key type
# ----------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------
# Login / Logout redirects
# ----------------------------
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/clients/login/"
