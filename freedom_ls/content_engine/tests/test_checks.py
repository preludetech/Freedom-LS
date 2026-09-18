"""Tests for the content_engine required-settings system check."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.content_engine.checks import (
    check_price_settings,
    check_required_content_engine_settings,
)


def test_unset_admonition_types_reports_required_setting_error() -> None:
    """An unset ADMONITION_TYPES surfaces a clear E001 instead of crashing at render."""
    with override_settings(ADMONITION_TYPES=None):
        errors = check_required_content_engine_settings()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_content_engine.E001"
    assert "ADMONITION_TYPES" in errors[0].msg


def test_set_admonition_types_produces_no_errors() -> None:
    """With ADMONITION_TYPES defined (the project default), the check is clean."""
    with override_settings(ADMONITION_TYPES={"default": {"icon": "info"}}):
        errors = check_required_content_engine_settings()

    assert errors == []


def test_unknown_default_currency_reports_error() -> None:
    with override_settings(DEFAULT_CURRENCY="ZZZ", PRICE_LOCALE=None):
        errors = check_price_settings()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_content_engine.E002"
    assert "ZZZ" in errors[0].msg


def test_valid_default_currency_produces_no_errors() -> None:
    with override_settings(DEFAULT_CURRENCY="ZAR", PRICE_LOCALE=None):
        errors = check_price_settings()

    assert errors == []


def test_unset_default_currency_produces_no_errors() -> None:
    with override_settings(DEFAULT_CURRENCY=None, PRICE_LOCALE=None):
        errors = check_price_settings()

    assert errors == []


def test_unknown_price_locale_reports_error() -> None:
    with override_settings(DEFAULT_CURRENCY=None, PRICE_LOCALE="not-a-locale"):
        errors = check_price_settings()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_content_engine.E003"
    assert "not-a-locale" in errors[0].msg


def test_valid_price_locale_produces_no_errors() -> None:
    with override_settings(DEFAULT_CURRENCY=None, PRICE_LOCALE="en_ZA"):
        errors = check_price_settings()

    assert errors == []


def test_unset_price_locale_produces_no_errors() -> None:
    with override_settings(DEFAULT_CURRENCY=None, PRICE_LOCALE=None):
        errors = check_price_settings()

    assert errors == []


def test_invalid_currency_and_locale_both_reported() -> None:
    with override_settings(DEFAULT_CURRENCY="ZZZ", PRICE_LOCALE="not-a-locale"):
        errors = check_price_settings()

    assert {error.id for error in errors} == {
        "freedom_ls_content_engine.E002",
        "freedom_ls_content_engine.E003",
    }
