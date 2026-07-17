"""Thin, pure module of deployment-settings primitives consumed by
config/settings_prod.py.

Flat constants and small functions only. Only stdlib and django.core.exceptions at
module top — nothing that touches the app registry — so this is safe to import at
settings-load time before the registry is ready (matching freedom_ls/base/env.py).
Unit-tested in freedom_ls/deployment/tests/test_settings_defaults.py.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Trustworthy only when production terminates TLS at a proxy that forwards
# X-Forwarded-Proto: https on every request reaching this app. That requires all of:
#   1. the origin is firewalled to the proxy's published IP ranges, so no client can
#      reach this app directly and forge the header itself;
#   2. the proxy's edge TLS mode is Full (strict), never Flexible — Flexible lets the
#      proxy claim https while speaking plain http to the origin;
#   3. the proxy's trusted-proxy list is scoped exactly to those IP ranges, never
#      0.0.0.0/0 — otherwise anyone can front the app with their own header;
#   4. the app container publishes no port except through the proxy, so there is no
#      unproxied path that skips header injection entirely;
#   5. no custom upstream header rule overrides the proxy's default
#      X-Forwarded-Proto value.
# Any one of these missing turns the header into an attacker-controlled input and
# Django would treat plain-http requests as secure.
SECURE_PROXY_SSL_HEADER: tuple[str, str] = ("HTTP_X_FORWARDED_PROTO", "https")

# Persistent DB connections. Recommended 60-300s; never None/unlimited, which would
# let connections accumulate without bound under load.
CONN_MAX_AGE: int = 60
CONN_HEALTH_CHECKS: bool = True


def require_secret_key() -> str:
    """Return SECRET_KEY from the environment, raising ImproperlyConfigured if
    unset/empty/whitespace-only.

    Fails fast during Gunicorn boot (visible crash-loop) instead of lazily on the
    first request that signs a cookie. Strips first so a whitespace-only value
    (e.g. " ") — truthy in Python but a functionally-broken key — is rejected too. A
    blank SECRET_KEY silently disables session/CSRF signing rather than raising, so
    catching it here is the only way to avoid a production deployment that looks up
    but has no real security boundary. Raises ImproperlyConfigured (not a bare
    KeyError) to match freedom_ls/base/env.py and give a clear boot traceback.
    """
    key = os.environ.get("SECRET_KEY", "").strip()
    if not key:
        raise ImproperlyConfigured(
            "SECRET_KEY must be set to a non-empty value in production."
        )
    return key


def database_ssl_options(sslmode: str) -> dict[str, str]:
    """Return the DATABASES OPTIONS dict for a libpq sslmode, e.g. {"sslmode": "prefer"}.

    Kept as a function (not a bare literal in settings_prod) so future
    sslmode-adjacent options (e.g. sslrootcert) can be added in one place and reach
    every project on a bump.
    """
    return {"sslmode": sslmode}


def build_logging_config(*, log_dir: Path | None = None) -> dict:
    """Return a Django LOGGING dict.

    Default (log_dir=None): stdout only, via a single StreamHandler shared by every
    logger — container-friendly, no on-disk state.

    When log_dir is supplied: additionally writes rotating file handlers under
    log_dir, reproducing the on-disk logging behaviour needed until the deployment's
    container log driver caps its own max size/file count. Until then, omitting
    log_dir would relocate the disk-fill risk onto an uncapped container log rather
    than removing it.
    """
    formatters = {
        "verbose": {
            "format": "{levelname} {asctime} {name} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    }
    filters = {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    }

    handlers: dict[str, dict] = {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    }

    if log_dir is None:
        general_handlers = ["console"]
        error_handlers = ["console"]
        security_handlers = ["console"]
        db_handlers = ["console"]
    else:
        handlers["file"] = {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / "django.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        }
        handlers["error_file"] = {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / "django_errors.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        }
        # Kept separate from "file" so security events (SuspiciousOperation,
        # DisallowedHost, CSRF failures) stay isolated for audit/alerting rather than
        # being buried in general request noise.
        handlers["security_file"] = {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / "security.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        }
        general_handlers = ["console", "file"]
        error_handlers = ["console", "error_file"]
        security_handlers = ["console", "security_file"]
        db_handlers = ["file"]

    loggers = {
        "django": {
            "handlers": general_handlers,
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": error_handlers,
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": security_handlers,
            "level": "INFO",
            "propagate": False,
        },
        # Kept at WARNING and non-propagating so per-query SQL logging never floods
        # the root logger at INFO.
        "django.db.backends": {
            "handlers": db_handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "freedom_ls": {
            "handlers": general_handlers,
            "level": "INFO",
            "propagate": False,
        },
    }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "filters": filters,
        "handlers": handlers,
        "loggers": loggers,
        "root": {
            "handlers": general_handlers,
            "level": "INFO",
        },
    }
