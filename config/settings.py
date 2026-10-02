"""
Helply settings.

Configuration is read from environment variables so the same code runs
locally (SQLite, no setup) and in Docker (PostgreSQL). See .env.example.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path):
    """Read KEY=VALUE lines from a local .env file. Real environment variables take precedence."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Helply apps
    "apps.core",
    "apps.accounts",
    "apps.tickets",
    "apps.sla",
    "apps.assets",
    "apps.kb",
    "apps.ai",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
                "apps.notifications.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL when POSTGRES_DB is set (Docker), otherwise SQLite for quick local dev.
# HELPLY_USE_SQLITE=1 forces SQLite, e.g. when this drive is plugged into a computer without Docker.
if os.environ.get("POSTGRES_DB") and not env_bool("HELPLY_USE_SQLITE"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "helply"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "en-ca"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Helply business settings ------------------------------------------------
# Pluggable AI backend. The keyword backend is a deterministic baseline;
# swap in an LLM / embedding backend later without touching business code.
HELPLY_AI_BACKEND = os.environ.get("HELPLY_AI_BACKEND", "apps.ai.backends.keyword.KeywordBackend")
# Minimum classifier confidence for a ticket to be auto-triaged without a supervisor.
HELPLY_AI_AUTO_TRIAGE_THRESHOLD = float(os.environ.get("HELPLY_AI_AUTO_TRIAGE_THRESHOLD", "0.6"))
# Auto-assign auto-triaged tickets to the least-loaded technician of the group.
HELPLY_AI_AUTO_ASSIGN = env_bool("HELPLY_AI_AUTO_ASSIGN", True)
# Share of the resolution window elapsed after which a ticket is flagged "at risk".
HELPLY_SLA_AT_RISK_RATIO = float(os.environ.get("HELPLY_SLA_AT_RISK_RATIO", "0.75"))

# --- Notifications -------------------------------------------------------------
# Development prints emails to the console. For real email set DJANGO_EMAIL_BACKEND to
# django.core.mail.backends.smtp.EmailBackend and the EMAIL_* variables below.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Helply IT Service Desk <helpdesk@example.com>")
# Used to build links in emails.
HELPLY_SITE_URL = os.environ.get("HELPLY_SITE_URL", "http://127.0.0.1:8000").rstrip("/")
# At most one email of the same kind per ticket per person within this window; in-app notifications are not throttled.
HELPLY_EMAIL_THROTTLE_MINUTES = int(os.environ.get("HELPLY_EMAIL_THROTTLE_MINUTES", "10"))
# Resolved tickets: remind the requester after N days, close automatically after M days.
HELPLY_CONFIRM_REMINDER_DAYS = int(os.environ.get("HELPLY_CONFIRM_REMINDER_DAYS", "2"))
HELPLY_AUTO_CLOSE_DAYS = int(os.environ.get("HELPLY_AUTO_CLOSE_DAYS", "5"))
