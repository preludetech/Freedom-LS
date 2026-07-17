import os

from freedom_ls.base.env import env_bool, env_int
from freedom_ls.deployment import settings_defaults as fls_defaults

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


# Static files
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # noqa: F405


# Logging configuration
# log_dir is temporary: drop it once container-level log size/rotation caps exist,
# to move to stdout-only.
LOGGING = fls_defaults.build_logging_config(log_dir=BASE_DIR / "logs")  # noqa: F405

# Email

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)


# Allauth

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"


# Media Storage

AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")

if AWS_STORAGE_BUCKET_NAME:
    from freedom_ls.deployment.storage import build_s3_media_storage

    default_storage = build_s3_media_storage(
        bucket_name=AWS_STORAGE_BUCKET_NAME,
        access_key=os.getenv("AWS_S3_ACCESS_KEY_ID"),
        secret_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),
        region_name=os.getenv("AWS_S3_REGION_NAME"),
        custom_domain=os.getenv("AWS_S3_CUSTOM_DOMAIN"),  # unset ⇒ private signed URLs
        # default True (private signed URLs); any falsy value (false/0/no/off) opts into public serving
        querystring_auth=env_bool("AWS_QUERYSTRING_AUTH", True),
        querystring_expire=env_int("AWS_QUERYSTRING_EXPIRE", 3600),
    )
else:
    default_storage = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }


STORAGES = {
    "default": default_storage,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
