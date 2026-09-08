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
    raises leaves neither behind. A request that already carries a valid
    cookie, or carries no tracked parameter, does no work at all.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        if (
            request.method != "GET"
            or not has_tracked_params(request)
            or read_attribution_cookie(request) is not None
        ):
            return self.get_response(request)
        site = get_cached_site(request)
        if not isinstance(site, Site):
            # A rejected Host resolves to UnknownSite, which is not a row, so
            # there is nothing to key a tally against.
            return self.get_response(request)
        first_touch = first_touch_from_request(request)
        response = self.get_response(request)
        set_attribution_cookie(response, first_touch)
        patch_vary_headers(response, ["Cookie"])
        patch_cache_control(response, private=True, no_store=True)
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
