"""Tests for CreateCohortAction — cohort creation carries the organisation.

CohortForm stays fields = ["name"]; the organisation is never a user choice.
CreateCohortAction.form_valid sets form.instance.organisation from
request.organisation before the base class saves.
"""

from __future__ import annotations

import pytest

from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.views import CreateCohortAction
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.student_management.factories import CohortFactory
from freedom_ls.student_management.models import Cohort


@pytest.mark.django_db
def test_creating_a_cohort_lands_it_in_request_organisation(mock_site_context):
    organisation = OrganisationFactory()
    request = RequestFactory().post("/", {"name": "New Cohort"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(
        request, instance=None, base_url="/cohorts"
    )

    assert response.status_code == 204
    cohort = Cohort.objects.get(name="New Cohort")
    assert cohort.organisation == organisation


@pytest.mark.django_db
def test_success_url_carries_the_organisation_slug(mock_site_context):
    organisation = OrganisationFactory()
    request = RequestFactory().post("/", {"name": "Redirect Cohort"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(
        request, instance=None, base_url="/cohorts"
    )

    cohort = Cohort.objects.get(name="Redirect Cohort")
    assert response["HX-Redirect"] == reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )


@pytest.mark.django_db
def test_two_organisations_can_each_have_a_cohort_with_the_same_name(
    mock_site_context,
):
    organisation_a = OrganisationFactory()
    organisation_b = OrganisationFactory()

    CohortFactory(organisation=organisation_a, name="Cohort X")
    CohortFactory(organisation=organisation_b, name="Cohort X")

    assert Cohort.objects.filter(name="Cohort X").count() == 2
