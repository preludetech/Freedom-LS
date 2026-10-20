"""Tests for the registration_rules system checks."""

from __future__ import annotations

import pytest

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.registration_rules.checks import check_rule_kinds_import


def test_e002_for_a_kind_path_that_does_not_import(settings):
    # Arrange
    settings.REGISTRATION_RULE_KINDS = {"attribute": "freedom_ls.nowhere.Missing"}

    # Act
    errors = check_rule_kinds_import(None)

    # Assert
    assert [e.id for e in errors] == ["freedom_ls_registration_rules.E002"]


def test_default_kinds_pass_the_import_check():
    assert check_rule_kinds_import(None) == []
