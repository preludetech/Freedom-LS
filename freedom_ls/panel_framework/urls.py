"""URLs for the panel_framework app itself.

Only the component reference page lives here today. `config/urls.py`
includes it under `if settings.DEBUG:`, since it exists for developers
building against the kit, not for end users.
"""

from __future__ import annotations

from django.urls import path

from freedom_ls.panel_framework.reference import component_reference

app_name = "panel_framework"

urlpatterns = [
    path("components/", component_reference, name="component_reference"),
]
