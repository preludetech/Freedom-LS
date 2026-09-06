"""Root URL configuration for error-page tests.

Adds routes that raise the exceptions Django's default handlers watch for,
alongside the app urlconfs those pages reverse against. Standalone, the way
`freedom_ls/health/tests/root_urls.py` and
`freedom_ls/panel_framework/tests/root_urls.py` are: this module ships in the
`freedom_ls` package, so importing the demo project's `config.urls` would kill
collection in a downstream install that has no `config` module.

Every route the error pages and the header bar `_base.html` renders reverse has
to be reachable from here. `{% url ... as var %}` fails silently, so a missing
one shows up as a button that never renders --
`test_every_page_offers_a_route_forward` is what catches that.
"""

from __future__ import annotations

from django.contrib import admin
from django.core.exceptions import BadRequest, PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.urls import include, path


def _raise_permission_denied(request: HttpRequest) -> HttpResponse:
    raise PermissionDenied


def _raise_bad_request(request: HttpRequest) -> HttpResponse:
    raise BadRequest


def _raise_server_error(request: HttpRequest) -> HttpResponse:
    raise RuntimeError("deliberate failure for the 500.html contract test")


urlpatterns = [
    path("test-403/", _raise_permission_denied, name="test_403"),
    path("test-400/", _raise_bad_request, name="test_400"),
    path("test-500/", _raise_server_error, name="test_500"),
    # admin:index is only reversed behind {% if user.is_staff %}, so no test
    # needs it yet; it is here so one with a staff user would not 500.
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("freedom_ls.accounts.urls")),
    path("educator/", include("freedom_ls.educator_interface.urls")),
    path("", include("freedom_ls.learner_interface.urls")),
]
