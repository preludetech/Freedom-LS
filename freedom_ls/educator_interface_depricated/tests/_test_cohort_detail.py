"""Tests for cohort_detail view."""

import pytest
from django.test import Client
from django.urls import reverse
from guardian.shortcuts import assign_perm

from freedom_ls.student_management.models import Cohort


@pytest.mark.django_db
def test_cohort_detail_view_returns_200(mock_site_context, user):
    """Test that cohort detail view returns 200 for authorized user."""
    # Create a cohort
    cohort = Cohort.objects.create(name="Test Cohort")

    # Assign view permission to user
    assign_perm("view_cohort", user, cohort)

    # Create client and login
    client = Client()
    client.force_login(user)

    # Call the cohort detail view (using cohort.pk as identifier)
    url = reverse("educator_interface:cohort_detail", kwargs={"cohort_id": cohort.pk})
    response = client.get(url)

    # Check response
    assert response.status_code == 200
    assert response.context["cohort"] == cohort
