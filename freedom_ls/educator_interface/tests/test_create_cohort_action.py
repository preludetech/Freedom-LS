"""Tests for CreateCohortAction — cohort creation carries the organisation.

CohortForm stays fields = ["name"]; the organisation is never a user choice.
CreateCohortAction attaches request.organisation to the instance before the
form validates, so the per-organisation uniqueness constraint is checked while
cleaning instead of blowing up as an IntegrityError at the database.

These are unit tests of the action, so they hand-build the request. That the
view actually sets request.organisation is covered end to end in
test_config_authorisation.py.
"""

from __future__ import annotations

import pytest

from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.educator_interface.views import CreateCohortAction
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory


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
def test_duplicate_cohort_name_in_same_organisation_is_rejected_with_a_visible_error(
    mock_site_context,
):
    """422 so HTMX swaps the form fragment back in rather than redirecting,
    with the clash named in that fragment."""
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    request = RequestFactory().post("/", {"name": "Year 10 Science"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(
        request, instance=None, base_url="/cohorts"
    )

    assert response.status_code == 422
    assert "already exists" in response.content.decode()


@pytest.mark.django_db
def test_duplicate_cohort_name_in_same_organisation_creates_no_second_row(
    mock_site_context,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    request = RequestFactory().post("/", {"name": "Year 10 Science"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    CreateCohortAction().handle_submit(request, instance=None, base_url="/cohorts")

    assert (
        Cohort.objects.filter(organisation=organisation, name="Year 10 Science").count()
        == 1
    )


@pytest.mark.django_db
def test_creating_a_cohort_named_after_one_in_another_organisation_succeeds(
    mock_site_context,
):
    other_organisation = OrganisationFactory()
    organisation = OrganisationFactory()
    CohortFactory(organisation=other_organisation, name="Year 10 Science")
    request = RequestFactory().post("/", {"name": "Year 10 Science"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(
        request, instance=None, base_url="/cohorts"
    )

    assert response.status_code == 204
    assert Cohort.objects.filter(name="Year 10 Science").count() == 2


@pytest.mark.django_db
def test_resaving_a_cohort_under_its_own_name_is_accepted(mock_site_context):
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")

    form = CohortForm({"name": "Year 10 Science"}, instance=cohort)

    assert form.is_valid()


@pytest.mark.django_db
def test_renaming_a_cohort_onto_a_sibling_name_is_rejected(mock_site_context):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    form = CohortForm({"name": "Year 10 Science"}, instance=cohort)

    assert not form.is_valid()
