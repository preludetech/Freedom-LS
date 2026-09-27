"""Tests for can(): the capability check every role assignment answers through."""

from __future__ import annotations

from types import ModuleType
from unittest.mock import patch

import pytest

from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role, SiteRolesConfig
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role

VIEW_COHORT = "freedom_ls_learner_management.view_cohort"
ADD_COHORT = "freedom_ls_learner_management.add_cohort"
VIEW_ORGANISATION = "freedom_ls_organisations.view_organisation"


@pytest.fixture(autouse=True)
def _clear_role_caches():
    """Every test here reads role config or assigns roles; keep them isolated."""
    clear_caches()
    yield
    clear_caches()


@pytest.mark.django_db
def test_a_superuser_can_do_anything(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(superuser=True)

    assert can(user, VIEW_ORGANISATION, organisation) is True


@pytest.mark.django_db
def test_an_inactive_user_is_denied_even_with_a_grant(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(is_active=False)
    assign_object_role(user, organisation, "organisation_admin")

    assert can(user, VIEW_ORGANISATION, organisation) is False


@pytest.mark.django_db
def test_an_anonymous_user_is_denied(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()

    assert can(AnonymousUser(), VIEW_ORGANISATION, organisation) is False


@pytest.mark.django_db
def test_a_site_admin_can_view_and_add_cohorts_in_any_organisation_on_its_site(
    mock_site_context: Site,
) -> None:
    """Closes the gap in role_based_permissions/tests/test_utils.py's
    TestSiteRoleFunctions: a site role was only ever proven to sync onto
    guardian, never checked against an object it doesn't share a content
    type with."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_site_role(user, "site_admin")

    assert can(user, VIEW_COHORT, cohort) is True
    assert can(user, ADD_COHORT, organisation) is True


@pytest.mark.django_db
def test_a_cohort_created_after_the_grant_is_covered_with_nothing_re_synced(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "organisation_admin")

    cohort = CohortFactory(organisation=organisation)

    assert can(user, VIEW_COHORT, cohort) is True


@pytest.mark.django_db
def test_a_changed_role_config_takes_effect_after_clear_caches(
    mock_site_context: Site, settings
) -> None:
    """No guardian re-sync is involved: the grant on the cohort never changes,
    only the role config's own permission set does."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_object_role(user, cohort, "cohort_viewer")
    capability = "freedom_ls_learner_management.a_capability_only_the_new_config_grants"

    assert can(user, capability, cohort) is False

    module_path = "fake_permissions_module_for_test_capabilities"
    fake_module = ModuleType(module_path)
    fake_module.ROLES = SiteRolesConfig(
        {
            "cohort_viewer": Role(
                display_name="Cohort viewer",
                permissions=frozenset({capability}),
                assignment_scope=SCOPE_OBJECT,
            ),
        }
    )
    settings.FREEDOMLS_PERMISSIONS_MODULES = {mock_site_context.name: module_path}

    with patch(
        "freedom_ls.role_based_permissions.loader.import_module",
        return_value=fake_module,
    ):
        clear_caches()
        assert can(user, capability, cohort) is True


@pytest.mark.django_db
def test_a_site_scope_with_only_an_object_grant_is_denied(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "organisation_admin")

    assert can(user, VIEW_ORGANISATION, mock_site_context) is False
