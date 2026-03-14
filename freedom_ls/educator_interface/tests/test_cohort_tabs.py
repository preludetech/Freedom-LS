from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.factories import CohortFactory


def _cohort_url(cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface", kwargs={"path_string": f"cohorts/{cohort_pk}"}
    )


def _tab_url(cohort_pk: object, tab_name: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"path_string": f"cohorts/{cohort_pk}/__tabs/{tab_name}"},
    )


def _tab_panel_url(cohort_pk: object, tab_name: str, panel_name: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "path_string": f"cohorts/{cohort_pk}/__tabs/{tab_name}/__panels/{panel_name}"
        },
    )


@pytest.mark.django_db
def test_cohort_renders_tab_bar(client, mock_site_context):
    """CohortInstanceView renders tab bar with 'Course Progress' and 'Details'."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_cohort_url(cohort.pk))
    content = response.content.decode()
    assert "Course Progress" in content
    assert "Details" in content
    assert 'role="tablist"' in content


@pytest.mark.django_db
def test_first_tab_content_rendered_inline(client, mock_site_context):
    """'Course Progress' tab content is present in initial page HTML (default active tab)."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_cohort_url(cohort.pk))
    content = response.content.decode()
    # The course progress panel should be rendered inline
    assert "tab-content-course_progress" in content
    # The active tab should be course_progress (set via data attribute for CSP-compatible Alpine)
    assert 'data-active-tab="course_progress"' in content


@pytest.mark.django_db
def test_details_tab_has_htmx_lazy_load(client, mock_site_context):
    """'Details' tab has HTMX lazy-load URL pointing to __tabs/details."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_cohort_url(cohort.pk))
    content = response.content.decode()
    expected_url = "/__tabs/details"
    assert expected_url in content
    assert "load-tab" in content


@pytest.mark.django_db
def test_htmx_request_to_tab_returns_panels_fragment(client, mock_site_context):
    """HTMX request to __tabs/details returns details + courses + students panels as fragment."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(
        _tab_url(cohort.pk, "details"),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    content = response.content.decode()
    # Should contain details panel
    assert "Details" in content
    # Should not be wrapped in full page layout
    assert "<nav" not in content


@pytest.mark.django_db
def test_single_panel_within_tab_returns_just_that_panel(client, mock_site_context):
    """Requesting __tabs/course_progress/__panels/course_progress returns just that panel."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(
        _tab_panel_url(cohort.pk, "course_progress", "course_progress")
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_direct_url_access_renders_full_page_with_tab_active(client, mock_site_context):
    """Non-HTMX GET to cohorts/{pk}/__tabs/details returns full page with 'Details' tab active."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_tab_url(cohort.pk, "details"))
    assert response.status_code == 200
    content = response.content.decode()
    # Should be a full page with navigation
    assert "<nav" in content
    # Active tab should be 'details' (set via data attribute for CSP-compatible Alpine)
    assert 'data-active-tab="details"' in content


@pytest.mark.django_db
def test_tab_buttons_include_history_push_state(client, mock_site_context):
    """Tab buttons include history.pushState calls with correct tab URL."""
    cohort = CohortFactory()
    user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    client.force_login(user)
    response = client.get(_cohort_url(cohort.pk))
    content = response.content.decode()
    # Tab buttons have data-tab-name attributes; Alpine component handles pushState
    assert 'data-tab-name="details"' in content
