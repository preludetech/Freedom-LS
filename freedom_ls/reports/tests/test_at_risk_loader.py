"""Tests for the at-risk rule registry loader."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.reports.at_risk.loader import get_at_risk_rules
from freedom_ls.reports.at_risk.rules import BASE_AT_RISK_RULES


class TestGetAtRiskRules:
    def test_default_setting_resolves_to_base_rules(self) -> None:
        get_at_risk_rules.cache_clear()
        rules = get_at_risk_rules()
        get_at_risk_rules.cache_clear()

        assert rules == BASE_AT_RISK_RULES

    def test_override_module_exporting_at_risk_rules_extends_base_rules(self) -> None:
        get_at_risk_rules.cache_clear()
        with override_settings(
            REPORTS_AT_RISK_RULES_MODULE="freedom_ls.reports.tests.at_risk_rules_fixture",
        ):
            rules = get_at_risk_rules()
        get_at_risk_rules.cache_clear()

        assert [rule.id for rule in rules] == [
            *(rule.id for rule in BASE_AT_RISK_RULES),
            "fixture_extra",
        ]

    def test_module_missing_both_export_names_raises_import_error(self) -> None:
        get_at_risk_rules.cache_clear()
        with (
            override_settings(REPORTS_AT_RISK_RULES_MODULE="freedom_ls.reports.config"),
            pytest.raises(ImportError),
        ):
            get_at_risk_rules()
        get_at_risk_rules.cache_clear()
