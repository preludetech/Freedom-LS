"""Shared helpers for the accounts app."""

from __future__ import annotations

from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme

from freedom_ls.site_aware_models.models import get_cached_site

from .config import config
from .models import SiteSignupPolicy


def is_safe_next_url(request: HttpRequest, candidate: str | None) -> str | None:
    """Return `candidate` if it is a safe same-host redirect target, else None.

    The single open-redirect guard for every `?next=`-style destination in
    this app (post-registration-completion redirect, signup-intent stash,
    signup-intent consume) — re-validate with this at each point of use,
    since a value that was safe when written is not guaranteed to still be
    safe when read back (e.g. from a session).
    """
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return None


def get_client_ip(request: HttpRequest) -> str:
    """Return the client IP address.

    When `config.TRUSTED_PROXY_IP_HEADER` is set, reads the leftmost value
    from the named header (e.g. ``"HTTP_X_FORWARDED_FOR"``). Otherwise falls
    back to ``REMOTE_ADDR``. Returns an empty string if neither is available.

    This is the only sanctioned way to derive a client IP for use in
    `LegalConsent` records and similar evidence trails.
    """
    header_name: str | None = config.TRUSTED_PROXY_IP_HEADER

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
