"""Tests for the 0002_rename_educator_roles data migration."""

import importlib

import pytest

from django.apps import apps as django_apps
from django.contrib.sites.models import Site

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.role_based_permissions.factories import (
    ObjectRoleAssignmentFactory,
    SiteRoleAssignmentFactory,
)

migration = importlib.import_module(
    "freedom_ls.role_based_permissions.migrations.0002_rename_educator_roles"
)

RENAMED_ROLES = [
    ("organisation_staff", "organisation_admin"),
    ("instructor", "cohort_admin"),
    ("ta", "cohort_viewer"),
]


@pytest.mark.django_db
class TestRenameForward:
    """rename_forward moves rows from the old role key to the new one."""

    @pytest.mark.parametrize(("old_role", "new_role"), RENAMED_ROLES)
    def test_site_role_assignment_moves_to_new_key(
        self, mock_site_context: Site, old_role: str, new_role: str
    ) -> None:
        assignment = SiteRoleAssignmentFactory(role=old_role)

        migration.rename_forward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == new_role

    @pytest.mark.parametrize(("old_role", "new_role"), RENAMED_ROLES)
    def test_object_role_assignment_moves_to_new_key(
        self, mock_site_context: Site, old_role: str, new_role: str
    ) -> None:
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort, role=old_role)

        migration.rename_forward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == new_role

    def test_site_admin_role_is_untouched(self, mock_site_context: Site) -> None:
        assignment = SiteRoleAssignmentFactory(role="site_admin")

        migration.rename_forward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == "site_admin"

    def test_custom_role_is_untouched(self, mock_site_context: Site) -> None:
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort, role="senior_ta")

        migration.rename_forward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == "senior_ta"


@pytest.mark.django_db
class TestRenameBackward:
    """rename_backward is the inverse: new key back to the old one."""

    @pytest.mark.parametrize(("old_role", "new_role"), RENAMED_ROLES)
    def test_site_role_assignment_moves_back_to_old_key(
        self, mock_site_context: Site, old_role: str, new_role: str
    ) -> None:
        assignment = SiteRoleAssignmentFactory(role=new_role)

        migration.rename_backward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == old_role

    @pytest.mark.parametrize(("old_role", "new_role"), RENAMED_ROLES)
    def test_object_role_assignment_moves_back_to_old_key(
        self, mock_site_context: Site, old_role: str, new_role: str
    ) -> None:
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort, role=new_role)

        migration.rename_backward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == old_role

    def test_site_admin_role_is_untouched(self, mock_site_context: Site) -> None:
        assignment = SiteRoleAssignmentFactory(role="site_admin")

        migration.rename_backward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == "site_admin"

    def test_custom_role_is_untouched(self, mock_site_context: Site) -> None:
        cohort = CohortFactory()
        assignment = ObjectRoleAssignmentFactory(target_object=cohort, role="senior_ta")

        migration.rename_backward(django_apps, None)

        assignment.refresh_from_db()
        assert assignment.role == "senior_ta"
