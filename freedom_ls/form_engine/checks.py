"""Django system checks for the form_engine app.

Check IDs follow Django's convention: ``app_label.severity + number``.
W = Warning. Checks run automatically on runserver, migrate, test, and
``manage.py check``.

W001 — FILE_SCAN_BACKEND is still the shipped no-op scanner while DEBUG is False.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Tags, Warning, register

from .config import FormEngineConfig, config


@register(Tags.security)
def check_file_scan_backend_configured(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Warning]:
    """W001: warn when production is running the inert scanner."""
    if settings.DEBUG:
        return []

    default = FormEngineConfig.declared_settings["FILE_SCAN_BACKEND"].default
    if default != config.FILE_SCAN_BACKEND:
        return []

    return [
        Warning(
            "FILE_SCAN_BACKEND is the shipped no-op scanner with DEBUG=False; "
            "uploaded files stay pending until a superuser marks them by hand.",
            hint="Point FILE_SCAN_BACKEND at a scanner for this environment.",
            id="freedom_ls_form_engine.W001",
        )
    ]
