"""The middleware that mints the attribution cookie and tallies first touches."""

from __future__ import annotations

from collections.abc import Callable

from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils import timezone
from django.utils.cache import patch_cache_control, patch_vary_headers

from freedom_ls.referral_tracking.capture import (
    first_touch_from_request,
    has_tracked_params,
    is_capture_suppressed,
    read_attribution_cookie,
    set_attribution_cookie,
)
from freedom_ls.referral_tracking.counters import (
    attribution_key_hash,
    increment_first_touch,
)
from freedom_ls.referral_tracking.models import ATTRIBUTION_KEY_FIELDS
from freedom_ls.site_aware_models.models import get_cached_site


class AttributionCaptureMiddleware:
    """Mint the first-party attribution cookie on a visitor's first tracked landing.

    The first touch is read off the request before the view runs, so nothing
    the view does can change what gets recorded; the cookie and the tally are
    only written once the view has returned successfully, so a view that
    raises leaves neither behind. A request that carries no tracked parameter
    does no work at all.

    Every response to a tracked landing carries `Vary: Cookie`, not only the
    minting one: a shared cache that stored the response served to a visitor
    who already held the cookie would replay it, with no `Set-Cookie`, to the
    next visitor who did not.

    The `/go/` and `/d/` referral redirect views opt out by name, calling
    `suppress_capture()` before doing anything else, so following a code
    itself never mints a cookie or tallies a first touch.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        if request.method != "GET" or not has_tracked_params(request):
            return self.get_response(request)
        site = self._site_to_mint_for(request)
        first_touch = first_touch_from_request(request) if site else None
        response = self.get_response(request)
        if is_capture_suppressed(request):
            return response
        patch_vary_headers(response, ["Cookie"])
        if site is None or first_touch is None:
            return response
        patch_cache_control(response, private=True, no_store=True)
        if not set_attribution_cookie(response, first_touch):
            # Nothing the browser can keep, so the next landing would mint
            # again; counting this one would count that visitor twice.
            return response
        key_fields = {name: first_touch[name] for name in ATTRIBUTION_KEY_FIELDS}
        increment_first_touch(
            site=site,
            day=timezone.localdate(),
            key_hash=attribution_key_hash(
                *(key_fields[name] for name in ATTRIBUTION_KEY_FIELDS)
            ),
            is_overflow=False,
            **key_fields,
        )
        return response

    @staticmethod
    def _site_to_mint_for(request: HttpRequest) -> Site | None:
        """The site to tally a mint against, or None when this landing mints nothing."""
        if read_attribution_cookie(request) is not None:
            return None
        site = get_cached_site(request)
        if not isinstance(site, Site):
            # A rejected Host resolves to UnknownSite, which is not a row, so
            # there is nothing to key a tally against.
            return None
        return site
