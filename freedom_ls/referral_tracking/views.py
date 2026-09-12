"""The redirect view behind `/go/{code}` and `/d/{CODE}`.

`require_safe` is the view-level guarantee that only GET and HEAD are served,
but an unsafe method never reaches it: `CsrfViewMiddleware` runs first and
answers a token-less POST 403, so that, not the decorator's 405, is what a
caller sees.
"""

from __future__ import annotations

from django.contrib.sites.models import Site
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_safe

from freedom_ls.referral_tracking.capture import suppress_capture
from freedom_ls.referral_tracking.codes import build_redirect_url, lookup_referral_code
from freedom_ls.referral_tracking.hits import record_hit
from freedom_ls.referral_tracking.models import Door
from freedom_ls.site_aware_models.models import get_cached_site


@require_safe
def follow_referral_code(request: HttpRequest, code: str, door: Door) -> HttpResponse:
    suppress_capture(request)
    site = get_cached_site(request)
    if not isinstance(site, Site):
        # A rejected Host resolves to UnknownSite, which is not a row and
        # cannot be looked up against.
        raise Http404
    referral_code = lookup_referral_code(site, code)
    if referral_code is None:
        raise Http404
    if request.method == "GET":
        record_hit(referral_code, door, request)
    query_string = request.META.get("QUERY_STRING", "")
    target = build_redirect_url(referral_code, query_string)
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = build_redirect_url(referral_code, query_string, base="/")
    response = HttpResponseRedirect(target)
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex"
    return response
