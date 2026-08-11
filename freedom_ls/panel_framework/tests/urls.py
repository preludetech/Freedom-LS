"""Test-only URL configuration for panel_framework tests."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import re_path

from freedom_ls.panel_framework.views import panel_framework_view

from .stub_panels import StubListConfig

app_name = "panel_framework_test"


def _stub_view(request: HttpRequest, path_string: str = "") -> HttpResponse:
    return HttpResponse("ok")


def _framework_view(request: HttpRequest, path_string: str = "") -> HttpResponse:
    return panel_framework_view(
        config={"stubs": StubListConfig},
        request=request,
        path_string=path_string,
        template_name="panel_framework/test_interface.html",
        url_name="panel_framework_test:framework",
    )


urlpatterns = [
    re_path(r"^framework/(?P<path_string>.*)$", _framework_view, name="framework"),
    # Exists only so tests can prove request.panel_url_kwargs reaches reverse()
    # calls: a second, generic kwarg alongside path_string. Not hit by any
    # dispatch in these tests, only reversed.
    re_path(
        r"^scoped/(?P<extra>[\w-]+)/(?P<path_string>.*)$",
        _stub_view,
        name="scoped_interface",
    ),
    re_path(r"^(?P<path_string>.*)$", _stub_view, name="interface"),
]
