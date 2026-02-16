"""Tests for cohorts_list view."""

import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from guardian.shortcuts import assign_perm

from freedom_ls.student_management.models import Cohort


@pytest.mark.django_db
def test_user_with_no_permissions_sees_no_cohorts(mock_site_context, user):
    """User without view permissions sees no cohorts."""
    # Create cohorts but don't assign permissions
    Cohort.objects.create(name="Cohort A")
    Cohort.objects.create(name="Cohort B")

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call view
    url = reverse("educator_interface:cohorts_list")
    response = client.get(url)

    # Check response
    assert response.status_code == 200
    cohorts_list_result = list(response.context["cohorts"])
    assert len(cohorts_list_result) == 0


@pytest.mark.django_db
def test_user_with_permissions_sees_assigned_cohorts(mock_site_context, user):
    """User with view permissions sees only assigned cohorts."""
    # Create cohorts
    cohort_a = Cohort.objects.create(name="Cohort A")
    Cohort.objects.create(name="Cohort B")
    cohort_c = Cohort.objects.create(name="Cohort C")

    # Assign permissions only for cohort_a and cohort_c
    assign_perm("view_cohort", user, cohort_a)
    assign_perm("view_cohort", user, cohort_c)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call view
    url = reverse("educator_interface:cohorts_list")
    response = client.get(url)

    # Check response
    assert response.status_code == 200
    cohorts = list(response.context["cohorts"])
    assert cohorts == [cohort_a, cohort_c]


@pytest.mark.django_db
def test_cohort_names_are_clickable_links(mock_site_context, user):
    """Test that cohort names are clickable links to the detail page."""
    # Create a cohort
    cohort = Cohort.objects.create(name="Test Cohort")

    # Assign view permission
    assign_perm("view_cohort", user, cohort)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call cohorts list view
    url = reverse("educator_interface:cohorts_list")
    response = client.get(url)

    # Check that the response contains a link to the cohort detail page
    assert response.status_code == 200
    cohort_detail_url = reverse("educator_interface:cohort_detail", kwargs={"cohort_id": cohort.pk})
    assert cohort_detail_url in response.content.decode()
