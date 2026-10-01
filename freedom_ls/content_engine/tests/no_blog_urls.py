"""Minimal URLconf with no 'blog' namespace, standing in for a project that did not install the blog."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import path


def _home(request: HttpRequest) -> HttpResponse:
    return HttpResponse()


urlpatterns = [
    path("", _home, name="home"),
]
