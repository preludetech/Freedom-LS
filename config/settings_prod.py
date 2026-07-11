import os

from .settings_base import *  # noqa: F403

HOST_DOMAIN = os.environ["HOST_DOMAIN"]


DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", HOST_DOMAIN]

# CSRF Configuration for HTTPS/Cloudflare tunnel
CSRF_TRUSTED_ORIGINS = [f"https://{HOST_DOMAIN}"]

# --- HTTPS Enforcement ---
SECURE_SSL_REDIRECT = True

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

SECRET_KEY = os.getenv("SECRET_KEY", "")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "USER": os.getenv("DB_USER", "DB_USER"),
        "NAME": os.getenv("DB_NAME", "DB_NAME"),
        "PASSWORD": os.getenv("DB_PASSWORD", "PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    },
}


# Static files
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # noqa: F405


# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django.log"),  # noqa: F405
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django_errors.log"),  # noqa: F405
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "security_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "security.log"),  # noqa: F405
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["error_file", "console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["security_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": False,
        },
        # Application loggers
        "freedom_ls": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}

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
        # default True (private signed URLs); case-insensitive so `false`/`False` both disable it
        querystring_auth=os.getenv("AWS_QUERYSTRING_AUTH", "True").strip().lower()
        != "false",
        querystring_expire=int(os.getenv("AWS_QUERYSTRING_EXPIRE", "3600")),
    )
else:
    default_storage = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }


# TODO @claude: Configure a production-ready TASKS backend (e.g., database-backed)
# when background tasks are used in production. The base setting uses ImmediateBackend
# which runs tasks synchronously.
TASKS = {
    "default": {
        "BACKEND": "django.tasks.backends.immediate.ImmediateBackend",
    },
}


STORAGES = {
    "default": default_storage,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
