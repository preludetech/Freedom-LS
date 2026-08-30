"""The admin app config FLS installs in place of ``django.contrib.admin``.

django-unfold's own ``DefaultAppConfig.ready()`` builds a fresh, empty
``UnfoldAdminSite`` and rebinds ``django.contrib.admin.site`` to it. Django
re-runs every ``ready()`` whenever the app registry is repopulated -- which
``override_settings(INSTALLED_APPS=...)`` does -- and the ``autodiscover()``
that follows re-registers nothing, because each app's ``admin`` module is
already imported. The admin registry is then empty for the rest of the
process, and every ``admin:<app_label>_<model>_<view>`` URL stops reversing.

Naming the site here instead hands it to ``django.contrib.admin.sites.site``,
a lazy object Django instantiates once and never rebuilds. Pair this with
``unfold.apps.BasicAppConfig`` in ``INSTALLED_APPS`` so unfold no longer
rebinds the site itself.
"""

from __future__ import annotations

from django.contrib.admin.apps import AdminConfig


class FreedomLSAdminConfig(AdminConfig):
    default_site = "unfold.sites.UnfoldAdminSite"
