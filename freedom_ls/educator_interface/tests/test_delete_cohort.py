from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.student_management.models import Cohort


def _cohort_url(cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface", kwargs={"path_string": f"cohorts/{cohort_pk}"}
    )


def _delete_action_url(cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"path_string": f"cohorts/{cohort_pk}/__actions/delete"},
    )


@pytest.mark.django_db
def test_delete_button_appears_on_cohort_detail(client, mock_site_context):
    """Delete button appears on cohort detail page."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    assign_perm("freedom_ls_student_management.delete_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_cohort_url(cohort.pk))
    content = response.content.decode()
    assert "Delete" in content


@pytest.mark.django_db
def test_delete_confirmation_shows_cascade_summary(client, mock_site_context):
    """Confirmation shows cascade summary for related objects."""
    cohort = CohortFactory()
    CohortMembershipFactory(cohort=cohort)
    CohortCourseRegistrationFactory(cohort=cohort)
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    assign_perm("freedom_ls_student_management.delete_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_cohort_url(cohort.pk))
    content = response.content.decode()
    # Should mention related objects that will be deleted
    assert (
        "will also delete" in content.lower() or "cohort membership" in content.lower()
    )


@pytest.mark.django_db
def test_successful_deletion_redirects_to_cohorts_list(client, mock_site_context):
    """Successful deletion deletes cohort and redirects to cohorts list."""
    cohort = CohortFactory()
    cohort_pk = cohort.pk
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.delete_cohort", user, cohort)
    client.force_login(user)
    response = client.delete(_delete_action_url(cohort_pk))
    assert response.status_code == 204
    assert "cohorts" in response["HX-Redirect"]
    assert not Cohort.objects.filter(pk=cohort_pk).exists()


@pytest.mark.django_db
def test_delete_without_permission_returns_403(client, mock_site_context):
    """User without delete_cohort permission gets 403."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    # No delete_cohort permission
    client.force_login(user)
    response = client.delete(_delete_action_url(cohort.pk))
    assert response.status_code == 403
    assert Cohort.objects.filter(pk=cohort.pk).exists()
