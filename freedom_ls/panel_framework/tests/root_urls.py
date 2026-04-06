"""Root URL configuration for panel_framework tests."""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("test-panel/", include("freedom_ls.panel_framework.tests.urls")),
]
