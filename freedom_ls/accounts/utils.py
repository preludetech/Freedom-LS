"""Shared helpers for the accounts app."""

from __future__ import annotations

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest

from freedom_ls.site_aware_models.models import get_cached_site

from .models import SiteSignupPolicy


def get_client_ip(request: HttpRequest) -> str:
    """Return the client IP address.

    When `settings.TRUSTED_PROXY_IP_HEADER` is set, reads the leftmost value
    from the named header (e.g. ``"HTTP_X_FORWARDED_FOR"``). Otherwise falls
    back to ``REMOTE_ADDR``. Returns an empty string if neither is available.

    This is the only sanctioned way to derive a client IP for use in
    `LegalConsent` records and similar evidence trails.
    """
    header_name: str | None = getattr(settings, "TRUSTED_PROXY_IP_HEADER", None)

    if header_name:
        raw_value = request.META.get(header_name, "")
        if raw_value:
            # X-Forwarded-For style headers may be comma-separated; take the
            # leftmost (the original client) and strip whitespace.
            leftmost = raw_value.split(",")[0].strip()
            if leftmost:
                return str(leftmost)

    return str(request.META.get("REMOTE_ADDR", "") or "")


def get_signup_policy_for_request(
    request: HttpRequest | None,
) -> SiteSignupPolicy | None:
    """Return the `SiteSignupPolicy` for the request's current site, or `None`."""
    if request is None:
        return None

    site = get_cached_site(request)
    if not isinstance(site, Site):
        return None

    try:
        policy: SiteSignupPolicy = SiteSignupPolicy.objects.get(site=site)
    except SiteSignupPolicy.DoesNotExist:
        return None
    return policy
