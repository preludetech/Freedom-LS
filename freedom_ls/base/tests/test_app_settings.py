"""Tests for the shared per-app settings base (freedom_ls.base.app_settings)."""

from __future__ import annotations

import pytest

from django.core.checks import ERROR
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from freedom_ls.base.app_settings import AppSettings, Setting, required_settings_errors


class DemoConfig(AppSettings):
    """Throwaway subclass covering one optional and one required setting."""

    DEMO_OPTIONAL: str
    DEMO_REQUIRED: str

    declared_settings = {
        "DEMO_OPTIONAL": Setting(default="fallback-value"),
        "DEMO_REQUIRED": Setting(required=True),
    }


def test_returns_declared_default_when_setting_absent_from_django_settings() -> None:
    config = DemoConfig()

    assert config.DEMO_OPTIONAL == "fallback-value"


def test_django_setting_value_overrides_declared_default() -> None:
    config = DemoConfig()

    with override_settings(DEMO_OPTIONAL="project-value"):
        assert config.DEMO_OPTIONAL == "project-value"


def test_string_setting_value_is_stripped() -> None:
    config = DemoConfig()

    with override_settings(DEMO_OPTIONAL="  padded-value  "):
        assert config.DEMO_OPTIONAL == "padded-value"


def test_empty_string_setting_falls_back_to_default() -> None:
    config = DemoConfig()

    with override_settings(DEMO_OPTIONAL=""):
        assert config.DEMO_OPTIONAL == "fallback-value"


def test_whitespace_only_setting_falls_back_to_default() -> None:
    config = DemoConfig()

    with override_settings(DEMO_OPTIONAL="   "):
        assert config.DEMO_OPTIONAL == "fallback-value"


def test_unknown_attribute_name_raises_attribute_error() -> None:
    config = DemoConfig()

    with pytest.raises(AttributeError):
        _ = config.NOT_A_DECLARED_SETTING


def test_required_setting_unset_raises_improperly_configured_on_access() -> None:
    config = DemoConfig()

    with pytest.raises(ImproperlyConfigured):
        _ = config.DEMO_REQUIRED


def test_required_setting_empty_string_raises_improperly_configured_on_access() -> None:
    config = DemoConfig()

    with override_settings(DEMO_REQUIRED=""), pytest.raises(ImproperlyConfigured):
        _ = config.DEMO_REQUIRED


def test_required_setting_set_returns_project_value() -> None:
    config = DemoConfig()

    with override_settings(DEMO_REQUIRED="dotted.path.Backend"):
        assert config.DEMO_REQUIRED == "dotted.path.Backend"


def test_missing_required_lists_unset_required_setting_names() -> None:
    config = DemoConfig()

    assert config.missing_required() == ["DEMO_REQUIRED"]


def test_missing_required_empty_when_required_setting_is_set() -> None:
    config = DemoConfig()

    with override_settings(DEMO_REQUIRED="dotted.path.Backend"):
        assert config.missing_required() == []


def test_missing_required_ignores_optional_settings() -> None:
    config = DemoConfig()

    with override_settings(DEMO_REQUIRED="dotted.path.Backend"):
        missing = config.missing_required()

    assert "DEMO_OPTIONAL" not in missing


def test_missing_required_never_raises_when_required_setting_unset() -> None:
    config = DemoConfig()

    # Must return a list, not propagate ImproperlyConfigured.
    assert isinstance(config.missing_required(), list)


def test_required_settings_errors_reports_missing_required_setting() -> None:
    config = DemoConfig()

    errors = required_settings_errors(config, "demo_app")

    assert len(errors) == 1
    assert errors[0].id == "demo_app.E001"
    assert errors[0].level == ERROR


def test_required_settings_errors_empty_when_required_setting_is_set() -> None:
    config = DemoConfig()

    with override_settings(DEMO_REQUIRED="dotted.path.Backend"):
        errors = required_settings_errors(config, "demo_app")

    assert errors == []


def test_required_settings_errors_never_raises_for_unset_required_setting() -> None:
    config = DemoConfig()

    # Must not propagate ImproperlyConfigured — checks must never raise.
    errors = required_settings_errors(config, "demo_app")

    assert errors[0].id == "demo_app.E001"
