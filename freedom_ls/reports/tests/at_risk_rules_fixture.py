"""Fixture module for the at-risk rules loader tests.

A real importable module, standing in for the kind of module a downstream
project points REPORTS_AT_RISK_RULES_MODULE at: it extends BASE_AT_RISK_RULES
with extra rules and exports the result as AT_RISK_RULES.
"""

from __future__ import annotations

from freedom_ls.reports.at_risk.rules import (
    BASE_AT_RISK_RULES,
    AtRiskRule,
    StudentDetailLike,
)


class _FixtureExtraRule:
    id = "fixture_extra"
    label = "Fixture extra rule"

    def evaluate(self, student: StudentDetailLike) -> str | None:
        return None


class _SeverityFreeRule:
    """A rule as it would have been written before severity existed.

    It declares no `severity`, and it always fires, so a test can see what
    severity its flags are given.
    """

    id = "severity_free"
    label = "Severity-free rule"

    def evaluate(self, student: StudentDetailLike) -> str | None:
        return "This rule always fires."


AT_RISK_RULES: list[AtRiskRule] = [
    *BASE_AT_RISK_RULES,
    _FixtureExtraRule(),
    _SeverityFreeRule(),
]
