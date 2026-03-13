from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.factories import CohortFactory
from freedom_ls.student_management.models import Cohort


def _cohorts_url() -> str:
    return reverse("educator_interface:interface", kwargs={"path_string": "cohorts"})


def _create_action_url() -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"path_string": "cohorts/__actions/create_cohort"},
    )


@pytest.mark.django_db
def test_create_cohort_form_renders_in_modal_on_list_page(client, mock_site_context):
    """Create cohort form renders in modal on cohorts list page."""
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.add_cohort", user)
    assign_perm("freedom_ls_student_management.view_cohort", user)
    client.force_login(user)
    response = client.get(_cohorts_url())
    assert response.status_code == 200
    assert "Create Cohort" in response.content.decode()


@pytest.mark.django_db
def test_submit_valid_form_creates_cohort(client, mock_site_context):
    """Submitting valid form creates cohort and returns HX-Redirect."""
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.add_cohort", user)
    client.force_login(user)
    response = client.post(_create_action_url(), {"name": "New Cohort"})
    assert Cohort.objects.filter(name="New Cohort").exists()
    cohort = Cohort.objects.get(name="New Cohort")
    assert response.status_code == 204
    assert f"cohorts/{cohort.pk}" in response["HX-Redirect"]


@pytest.mark.django_db
def test_save_and_add_another_returns_empty_form_and_trigger(client, mock_site_context):
    """'Save and add another' returns re-rendered empty form + HX-Trigger event."""
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.add_cohort", user)
    client.force_login(user)
    response = client.post(
        _create_action_url(),
        {"name": "Cohort A", "action": "save_and_add"},
    )
    assert response.status_code == 200
    assert Cohort.objects.filter(name="Cohort A").exists()
    assert response["HX-Trigger"] == "cohortCreated"
    # Form should be empty (no value for name field pre-filled)
    content = response.content.decode()
    assert "Create Cohort" in content


@pytest.mark.django_db
def test_duplicate_cohort_name_returns_422(client, mock_site_context):
    """Duplicate cohort name within site returns 422 with validation error."""
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.add_cohort", user)
    client.force_login(user)
    CohortFactory(name="Existing")
    response = client.post(_create_action_url(), {"name": "Existing"})
    assert response.status_code == 422


@pytest.mark.django_db
def test_permission_check_returns_403(client, mock_site_context):
    """User without add_cohort permission returns 403."""
    user = UserFactory(staff=True)
    # No add_cohort permission
    client.force_login(user)
    response = client.post(_create_action_url(), {"name": "Forbidden"})
    assert response.status_code == 403
    assert not Cohort.objects.filter(name="Forbidden").exists()
