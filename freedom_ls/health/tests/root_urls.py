"""Root URL configuration for health endpoint tests.

Wraps freedom_ls.health.urls behind include() (rather than using it directly
as ROOT_URLCONF) so its app_name is registered as a namespace — Django only
turns app_name into a namespace for an included urlconf, not for the urlconf
module set directly as ROOT_URLCONF. Mirrors the panel_framework tests'
root_urls.py wrapper.
"""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("health/", include("freedom_ls.health.urls")),
]
