"""Tests for CreateCohortAction — cohort creation carries the organisation.

CohortForm stays fields = ["name"]; the organisation is never a user choice.
CreateCohortAction attaches request.organisation to the instance before the
form validates, so the per-organisation uniqueness constraint is checked while
cleaning instead of blowing up as an IntegrityError at the database.

Most of these are unit tests of the action, so they hand-build the request.
That the view actually sets request.organisation is covered end to end in
test_config_authorisation.py. The one true end-to-end test here proves the
success criterion this slice exists for: an organisation admin with no
superuser flag can create a cohort through the interface.
"""

from __future__ import annotations

import json
import re

import pytest

from django.contrib.sites.models import Site
from django.core.exceptions import NON_FIELD_ERRORS
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.events import COHORT_CHANGED
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.educator_interface.views import CohortConfig, CreateCohortAction
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.role_based_permissions.utils import assign_object_role


def _ctx(request: HttpRequest) -> PanelContext:
    return PanelContext(
        request=request,
        instance=None,
        base_url="/cohorts",
        name="",
        config=CohortConfig,
    )


@pytest.mark.django_db
def test_creating_a_cohort_lands_it_in_request_organisation(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    request = RequestFactory().post("/", {"name": "New Cohort"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(_ctx(request))

    assert response.status_code == 204
    cohort = Cohort.objects.get(name="New Cohort")
    assert cohort.organisation == organisation


@pytest.mark.django_db
def test_success_url_carries_the_organisation_slug(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    request = RequestFactory().post("/", {"name": "Redirect Cohort"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(_ctx(request))

    cohort = Cohort.objects.get(name="Redirect Cohort")
    assert json.loads(response["HX-Location"]) == {
        "path": reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"cohorts/{cohort.pk}",
            },
        ),
        "target": "#main-content",
        "swap": "outerHTML",
    }
    assert response["HX-Trigger"] == build_hx_trigger(
        {COHORT_CHANGED: [str(cohort.pk)]}, close_modal=True
    )
    assert "HX-Redirect" not in response


@pytest.mark.django_db
def test_duplicate_cohort_name_in_same_organisation_is_rejected_with_a_visible_error(
    mock_site_context: Site,
) -> None:
    """422 so HTMX swaps the form fragment back in rather than redirecting,
    with the clash named in that fragment."""
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    request = RequestFactory().post("/", {"name": "Year 10 Science"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(_ctx(request))

    assert response.status_code == 422
    assert "Another cohort already has this name." in response.content.decode()


@pytest.mark.django_db
def test_duplicate_cohort_name_error_is_attached_to_the_name_field(
    mock_site_context: Site,
) -> None:
    """The Name input is marked invalid and the summary counts one field."""
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    request = RequestFactory().post("/", {"name": "Year 10 Science"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(_ctx(request))

    html = response.content.decode()
    name_input = re.search(r'<input[^>]*name="name"[^>]*>', html)
    assert name_input is not None
    assert 'aria-invalid="true"' in name_input.group(0)
    assert "1 field to fix." in html


@pytest.mark.django_db
def test_duplicate_cohort_name_in_same_organisation_creates_no_second_row(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    request = RequestFactory().post("/", {"name": "Year 10 Science"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    CreateCohortAction().handle_submit(_ctx(request))

    assert (
        Cohort.objects.filter(organisation=organisation, name="Year 10 Science").count()
        == 1
    )


@pytest.mark.django_db
def test_creating_a_cohort_named_after_one_in_another_organisation_succeeds(
    mock_site_context: Site,
) -> None:
    other_organisation = OrganisationFactory()
    organisation = OrganisationFactory()
    CohortFactory(organisation=other_organisation, name="Year 10 Science")
    request = RequestFactory().post("/", {"name": "Year 10 Science"})
    request.user = UserFactory(staff=True)
    request.organisation = organisation

    response = CreateCohortAction().handle_submit(_ctx(request))

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
    assert form.errors["name"] == ["Another cohort already has this name."]
    assert NON_FIELD_ERRORS not in form.errors


@pytest.mark.django_db
def test_an_organisation_admin_with_no_superuser_flag_creates_a_cohort(
    mock_site_context: Site, logged_in_client
) -> None:
    """The success criterion this slice exists for."""
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "organisation_admin")
    client = logged_in_client(user)

    list_response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )
    assert "Create Cohort" in list_response.content.decode()

    create_response = client.post(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": "cohorts/__actions/create_cohort",
            },
        ),
        {"name": "New Cohort"},
        HTTP_HX_REQUEST="true",
    )

    assert create_response.status_code == 204
    assert Cohort.objects.filter(organisation=organisation, name="New Cohort").exists()
