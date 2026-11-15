"""The middleware that mints the attribution cookie, tallies first touches and records signed-in landings."""

from __future__ import annotations

from collections.abc import Callable

from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils import timezone
from django.utils.cache import patch_cache_control, patch_vary_headers

from freedom_ls.referral_tracking.capture import (
    append_touch,
    first_touch_from_request,
    has_tracked_params,
    is_capture_suppressed,
    is_cookie_clear_requested,
    read_attribution_cookie,
    read_cookie_touches,
    set_attribution_cookie,
    suppress_capture,
)
from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.conversions import record_live_touch
from freedom_ls.referral_tracking.counters import (
    attribution_key_hash_of,
    increment_first_touch,
)
from freedom_ls.referral_tracking.models import ATTRIBUTION_KEY_FIELDS
from freedom_ls.referral_tracking.views import follow_referral_code
from freedom_ls.site_aware_models.models import get_cached_site

_LANDING_ATTR = "_attribution_landing"


class AttributionCaptureMiddleware:
    """Record tracked landings: a cookie for anonymous visitors, a row for signed-in users.

    An anonymous visitor's first tracked landing mints the first-party
    attribution cookie and tallies the first touch; a later landing with a
    different attribution key is appended to the cookie's bounded touch list,
    with no tally and no query. A signed-in user's tracked
    landing writes an `AttributionTouch` row instead and never touches the
    cookie or the tally, so a later login cannot record the same landing twice.

    The landing and its time are read off the request before the view runs, so
    nothing the view does can change what gets recorded. A signed-in user's
    touch row is written in `process_view`, once the view is known and before
    it runs, so a conversion the view itself starts sees that touch in play;
    the landing happened, so a view that then raises still leaves the row. The
    cookie and tally are written once the view has returned successfully. A
    view that signs the visitor in has already flushed the cookie, which this
    response deletes, so its landing is written as the account's touch rather
    than added to that cookie. A request that carries no tracked parameter
    does no work at all, and resolves no session.

    Every response to a tracked landing carries `Vary: Cookie`, not only the
    minting one: a shared cache that stored the response served to a visitor
    who already held the cookie would replay it, with no `Set-Cookie`, to the
    next visitor who did not.

    The `/go/` and `/d/` referral redirect views opt out: `process_view`
    suppresses capture for them, so following a code itself never mints a
    cookie, tallies a first touch or writes a touch row.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = self._handle(request)
        if is_cookie_clear_requested(request):
            response.delete_cookie(
                config.REFERRAL_TRACKING_COOKIE_NAME, path="/", samesite="Lax"
            )
        return response

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable[..., HttpResponseBase],
        view_args: tuple[object, ...],
        view_kwargs: dict[str, object],
    ) -> None:
        if view_func is follow_referral_code:
            suppress_capture(request)
            return
        landing: dict[str, str] | None = getattr(request, _LANDING_ATTR, None)
        if landing is not None and request.user.is_authenticated:
            _record_live_touch(request, landing)

    def _handle(self, request: HttpRequest) -> HttpResponseBase:
        if request.method != "GET" or not has_tracked_params(request):
            return self.get_response(request)
        landing = first_touch_from_request(request)
        setattr(request, _LANDING_ATTR, landing)
        # Read before the view, and only for a tracked GET, so an untracked
        # request resolves no session.
        was_signed_in = request.user.is_authenticated
        response = self.get_response(request)
        if is_capture_suppressed(request):
            return response
        patch_vary_headers(response, ["Cookie"])
        if was_signed_in:
            return response
        if request.user.is_authenticated:
            _record_live_touch(request, landing)
            return response
        first_touch = read_attribution_cookie(request)
        if first_touch is not None:
            # A repeat of the latest key appends nothing and leaves the cookie
            # byte-identical. When the new list cannot fit, the browser keeps
            # the cookie it already has.
            touches = append_touch(read_cookie_touches(request), first_touch, landing)
            if touches is not None:
                patch_cache_control(response, private=True, no_store=True)
                set_attribution_cookie(response, first_touch, touches=touches)
            return response
        mint_site = get_cached_site(request)
        if not isinstance(mint_site, Site):
            # A rejected Host resolves to UnknownSite, which is not a row, so
            # there is nothing to key a tally against.
            return response
        patch_cache_control(response, private=True, no_store=True)
        if not set_attribution_cookie(response, landing):
            # Nothing the browser can keep, so the next landing would mint
            # again; counting this one would count that visitor twice.
            return response
        increment_first_touch(
            site=mint_site,
            day=timezone.localdate(),
            key_hash=attribution_key_hash_of(landing),
            is_overflow=False,
            **{name: landing[name] for name in ATTRIBUTION_KEY_FIELDS},
        )
        return response


def _record_live_touch(request: HttpRequest, landing: dict[str, str]) -> None:
    site = get_cached_site(request)
    if isinstance(site, Site) and request.user.is_authenticated:
        record_live_touch(landing=landing, user=request.user, site=site)
