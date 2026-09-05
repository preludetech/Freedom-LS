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

# The header the edge sets to the visitor's own address, read by get_client_ip for
# django-axes lockout keys and LegalConsent records, and handed to allauth as
# ALLAUTH_TRUSTED_CLIENT_IP_HEADER. It must be one the edge *sets* rather than
# appends, so it carries exactly one address.
#
# It needs preconditions 1, 3 and 4 above just as much as X-Forwarded-Proto does:
# any path that reaches the origin without traversing the proxy lets a client set
# this header itself, and then it picks its own lockout key — rotating the value
# per attempt so the failure counter never reaches AXES_FAILURE_LIMIT — and writes
# whatever address it likes into the consent evidence trail.
#
# Naming a header also removes allauth's own fallback to REMOTE_ADDR, so this is
# load-bearing in the other direction too: an edge that does not set it makes
# allauth's get_client_ip return None, and every login, signup and password-reset
# answers 403. The default names the header cloudflared sets, matching the tunnel
# the production settings already assume; an edge that sets a different one is
# configured through the TRUSTED_CLIENT_IP_HEADER environment variable rather than
# by editing this value.
TRUSTED_CLIENT_IP_HEADER: str = "CF-Connecting-IP"

# Persistent DB connections. Recommended 60-300s; never None/unlimited, which would
# let connections accumulate without bound under load.
CONN_MAX_AGE: int = 60
CONN_HEALTH_CHECKS: bool = True

# Path-prefix regexes exempt from SECURE_SSL_REDIRECT's 301→https. Internal probes
# hit /health/… over plain HTTP (Docker healthcheck / smoke test); paired with the
# proxy-header setting, a naive probe would otherwise read the 301 as unhealthy.
# Exempting the prefix serves those paths plainly. Assigned in config/settings_prod.py
# and kept greppable there rather than mutated invisibly from an AppConfig.
SECURE_REDIRECT_EXEMPT: list[str] = [r"^health/"]

# Durable, database-backed task backend for production (django-tasks-db, ORM/Postgres —
# no Celery/Redis). HARD operational dependency: an out-of-process
# `python manage.py fls_run_worker` must be running, or enqueued tasks persist in the DB
# and never execute. Enqueue is a plain INSERT with no on-commit machinery of its own,
# so it joins whatever transaction is open and the worker cannot see the row until that
# commits; a caller whose task needs its own row committed first wraps the enqueue in
# transaction.on_commit itself, as reports/views.py does.
DATABASE_TASKS: dict[str, dict[str, str]] = {
    "default": {"BACKEND": "django_tasks_db.DatabaseBackend"},
}


# Outgoing mail is handed to the task queue rather than sent in the request: an SMTP
# session against a hosted provider costs seconds, and the sender waits for all of it.
# A dotted string rather than an import, per this module's stdlib-only rule. Both
# settings modules point EMAIL_BACKEND here; EMAIL_UPSTREAM_BACKEND (declared in this
# app's config.py) is what the worker actually sends through.
QUEUED_EMAIL_BACKEND: str = "freedom_ls.deployment.mail.QueuedEmailBackend"

# Socket timeout for each SMTP operation, in seconds. Unset, smtplib inherits Python's
# global default of None and a black-holed connection hangs forever -- which, now that
# the send happens on the worker, would stall every other queued task behind it until
# the watchdog killed the process. Ten seconds absorbs a slow TLS handshake without
# failing legitimate sends, and stays far inside WORKER_MAX_TASK_SECONDS.
EMAIL_TIMEOUT_SECONDS: int = 10

# Database-backed cache for production. LOCATION is a table name, not created by
# migration: `createcachetable` makes it, idempotently, as part of the
# downstream's deploy sequence.
#
# MAX_ENTRIES is sized for the cache's only production consumer, allauth's rate
# limiting. DatabaseCache culls by deleting expired rows and then a third of what
# remains ordered by cache_key -- blind to age or importance -- so a limit near the
# working set lets a password spray evict the login_failed counters that are
# tracking it. The entries are short-lived (60s to 5m windows), so expiry does most
# of the work and this is headroom rather than a working size.
DATABASE_CACHES: dict[str, dict[str, object]] = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache_table",
        "OPTIONS": {"MAX_ENTRIES": 50000},
    }
}


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


def require_webhook_encryption_salt() -> str:
    """Return WEBHOOK_ENCRYPTION_SALT from the environment, raising
    ImproperlyConfigured if unset/empty/whitespace-only.

    In production the dev fallback (a hardcoded deterministic salt in
    settings_base.py) silently weakens webhook-secret Fernet encryption, so this
    fails fast at settings-import time instead of shipping the insecure salt.
    """
    salt = os.environ.get("WEBHOOK_ENCRYPTION_SALT", "").strip()
    if not salt:
        raise ImproperlyConfigured(
            "WEBHOOK_ENCRYPTION_SALT must be set to a non-empty value in production."
        )
    return salt


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
    logger — container-friendly, no on-disk state, and the mode production uses,
    relying on the container log driver to cap and rotate what it collects.

    When log_dir is supplied: additionally writes rotating file handlers under
    log_dir, for a deployment that wants logs on disk regardless of what its
    container log driver does.
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
