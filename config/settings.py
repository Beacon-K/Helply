"""
Helply settings.

Configuration is read from environment variables (or the local .env file) so the
same code runs in development, for demos and in production. See .env.example.

HELPLY_ENVIRONMENT selects the mode:
  development  (default) debug pages on, demo data allowed
  demo         debug off, demo data allowed (start-demo.bat / start-online.bat)
  production   debug off, a fixed DJANGO_SECRET_KEY is required, and every command
               that loads or wipes demo data refuses to run
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

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


HELPLY_ENVIRONMENT = os.environ.get("HELPLY_ENVIRONMENT", "development").strip().lower()
if HELPLY_ENVIRONMENT not in ("development", "demo", "production"):
    raise ImproperlyConfigured("HELPLY_ENVIRONMENT must be development, demo or production.")
IS_PRODUCTION = HELPLY_ENVIRONMENT == "production"

DEV_SECRET_KEY = "dev-insecure-change-me"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", DEV_SECRET_KEY)
if IS_PRODUCTION and (SECRET_KEY == DEV_SECRET_KEY or len(SECRET_KEY) < 40):
    # A fixed, private key keeps people signed in across restarts and makes password-reset links valid.
    raise ImproperlyConfigured("Production needs a private DJANGO_SECRET_KEY of at least 40 characters in .env "
                               "(setup.bat generates one).")
DEBUG = env_bool("DJANGO_DEBUG", HELPLY_ENVIRONMENT == "development")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Public demo behind Cloudflare Tunnel (see start-online.bat). The tunnel terminates HTTPS
# and forwards to this computer on 127.0.0.1 only, so its X-Forwarded-Proto header can be trusted.
HELPLY_PUBLIC_HOST = os.environ.get("HELPLY_PUBLIC_HOST", "").strip()
if HELPLY_PUBLIC_HOST:
    ALLOWED_HOSTS += [HELPLY_PUBLIC_HOST, f"www.{HELPLY_PUBLIC_HOST}"]
    CSRF_TRUSTED_ORIGINS = [f"https://{HELPLY_PUBLIC_HOST}", f"https://www.{HELPLY_PUBLIC_HOST}"]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_SSL_REDIRECT = True
    # Short HSTS window and no subdomains, so the domain is not locked to this setup for long.
    SECURE_HSTS_SECONDS = 3600

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
    "apps.monitoring",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves CSS/JS/images when DEBUG is off
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
                "apps.core.context_processors.asset_version",
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
            # The web server, scheduled jobs and monitoring agents write at the same time: WAL lets readers
            # and one writer work together, and IMMEDIATE + timeout make writers queue instead of failing.
            "OPTIONS": {
                "timeout": 20,
                "transaction_mode": "IMMEDIATE",
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            },
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
# Minimum classifier confidence for a ticket to be auto-triaged without a administrator.
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
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))  # Django waits forever by default
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Helply IT Service Desk <helpdesk@example.com>")
# Never send email to these domains: they are reserved for documentation and testing (RFC 2606 / 6761), so
# nothing can be delivered there, and the bounces would damage the sending domain's reputation with the mail
# provider. A name without a leading dot blocks that domain and its subdomains; ".test" blocks the whole suffix.
# Notifications to such addresses still appear in the app. Set HELPLY_EMAIL_BLOCKED_DOMAINS (comma separated)
# to block more, e.g. a placeholder domain used by demo accounts; the reserved ones are always blocked.
HELPLY_EMAIL_BLOCKED_DOMAINS = tuple(dict.fromkeys(
    ("example.com", "example.org", "example.net", ".example", ".test", ".invalid", ".localhost")
    + tuple(d.strip().lower() for d in os.environ.get("HELPLY_EMAIL_BLOCKED_DOMAINS", "").split(",") if d.strip())
))
# Used to build links in emails.
HELPLY_SITE_URL = os.environ.get("HELPLY_SITE_URL", "http://127.0.0.1:8000").rstrip("/")
# At most one email of the same kind per ticket per person within this window; in-app notifications are not throttled.
HELPLY_EMAIL_THROTTLE_MINUTES = int(os.environ.get("HELPLY_EMAIL_THROTTLE_MINUTES", "10"))
# Resolved tickets: remind the requester after N days, close automatically after M days.
HELPLY_CONFIRM_REMINDER_DAYS = int(os.environ.get("HELPLY_CONFIRM_REMINDER_DAYS", "2"))
HELPLY_AUTO_CLOSE_DAYS = int(os.environ.get("HELPLY_AUTO_CLOSE_DAYS", "5"))

# --- Logging --------------------------------------------------------------------
# Warnings and errors go to logs/helply.log (rotated), so problems can be investigated
# when debug pages are off.
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "helply.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "plain",
            "level": "WARNING",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {"django.server": {"level": "WARNING"}},
}

# --- Backups ----------------------------------------------------------------------
HELPLY_BACKUP_DIR = Path(os.environ.get("HELPLY_BACKUP_DIR", BASE_DIR / "backups"))
HELPLY_BACKUP_KEEP = int(os.environ.get("HELPLY_BACKUP_KEEP", "14"))

# Cloud server monitoring (apps.monitoring). The agent reports about every 10 seconds.
HELPLY_MONITOR_OFFLINE_SECONDS = int(os.environ.get("HELPLY_MONITOR_OFFLINE_SECONDS", "60"))  # card turns grey
HELPLY_MONITOR_ALERT_OFFLINE_SECONDS = int(os.environ.get("HELPLY_MONITOR_ALERT_OFFLINE_SECONDS", "120"))  # ticket
# Who is emailed (besides the ticket assignee's normal notices) when a server goes offline; must match a user's email.
HELPLY_MONITOR_OFFLINE_EMAILS = tuple(
    e.strip() for e in os.environ.get("HELPLY_MONITOR_OFFLINE_EMAILS", "alice@helply.work").split(",") if e.strip())
HELPLY_MONITOR_CPU_PERCENT = float(os.environ.get("HELPLY_MONITOR_CPU_PERCENT", "90"))
HELPLY_MONITOR_MEM_PERCENT = float(os.environ.get("HELPLY_MONITOR_MEM_PERCENT", "90"))
HELPLY_MONITOR_DISK_PERCENT = float(os.environ.get("HELPLY_MONITOR_DISK_PERCENT", "90"))
HELPLY_MONITOR_SUSTAIN_MINUTES = int(os.environ.get("HELPLY_MONITOR_SUSTAIN_MINUTES", "5"))
HELPLY_MONITOR_MIN_INTERVAL = float(os.environ.get("HELPLY_MONITOR_MIN_INTERVAL", "3"))  # ignore faster reports
HELPLY_MONITOR_RAW_HOURS = int(os.environ.get("HELPLY_MONITOR_RAW_HOURS", "48"))
HELPLY_MONITOR_HOURLY_DAYS = int(os.environ.get("HELPLY_MONITOR_HOURLY_DAYS", "90"))
