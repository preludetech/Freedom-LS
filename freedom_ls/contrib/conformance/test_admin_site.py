"""Probe: the admin registry survives an app-registry repopulation.

Django rebuilds the app registry -- running every ``AppConfig.ready()`` again
-- whenever ``INSTALLED_APPS`` changes, which any test using
``override_settings(INSTALLED_APPS=...)`` does. A config whose ``ready()``
replaces ``django.contrib.admin.site`` loses every registration at that point
and never gets them back, because the ``autodiscover()`` that follows re-imports
nothing: each app's ``admin`` module is already in ``sys.modules``.

The damage is silent and permanent for the process. ``config/urls.py`` binds
``admin.site.urls`` at import, so an empty registry means every
``admin:<app_label>_<model>_<view>`` name stops reversing -- surfacing as
``NoReverseMatch`` in whichever admin tests happen to run afterwards.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.test import override_settings

__all__ = ["test_admin_registry_survives_installed_apps_override"]


def test_admin_registry_survives_installed_apps_override() -> None:
    registered = len(admin.site._registry)
    assert registered, "no ModelAdmins registered -- the probe would prove nothing"

    with override_settings(INSTALLED_APPS=list(settings.INSTALLED_APPS)):
        during = len(admin.site._registry)

    assert during == registered, (
        "Repopulating the app registry dropped the admin registry from "
        f"{registered} models to {during}. An installed AppConfig is rebinding "
        "django.contrib.admin.site in its ready(). django-unfold's default "
        'config does this: install "unfold.apps.BasicAppConfig" instead, and '
        "name unfold.sites.UnfoldAdminSite as default_site on a "
        "django.contrib.admin AppConfig subclass."
    )
    assert len(admin.site._registry) == registered, (
        "The admin registry did not come back when the override was unwound."
    )
