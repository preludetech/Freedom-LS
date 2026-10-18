"""Tests for the rule-kind loader."""

from __future__ import annotations

import pytest

from django.core.exceptions import ImproperlyConfigured

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.registration_rules.kinds import AttributeRuleKind
from freedom_ls.registration_rules.loader import get_rule_kind


def test_attribute_resolves_to_the_attribute_kind():
    assert isinstance(get_rule_kind("attribute"), AttributeRuleKind)


def test_unknown_key_raises_improperly_configured():
    with pytest.raises(ImproperlyConfigured):
        get_rule_kind("nonexistent")
