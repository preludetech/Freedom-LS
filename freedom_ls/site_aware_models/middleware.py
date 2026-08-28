from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse

from freedom_ls.site_aware_models.models import _thread_locals


class CurrentSiteMiddleware:
    """Publish the request on a thread local for the duration of the request.

    `SiteAwareManager` and `SiteAwareModelBase.save` read the site from this
    thread local, so whatever it holds decides which rows a query sees. It is
    saved and restored rather than deleted: a re-entrant call must hand the
    outer request back, and a view that raises must not leave its request
    behind for the next request the thread serves.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse | StreamingHttpResponse],
    ) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
        had_request = hasattr(_thread_locals, "request")
        previous = getattr(_thread_locals, "request", None)
        _thread_locals.request = request
        try:
            return self.get_response(request)
        finally:
            if had_request:
                _thread_locals.request = previous
            else:
                delattr(_thread_locals, "request")
