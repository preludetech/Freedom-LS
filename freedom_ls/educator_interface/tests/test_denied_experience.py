"""The educator interface hides actions a request may not use.

Slice 8 adds the 403 fragment for a denied action posted anyway. This slice
only proves the control itself is never rendered for a role that cannot use
it -- "hidden, not disabled".
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


def _cohorts_list_html(client: Client, organisation: Organisation) -> str:
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )
    return response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_create_cohort_control_is_absent_for_a_role_that_may_not_create_cohorts(
    mock_site_context: Site, logged_in_client, role: str
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_object_role(user, cohort, role)
    client = logged_in_client(user)

    html = _cohorts_list_html(client, organisation)

    assert "Create Cohort" not in html
