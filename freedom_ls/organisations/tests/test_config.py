"""Tests for organisations per-app config defaults."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.organisations.config import config


def test_organisation_logo_storage_alias_defaults_to_public() -> None:
    assert config.ORGANISATION_LOGO_STORAGE_ALIAS == "public"


def test_organisation_logo_storage_alias_reads_project_override() -> None:
    with override_settings(ORGANISATION_LOGO_STORAGE_ALIAS="user_uploads"):
        assert config.ORGANISATION_LOGO_STORAGE_ALIAS == "user_uploads"
