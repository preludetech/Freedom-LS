"""System checks for the messaging policy app."""

from __future__ import annotations

import pytest
from pytest_django.fixtures import SettingsWrapper

from django.contrib.sites.models import Site
from django.test import override_settings

from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.messaging_policy.checks import (
    check_default_flags,
    check_offered_roles_exist,
    check_stored_offered_roles,
)
from freedom_ls.messaging_policy.factories import SiteMessagingConfigFactory

VALID_FLAGS = {
    "learner_to_educator": "closed",
    "learner_to_cohort_peer": "open",
    "learner_to_course_peer": "closed",
}


@pytest.mark.parametrize(
    "flags",
    [
        {"learner_to_educator": "closed", "learner_to_cohort_peer": "closed"},
        {**VALID_FLAGS, "learner_to_everyone": "open"},
        {**VALID_FLAGS, "learner_to_educator": "inherit"},
        {**VALID_FLAGS, "learner_to_educator": "sometimes"},
    ],
    ids=["missing_key", "unknown_key", "inherit_value", "bad_value"],
)
def test_malformed_default_flags_produce_an_error(flags: dict[str, str]) -> None:
    with override_settings(MESSAGING_DEFAULT_FLAGS=flags):
        errors = check_default_flags(None)

    assert [error.id for error in errors] == ["freedom_ls_messaging_policy.E001"]


def test_valid_default_flags_produce_no_error() -> None:
    with override_settings(MESSAGING_DEFAULT_FLAGS=VALID_FLAGS):
        errors = check_default_flags(None)

    assert errors == []


def test_the_shipped_default_flags_produce_no_error() -> None:
    assert check_default_flags(None) == []


def test_an_unknown_offered_role_produces_an_error() -> None:
    with override_settings(MESSAGING_OFFERED_EDUCATOR_ROLES=["cohort_admin", "nope"]):
        errors = check_offered_roles_exist(None)

    assert [error.id for error in errors] == ["freedom_ls_messaging_policy.E002"]


def test_the_shipped_offered_roles_produce_no_error() -> None:
    assert check_offered_roles_exist(None) == []


@pytest.mark.django_db
def test_an_offered_role_missing_from_a_site_role_config_produces_an_error(
    mock_site_context: Site, settings: SettingsWrapper
) -> None:
    settings.MESSAGING_OFFERED_EDUCATOR_ROLES = ["cohort_admin"]

    with custom_role_config(
        mock_site_context, settings, without=frozenset({"cohort_admin"})
    ):
        errors = check_offered_roles_exist(None)

    assert [error.id for error in errors] == ["freedom_ls_messaging_policy.E002"]


@pytest.mark.django_db
def test_a_stored_role_dropped_from_the_site_role_config_produces_a_warning(
    mock_site_context: Site, settings: SettingsWrapper
) -> None:
    SiteMessagingConfigFactory(offered_educator_roles=["cohort_viewer"])

    with custom_role_config(
        mock_site_context, settings, without=frozenset({"cohort_viewer"})
    ):
        warnings = check_stored_offered_roles(None)

    assert [warning.id for warning in warnings] == ["freedom_ls_messaging_policy.W001"]


@pytest.mark.django_db
def test_a_stored_role_that_no_longer_grants_view_learner_produces_a_warning(
    mock_site_context: Site,
) -> None:
    SiteMessagingConfigFactory(offered_educator_roles=["system_admin"])

    warnings = check_stored_offered_roles(None)

    assert [warning.id for warning in warnings] == ["freedom_ls_messaging_policy.W001"]


@pytest.mark.django_db
@pytest.mark.parametrize("value", [None, ["cohort_admin"]], ids=["none", "known_key"])
def test_a_known_or_unset_stored_offered_roles_value_produces_no_warning(
    mock_site_context: Site, value: list[str] | None
) -> None:
    SiteMessagingConfigFactory(offered_educator_roles=value)

    assert check_stored_offered_roles(None) == []
