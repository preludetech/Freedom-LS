"""Tests for the reports app's Django system checks."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.reports.at_risk.loader import get_at_risk_rules
from freedom_ls.reports.checks import (
    check_at_risk_rules_module_configured,
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


class TestAtRiskRulesModuleCheck:
    def test_fires_when_module_cannot_be_imported(self) -> None:
        get_at_risk_rules.cache_clear()
        with override_settings(REPORTS_AT_RISK_RULES_MODULE="does.not.exist"):
            warnings = check_at_risk_rules_module_configured()
        get_at_risk_rules.cache_clear()

        assert len(warnings) == 1
        assert warnings[0].id == "freedom_ls_reports.W003"

    def test_fires_when_module_exports_neither_rules_name(self) -> None:
        get_at_risk_rules.cache_clear()
        with override_settings(
            REPORTS_AT_RISK_RULES_MODULE="freedom_ls.reports.config"
        ):
            warnings = check_at_risk_rules_module_configured()
        get_at_risk_rules.cache_clear()

        assert len(warnings) == 1
        assert warnings[0].id == "freedom_ls_reports.W003"

    def test_silent_when_module_resolves_to_a_rule_list(self) -> None:
        get_at_risk_rules.cache_clear()
        warnings = check_at_risk_rules_module_configured()
        get_at_risk_rules.cache_clear()

        assert warnings == []
