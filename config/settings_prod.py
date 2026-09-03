import os

from freedom_ls.base.env import env_int, env_str
from freedom_ls.deployment import settings_defaults as fls_defaults
from freedom_ls.deployment.storage import build_storages

from .settings_base import *  # noqa: F403

HOST_DOMAIN = os.environ["HOST_DOMAIN"]


DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", HOST_DOMAIN]

# CSRF Configuration for HTTPS/Cloudflare tunnel
CSRF_TRUSTED_ORIGINS = [f"https://{HOST_DOMAIN}"]

# --- HTTPS Enforcement ---
SECURE_SSL_REDIRECT = True

# Safe as a hard default because production terminates TLS at a trusted proxy that
# forwards X-Forwarded-Proto: https on every request reaching this app; the trust
# preconditions live beside the primitive in settings_defaults.py.
SECURE_PROXY_SSL_HEADER = fls_defaults.SECURE_PROXY_SSL_HEADER
SECURE_REDIRECT_EXEMPT = fls_defaults.SECURE_REDIRECT_EXEMPT

# --- HSTS (configurable rollout via env vars) ---
SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    os.environ.get("HSTS_INCLUDE_SUBDOMAINS", "False") == "True"
)
SECURE_HSTS_PRELOAD = os.environ.get("HSTS_PRELOAD", "False") == "True"

# --- Secure Cookies ---
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# --- Security Headers ---
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Session Timeout ---
SESSION_COOKIE_AGE = 1209600  # 2 weeks

# --- Upload Limits ---
DATA_UPLOAD_MAX_MEMORY_SIZE = 5_242_880  # 5 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5_242_880  # 5 MB

SECRET_KEY = fls_defaults.require_secret_key()
SALT_KEY = fls_defaults.require_webhook_encryption_salt()

# Explicitly typed so the OPTIONS/CONN_MAX_AGE/CONN_HEALTH_CHECKS values added below
# (not all plain strings) type-check as assignments into the same dict.
DATABASES: dict[str, dict[str, str | int | bool | dict[str, str]]] = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "USER": os.getenv("DB_USER", "DB_USER"),
        "NAME": os.getenv("DB_NAME", "DB_NAME"),
        "PASSWORD": os.getenv("DB_PASSWORD", "PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    },
}

DATABASES["default"]["OPTIONS"] = fls_defaults.database_ssl_options(
    os.getenv("DB_SSLMODE", "prefer")
)

DATABASES["default"]["CONN_MAX_AGE"] = env_int(
    "DB_CONN_MAX_AGE", fls_defaults.CONN_MAX_AGE
)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = fls_defaults.CONN_HEALTH_CHECKS

# Durable, database-backed task backend (django-tasks-db). Requires a running
# `python manage.py fls_run_worker` process; see settings_defaults.py for details.
TASKS = fls_defaults.DATABASE_TASKS

CACHES = fls_defaults.DATABASE_CACHES


# Static files
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # noqa: F405


# Logging configuration
# Stdout only: the container log driver is what caps and rotates output, not this
# process. Writing to disk here would let logs fill the container's own filesystem.
LOGGING = fls_defaults.build_logging_config()

# Email

# Queued by default: an SMTP session against a hosted provider costs seconds and the
# sender waits for all of it, so QueuedEmailBackend hands the message to the task queue
# and fls_run_worker sends it through EMAIL_UPSTREAM_BACKEND. Still env-overridable --
# setting EMAIL_BACKEND back to the SMTP backend restores synchronous in-request
# sending for a deployment that runs no worker. To keep queueing but send through a
# provider's own backend, set EMAIL_UPSTREAM_BACKEND (see deployment/config.py) rather
# than this.
EMAIL_BACKEND = env_str("EMAIL_BACKEND", fls_defaults.QUEUED_EMAIL_BACKEND)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", fls_defaults.EMAIL_TIMEOUT_SECONDS)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)


# Allauth

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# Do not set ALLAUTH_TRUSTED_PROXY_COUNT; it selects the X-Forwarded-For path
# instead. Naming the header removes allauth's fallback to REMOTE_ADDR, so the
# edge header becomes load-bearing for login and signup here in production; the
# trust preconditions live beside the primitive in settings_defaults.py.
#
# Read from the environment because the header is a property of whichever edge is
# in front of this deployment, not of FLS: the default names the one cloudflared
# sets, and an edge that sets a different one would otherwise 403 every login with
# nothing to change short of a code edit. Both settings come from the one
# expression so they cannot drift apart -- axes and allauth keying their counters
# on different addresses is checked by freedom_ls_deployment.E006.
TRUSTED_PROXY_IP_HEADER = env_str(
    "TRUSTED_CLIENT_IP_HEADER", fls_defaults.TRUSTED_CLIENT_IP_HEADER
)
ALLAUTH_TRUSTED_CLIENT_IP_HEADER = TRUSTED_PROXY_IP_HEADER


# Media Storage
#
# Every alias is declared, always. A missing alias is what turned a settings gap
# into learner PII in a shared bucket, so there is no conditional here and no
# fallback path: build_storages() resolves each alias from its own environment
# variables and emits a key either way. Under `manage.py check --deploy`,
# freedom_ls_deployment.E001 through E004 are what catch an alias that landed
# somewhere it should not have. The three alias names come from the settings that
# name them, so renaming one moves the emitted key with it.
STORAGES = build_storages(
    staticfiles={"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    logo_alias=ORGANISATION_LOGO_STORAGE_ALIAS,  # noqa: F405
    content_media_alias=CONTENT_MEDIA_STORAGE_ALIAS,  # noqa: F405
    reports_alias=REPORTS_STORAGE_ALIAS,  # noqa: F405
)
