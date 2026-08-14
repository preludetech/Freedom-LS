"""Loader for the configured at-risk rule registry.

get_at_risk_rules() is cached for the process lifetime. Callers that use
override_settings(REPORTS_AT_RISK_RULES_MODULE=...) in tests MUST call
get_at_risk_rules.cache_clear() before and after the test to avoid the cached
list bleeding across tests.
"""

from __future__ import annotations

import functools
from importlib import import_module

from freedom_ls.reports.at_risk.rules import AtRiskRule
from freedom_ls.reports.config import config


@functools.cache
def get_at_risk_rules() -> list[AtRiskRule]:
    """Resolve config.REPORTS_AT_RISK_RULES_MODULE into an ordered rule list.

    Accepts either an AT_RISK_RULES or a BASE_AT_RISK_RULES export, so the
    default module (which only defines BASE_AT_RISK_RULES) needs no extra
    alias module to satisfy the setting.
    """
    module_path = config.REPORTS_AT_RISK_RULES_MODULE
    module = import_module(module_path)
    rules = getattr(module, "AT_RISK_RULES", None)
    if rules is None:
        rules = getattr(module, "BASE_AT_RISK_RULES", None)
    if rules is None:
        raise ImportError(
            f"Module '{module_path}' has neither 'AT_RISK_RULES' nor "
            f"'BASE_AT_RISK_RULES' attribute."
        )
    return list(rules)
