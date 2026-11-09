"""The staff administration QA command seeds the no-role and viewer-role staff personas."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.core.management import call_command

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.qa_helpers"):
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.models import StaffMember
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

pytestmark = [pytest.mark.django_db, pytest.mark.dev_tooling]


@pytest.fixture
def seeded_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    Site.objects.create(name="Bloom", domain="bloom.example.test")
    UserFactory(site=site, email="demodev@email.com", is_superuser=True)
    call_command("qa_create_staff_administration_scenario")
    call_command("qa_create_staff_administration_scenario")
    return site


def _grants(email: str, role: str) -> int:
    return ObjectRoleAssignment._base_manager.filter(
        user__email=email, role=role, is_active=True
    ).count()


def test_no_role_persona_has_one_active_staff_member_and_no_grant(seeded_site):
    northside = Organisation._base_manager.get(site=seeded_site, slug="northside")

    rows = StaffMember._base_manager.filter(
        user__email="norole.staff@qa.test", organisation=northside
    )

    assert [row.is_active for row in rows] == [True]
    assert not ObjectRoleAssignment._base_manager.filter(
        user__email="norole.staff@qa.test"
    ).exists()


def test_viewing_admin_has_one_staff_viewer_grant_and_one_cohort_admin_grant(
    seeded_site,
):
    assert _grants("viewing.admin@qa.test", "organisation_staff_viewer") == 1
    assert _grants("viewing.admin@qa.test", "cohort_admin") == 1


def test_roles_viewer_has_exactly_one_grant(seeded_site):
    assignments = ObjectRoleAssignment._base_manager.filter(
        user__email="roles.viewer@qa.test", is_active=True
    )

    assert [a.role for a in assignments] == ["organisation_staff_roles_viewer"]
