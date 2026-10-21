"""Tests for the migration that deletes role rows left behind by deleted cohorts."""

import importlib

import pytest
from guardian.models import UserObjectPermission

from django.apps import apps as django_apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    delete_cohort_leaving_role_rows,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import assign_object_role

migration = importlib.import_module(
    "freedom_ls.learner_management.migrations.0006_delete_orphan_cohort_role_rows"
)


def _cohort_with_role_rows() -> Cohort:
    cohort: Cohort = CohortFactory()
    assign_object_role(UserFactory(), cohort, "cohort_admin")
    return cohort


@pytest.mark.django_db
class TestDeleteOrphans:
    def test_removes_the_assignment_of_a_deleted_cohort(
        self, mock_site_context: Site
    ) -> None:
        cohort = _cohort_with_role_rows()
        delete_cohort_leaving_role_rows(cohort)

        migration.delete_orphans(django_apps, None)

        assert ObjectRoleAssignment._base_manager.count() == 0

    def test_removes_the_guardian_row_of_a_deleted_cohort(
        self, mock_site_context: Site
    ) -> None:
        cohort = _cohort_with_role_rows()
        delete_cohort_leaving_role_rows(cohort)

        migration.delete_orphans(django_apps, None)

        assert not UserObjectPermission.objects.filter(
            content_type=ContentType.objects.get_for_model(Cohort)
        ).exists()

    def test_keeps_the_rows_of_a_cohort_that_exists(
        self, mock_site_context: Site
    ) -> None:
        _cohort_with_role_rows()
        guardian_rows = UserObjectPermission.objects.count()

        migration.delete_orphans(django_apps, None)

        assert ObjectRoleAssignment._base_manager.count() == 1
        assert UserObjectPermission.objects.count() == guardian_rows
