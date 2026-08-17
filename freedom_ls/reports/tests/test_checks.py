"""Tests for the reports app's Django system checks."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.reports.checks import (
    check_report_font_faces_resolvable,
    check_reports_storage_alias_configured,
    check_required_reports_settings,
    check_tailwind_bundle_resolvable,
)


class TestRequiredSettingsCheck:
    def test_no_required_settings_produces_no_errors(self) -> None:
        # None of the settings this app declares are required=True.
        errors = check_required_reports_settings()

        assert errors == []


class TestReportsStorageAliasCheck:
    def test_fires_when_storage_alias_missing_from_storages(self) -> None:
        with override_settings(
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                },
            },
        ):
            warnings = check_reports_storage_alias_configured()

        assert len(warnings) == 1
        assert warnings[0].id == "freedom_ls_reports.W001"
        assert "REPORTS_STORAGE_ALIAS" in warnings[0].msg

    def test_silent_when_storage_alias_present(self) -> None:
        with override_settings(
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                },
                "reports": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            },
        ):
            warnings = check_reports_storage_alias_configured()

        assert warnings == []


class TestTailwindBundleCheck:
    def test_fires_when_bundle_not_resolvable(self, mocker) -> None:
        mocker.patch("freedom_ls.reports.checks.finders.find", return_value=None)

        warnings = check_tailwind_bundle_resolvable()

        assert len(warnings) == 1
        assert warnings[0].id == "freedom_ls_reports.W002"
        hint = warnings[0].hint
        assert hint is not None
        assert "tailwind_build" in hint

    def test_silent_when_bundle_resolvable(self, mocker) -> None:
        mocker.patch(
            "freedom_ls.reports.checks.finders.find",
            return_value="/some/path/vendor/tailwind.output.css",
        )

        warnings = check_tailwind_bundle_resolvable()

        assert warnings == []


class TestReportFontFacesCheck:
    def test_fires_once_per_unresolvable_face(self) -> None:
        with override_settings(
            REPORTS_FONT_FACES=[
                {
                    "family": "Nowhere",
                    "weight": "400",
                    "style": "normal",
                    "static_path": "reports/fonts/does-not-exist.ttf",
                },
                {
                    "family": "Nameless",
                    "weight": "400",
                    "style": "normal",
                    "static_path": "",
                },
            ]
        ):
            warnings = check_report_font_faces_resolvable()

        assert len(warnings) == 2
        assert {warning.id for warning in warnings} == {"freedom_ls_reports.W004"}
        assert "does-not-exist.ttf" in warnings[0].msg

    def test_silent_for_the_shipped_faces(self) -> None:
        # No override: the faces this app ships must all resolve, or a fresh
        # install would warn out of the box.
        warnings = check_report_font_faces_resolvable()

        assert warnings == []
