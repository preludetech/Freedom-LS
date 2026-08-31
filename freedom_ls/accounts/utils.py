"""Shared helpers for the accounts app."""

from __future__ import annotations

import ipaddress

from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from freedom_ls.site_aware_models.models import get_cached_site

from .config import config
from .models import SiteSignupPolicy


def get_client_ip(request: HttpRequest) -> str:
    """Return the client IP address: the configured header's value, or REMOTE_ADDR.

    When `config.TRUSTED_PROXY_IP_HEADER` names a header (e.g. "X-Real-IP"), that
    header is the only source: its value is returned whole, never split, because
    the leftmost entry of an appended header is whatever the visitor typed. The
    header must be one the edge *sets* rather than appends, so it carries exactly
    one address. A missing header or a value that is not a single valid address
    means the edge is misconfigured or was bypassed, so the request is refused
    rather than credited with a fallback address that every other visitor behind
    the same misconfigured edge would also get. REMOTE_ADDR is used only when no
    header is configured at all, which is what keeps this correct on a deployment
    with no proxy in front.

    The return value goes into GenericIPAddressField columns without a
    full_clean, so an unparseable value would reach Postgres as an inet and
    take the whole request down with it.

    This is the only sanctioned way to derive a client IP for LegalConsent
    records, django-axes lockouts and similar evidence trails.

    Raises:
        PermissionDenied: the configured header is absent or its value is not a
            single valid IP address. The message names the header, never the
            rejected value, since that value is attacker-controlled and would
            otherwise be written into logs.
    """
    header_name: str | None = config.TRUSTED_PROXY_IP_HEADER

    if header_name:
        value = str(request.headers.get(header_name, ""))
        if not _is_ip_address(value):
            raise PermissionDenied(
                f"Client IP header {header_name!r} is missing or malformed."
            )
        return value

    return str(request.META.get("REMOTE_ADDR", "") or "")


def _is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def get_signup_policy_for_request(
    request: HttpRequest | None,
) -> SiteSignupPolicy | None:
    """Return the `SiteSignupPolicy` for the request's current site, or `None`."""
    if request is None:
        return None

    site = get_cached_site(request)
    if not isinstance(site, Site):
        return None

    # _base_manager, not the site-aware `objects`: site is already resolved from
    # this request, and the site-aware manager would AND a second site read from
    # the ambient thread-local request. A mismatch there returns None rather than
    # erroring, which drops the signup form back to the global defaults.
    try:
        policy: SiteSignupPolicy = SiteSignupPolicy._base_manager.get(site=site)
    except SiteSignupPolicy.DoesNotExist:
        return None
    return policy


def get_effective_require_name(policy: SiteSignupPolicy | None) -> bool:
    if policy is not None:
        return policy.require_name
    return bool(config.REQUIRE_NAME)


def get_effective_require_terms_acceptance(policy: SiteSignupPolicy | None) -> bool:
    if policy is not None:
        return policy.require_terms_acceptance
    return bool(config.REQUIRE_TERMS_ACCEPTANCE)


def get_effective_additional_registration_forms(
    policy: SiteSignupPolicy | None,
) -> list[str]:
    if policy is not None:
        return list(policy.additional_registration_forms)
    return list(config.ADDITIONAL_REGISTRATION_FORMS)
