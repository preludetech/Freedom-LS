"""Django system checks for the learner_interface app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error, W = Warning. Checks run automatically on runserver, migrate, test,
and ``manage.py check``.

W001 — A 'sitemap' URL is wired but django.contrib.sitemaps is not installed.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Warning, register


@register()
def check_sitemaps_app_installed(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """W001: warn when a 'sitemap' URL is wired without django.contrib.sitemaps."""
    from django.apps import apps
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured
    from django.urls import NoReverseMatch, reverse

    if not apps.is_installed("freedom_ls.learner_interface"):
        return []
    if app_configs is not None and not any(
        c.label == "freedom_ls_learner_interface" for c in app_configs
    ):
        return []
    if apps.is_installed("django.contrib.sitemaps"):
        return []
    if not getattr(settings, "ROOT_URLCONF", None):
        return []
    try:
        reverse("sitemap")
    except (NoReverseMatch, ImproperlyConfigured):
        return []
    return [
        Warning(
            "A 'sitemap' URL is wired but 'django.contrib.sitemaps' is not in INSTALLED_APPS.",
            hint="Add 'django.contrib.sitemaps' to INSTALLED_APPS, or remove the sitemap URL.",
            id="freedom_ls_learner_interface.W001",
        )
    ]
