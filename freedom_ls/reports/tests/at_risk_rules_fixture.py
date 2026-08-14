"""Fixture module for the at-risk rules loader tests.

A real importable module, standing in for the kind of module a downstream
project points REPORTS_AT_RISK_RULES_MODULE at: it extends BASE_AT_RISK_RULES
with one extra rule and exports the result as AT_RISK_RULES.
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


AT_RISK_RULES: list[AtRiskRule] = [*BASE_AT_RISK_RULES, _FixtureExtraRule()]
