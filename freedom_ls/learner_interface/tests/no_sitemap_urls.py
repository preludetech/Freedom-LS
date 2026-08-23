"""Minimal URLconf with no 'sitemap' name, for the W001 check's silent case."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import path


def _home(request: HttpRequest) -> HttpResponse:
    return HttpResponse()


urlpatterns = [
    path("", _home, name="home"),
]
