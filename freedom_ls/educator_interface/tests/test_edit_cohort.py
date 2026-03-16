from __future__ import annotations

import json

import pytest
from guardian.shortcuts import assign_perm

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.factories import CohortFactory


def _edit_action_url(cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "path_string": f"cohorts/{cohort_pk}/__tabs/details/__panels/details/__actions/edit"
        },
    )


def _details_tab_url(cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"path_string": f"cohorts/{cohort_pk}/__tabs/details"},
    )


@pytest.mark.django_db
def test_edit_button_appears_on_cohort_details_panel(client, mock_site_context):
    """Edit button appears on cohort details panel."""
    cohort = CohortFactory(name="Test Cohort")
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    assign_perm("freedom_ls_student_management.change_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_details_tab_url(cohort.pk), HTTP_HX_REQUEST="true")
    content = response.content.decode()
    assert "Edit" in content


@pytest.mark.django_db
def test_successful_edit_updates_cohort(client, mock_site_context):
    """Successful edit updates cohort name."""
    cohort = CohortFactory(name="Old Name")
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.change_cohort", user, cohort)
    client.force_login(user)
    response = client.post(_edit_action_url(cohort.pk), {"name": "New Name"})
    assert response.status_code == 204
    cohort.refresh_from_db()
    assert cohort.name == "New Name"
    trigger = json.loads(response["HX-Trigger"])
    assert "panelChanged" in trigger
    assert trigger["panelChanged"]["instanceTitle"] == "New Name"


@pytest.mark.django_db
def test_duplicate_name_edit_returns_422(client, mock_site_context):
    """Duplicate name returns 422 with validation error."""
    CohortFactory(name="Existing")
    cohort = CohortFactory(name="Original")
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.change_cohort", user, cohort)
    client.force_login(user)
    response = client.post(_edit_action_url(cohort.pk), {"name": "Existing"})
    assert response.status_code == 422


@pytest.mark.django_db
def test_tab_panels_have_data_tab_url(client, mock_site_context):
    """Tab panel divs include data-tab-url so Alpine can refresh them after edit."""
    cohort = CohortFactory(name="Test Cohort")
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_details_tab_url(cohort.pk))
    content = response.content.decode()
    assert "data-tab-url" in content


@pytest.mark.django_db
def test_edit_without_permission_returns_403(client, mock_site_context):
    """User without change_cohort permission gets 403."""
    cohort = CohortFactory(name="Test")
    user = UserFactory(staff=True)
    # No change_cohort permission
    client.force_login(user)
    response = client.post(_edit_action_url(cohort.pk), {"name": "Changed"})
    assert response.status_code == 403
    cohort.refresh_from_db()
    assert cohort.name == "Test"
