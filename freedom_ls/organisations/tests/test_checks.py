"""Tests for the organisations required-settings system check."""

from __future__ import annotations

from django.core.checks import registry

from freedom_ls.organisations.checks import check_required_organisations_settings


def test_check_is_registered_via_app_ready() -> None:
    # Guards against OrganisationsConfig.ready() dropping the checks import: a
    # direct call to the function would stay green even if it were never
    # registered and so never ran on manage.py check / migrate.
    assert check_required_organisations_settings in registry.registry.registered_checks
