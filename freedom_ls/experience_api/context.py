"""Request-scoped context helpers — no DB writes, no thread-local reads.

These are pure functions used by :mod:`freedom_ls.experience_api.tracking`.
They take the request (which the tracker has already resolved from
``_thread_locals`` or from an explicit argument) and return primitives
suitable for the ``Event`` row.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.site_aware_models.models import get_cached_site


def get_current_site_and_domain(
    request: HttpRequest | None,
) -> tuple[Site | RequestSite | None, str | None]:
    """Resolve the current site and its domain snapshot from a request.

    When no request is available (async task context, system call path) both
    components are ``None`` and the caller may pass them straight through.
    """
    if request is None:
        return None, None
    site = get_cached_site(request)
    domain = getattr(site, "domain", None)
    return site, domain


def hash_session_key(session_key: str | None) -> str | None:
    """SHA-256 of ``SECRET_KEY + session_key``, lower-case hex, 64 chars.

    Salting with ``SECRET_KEY`` makes the hash non-correlatable across
    installs; rotating the secret therefore rotates every hash (acceptable —
    session_id_hash is a correlation aid, not a stable identifier).

    Non-string input returns ``None`` — this guards against mocked request
    objects in tests, and against sessions that never populated a key.
    """
    if not session_key or not isinstance(session_key, str):
        return None
    salted = (settings.SECRET_KEY + session_key).encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def get_ip_address(request: HttpRequest | None) -> str | None:
    """Return the request IP when capture is enabled, else ``None``.

    ``EXPERIENCE_API_CAPTURE_IP`` gates capture globally. The tracker does
    **not** parse ``X-Forwarded-For`` — that needs a per-deployment trusted-
    proxy configuration and is out of scope for the initial implementation.

    TODO: add an opt-in ``EXPERIENCE_API_TRUSTED_PROXIES`` setting and
    parse ``X-Forwarded-For`` accordingly so deployments behind a known
    reverse proxy can record the originating client IP.
    """
    if not getattr(settings, "EXPERIENCE_API_CAPTURE_IP", False):
        return None
    if request is None:
        return None
    meta = getattr(request, "META", None)
    if not isinstance(meta, dict):
        return None
    ip = meta.get("REMOTE_ADDR")
    return ip if isinstance(ip, str) and ip else None


def get_user_agent(request: HttpRequest | None) -> str | None:
    """Snapshot the ``User-Agent`` header, truncating to the DB field limit."""
    if request is None:
        return None
    meta = getattr(request, "META", None)
    if not isinstance(meta, dict):
        return None
    ua = meta.get("HTTP_USER_AGENT")
    if not ua or not isinstance(ua, str):
        return None
    # Truncate to the Event.user_agent column length (1024).
    truncated: str = ua[:1024]
    return truncated


def _site_homepage(site: Site | RequestSite | None) -> str:
    """Return a stable homepage URL for use as the IFI ``homePage``.

    For a ``Site`` instance we use ``"https://<domain>"``; for a
    ``RequestSite`` fallback we use the domain string directly. An empty
    site yields an empty homepage — the wrapper / tracker will either
    supply ``actor=None`` or the caller has a bug.
    """
    if site is None:
        return ""
    domain = getattr(site, "domain", "") or ""
    if not domain:
        return ""
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain
    return f"https://{domain}"


def build_actor_ifi(user: User | None, site: Site | RequestSite | None) -> str:
    """Build the xAPI Inverse-Functional Identifier for ``user`` / ``site``.

    Shape: ``"<site_homepage>|<user.id>"``. Never email. The empty string is
    a sentinel used when ``user`` is ``None`` (system-generated events).
    """
    if user is None:
        return ""
    return f"{_site_homepage(site)}|{user.id}"
