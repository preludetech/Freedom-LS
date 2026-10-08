"""Root URL configuration for the RemoveSlashMiddleware tests.

Standalone, like `error_pages_urls.py`, so these tests reach no other app's
routes and the module imports in a downstream install with no `config`.

`handler404` answers with a bare response: the tests read the status and the
`Location` header, and rendering the site's 404 page would drag the site
context and the database into tests about URL routing.
"""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotFound
from django.urls import path


def _ok(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


def _not_found(request: HttpRequest) -> HttpResponse:
    raise Http404


def _bare_404(request: HttpRequest, exception: Exception) -> HttpResponse:
    return HttpResponseNotFound("not found")


handler404 = _bare_404

urlpatterns = [
    path("", _ok, name="root"),
    path("plain", _ok, name="plain"),
    path("slashed/", _ok, name="slashed"),
    path("missing/", _not_found, name="missing"),
]
