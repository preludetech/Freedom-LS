from __future__ import annotations

import hmac
from datetime import datetime

from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from freedom_ls.site_aware_models.models import SiteResolutionError, get_cached_site

from .models import KEY_TEXT_PREFIX, ApiKey, hash_key

AUTH_FAILED_MESSAGE = "Invalid API key."
# A hash no key can match: the hash and compare run for an unknown prefix
# too, so that step costs the same either way (the row fetch does not).
_NO_MATCH_HASH = hash_key("")


def host_site(request: HttpRequest) -> Site | None:
    """The host's Site, or None when the host resolves to no row.

    Both failure shapes of site resolution end here: a rejected or unknown host
    (UnknownSite, Site.DoesNotExist) and a process with no request to resolve
    from (SiteResolutionError).
    """
    try:
        site = get_cached_site(request)
    except (Site.DoesNotExist, SiteResolutionError):
        return None
    return site if isinstance(site, Site) else None


class ApiKeyAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[None, ApiKey] | None:
        header: str = request.META.get("HTTP_AUTHORIZATION", "")
        if not header:
            return None
        prefix, key_text = self._parse(header)
        # The Django request, not DRF's wrapper: the site cache lives on the
        # HttpRequest and the site-aware manager reads the same object.
        site = host_site(request._request)
        if site is None:
            raise AuthenticationFailed(AUTH_FAILED_MESSAGE)
        now = timezone.now()
        api_key = self._match(prefix, key_text, site, now)
        return (None, api_key)

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="api"'

    def _parse(self, header: str) -> tuple[str, str]:
        """The prefix and the key text of a well-formed `Bearer flsk_<prefix>.<secret>`."""
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed(AUTH_FAILED_MESSAGE)
        key_text = parts[1]
        prefix, dot, _secret = key_text.removeprefix(KEY_TEXT_PREFIX).partition(".")
        if not key_text.startswith(KEY_TEXT_PREFIX) or not dot:
            raise AuthenticationFailed(AUTH_FAILED_MESSAGE)
        return prefix, key_text

    def _match(self, prefix: str, key_text: str, site: Site, now: datetime) -> ApiKey:
        # The base manager: the default one filters on the host, and the
        # site match below is the explicit check this code is accountable for.
        api_key = ApiKey._base_manager.filter(key_prefix=prefix, site=site).first()
        expected = api_key.key_hash if api_key is not None else _NO_MATCH_HASH
        matched = hmac.compare_digest(hash_key(key_text), expected)
        if api_key is None or not matched or not api_key.is_active(now):
            raise AuthenticationFailed(AUTH_FAILED_MESSAGE)
        return api_key
