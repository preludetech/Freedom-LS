"""The educator dashboard: a base view with no instance and no table."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture
def educator(mock_site_context):
    organisation = OrganisationFactory(name="Northside Academy")
    user = UserFactory(staff=True)
    assign_object_role(user, organisation, "organisation_staff")
    return organisation, user


@pytest.mark.django_db
def test_dashboard_renders_the_reporting_placeholder(educator, logged_in_client):
    organisation, user = educator

    response = logged_in_client(user).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "dashboard"},
        )
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Reporting" in content
    assert "Northside Academy arrives in a later release" in content


@pytest.mark.django_db
def test_the_bare_root_redirects_to_the_dashboard(educator, logged_in_client):
    organisation, user = educator

    response = logged_in_client(user).get(reverse("educator_interface:root"))

    assert response["Location"] == reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "dashboard"},
    )
