"""Tests for the content_engine required-settings system check."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.content_engine.checks import check_required_content_engine_settings


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
