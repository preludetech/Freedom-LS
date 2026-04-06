"""Test-only URL configuration for panel_framework tests."""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import re_path

app_name = "panel_framework_test"


def _stub_view(request: object, path_string: str = "") -> HttpResponse:
    return HttpResponse("ok")


urlpatterns = [
    re_path(r"^(?P<path_string>.*)$", _stub_view, name="interface"),
]
