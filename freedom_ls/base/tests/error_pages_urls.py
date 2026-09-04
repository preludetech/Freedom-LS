"""Root URL configuration for error-page tests.

Adds two routes that raise the exceptions Django's default handlers watch
for, splatted in front of `config.urls.urlpatterns` (rather than used
standalone) so `{% url %}` inside `403.html`/`400.html` still reverses every
named route those pages need. Mirrors `freedom_ls/health/tests/root_urls.py`
and `freedom_ls/panel_framework/tests/root_urls.py`.
"""

from __future__ import annotations

from django.core.exceptions import BadRequest, PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.urls import path

from config.urls import urlpatterns as _base_urlpatterns


def _raise_permission_denied(request: HttpRequest) -> HttpResponse:
    raise PermissionDenied


def _raise_bad_request(request: HttpRequest) -> HttpResponse:
    raise BadRequest


urlpatterns = [
    path("test-403/", _raise_permission_denied, name="test_403"),
    path("test-400/", _raise_bad_request, name="test_400"),
    *_base_urlpatterns,
]
