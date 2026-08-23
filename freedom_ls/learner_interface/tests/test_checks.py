"""Tests for the learner_interface Django system check."""

from __future__ import annotations

from django.apps import apps
from django.conf import settings
from django.test import override_settings

from freedom_ls.tests.app_guards import app_not_installed

INSTALLED_APPS_WITHOUT_SITEMAPS = [
    app for app in settings.INSTALLED_APPS if app != "django.contrib.sitemaps"
]


class TestSitemapsAppInstalledCheck:
    """W001: warn when a 'sitemap' URL is wired without django.contrib.sitemaps."""

    @override_settings(INSTALLED_APPS=INSTALLED_APPS_WITHOUT_SITEMAPS)
    def test_fires_when_sitemap_url_wired_and_sitemaps_not_installed(self):
        from freedom_ls.learner_interface.checks import check_sitemaps_app_installed

        warnings = check_sitemaps_app_installed(app_configs=None)

        assert len(warnings) == 1
        assert warnings[0].id == "freedom_ls_learner_interface.W001"

    def test_silent_for_reference_config(self):
        from freedom_ls.learner_interface.checks import check_sitemaps_app_installed

        warnings = check_sitemaps_app_installed(app_configs=None)

        assert warnings == []

    @override_settings(
        INSTALLED_APPS=INSTALLED_APPS_WITHOUT_SITEMAPS,
        ROOT_URLCONF="freedom_ls.learner_interface.tests.no_sitemap_urls",
    )
    def test_silent_when_no_sitemap_url_is_wired(self):
        from freedom_ls.learner_interface.checks import check_sitemaps_app_installed

        warnings = check_sitemaps_app_installed(app_configs=None)

        assert warnings == []

    @override_settings(
        INSTALLED_APPS=INSTALLED_APPS_WITHOUT_SITEMAPS,
        ROOT_URLCONF=None,
    )
    def test_silent_when_root_urlconf_is_none(self):
        from freedom_ls.learner_interface.checks import check_sitemaps_app_installed

        warnings = check_sitemaps_app_installed(app_configs=None)

        assert warnings == []

    @override_settings(
        INSTALLED_APPS=[
            app
            for app in settings.INSTALLED_APPS
            if app != "freedom_ls.learner_interface"
        ]
    )
    def test_silent_when_learner_interface_not_installed(self):
        from freedom_ls.learner_interface.checks import check_sitemaps_app_installed

        assert app_not_installed("freedom_ls.learner_interface")

        warnings = check_sitemaps_app_installed(app_configs=None)

        assert warnings == []

    @override_settings(INSTALLED_APPS=INSTALLED_APPS_WITHOUT_SITEMAPS)
    def test_silent_when_app_configs_excludes_learner_interface(self):
        from freedom_ls.learner_interface.checks import check_sitemaps_app_installed

        unrelated_app_config = apps.get_app_config("freedom_ls_content_engine")
        warnings = check_sitemaps_app_installed(app_configs=[unrelated_app_config])

        assert warnings == []
