"""The educator interface hides actions a request may not use.

Slice 8 adds the 403 fragment for a denied action posted anyway. This slice
only proves the control itself is never rendered for a role that cannot use
it -- "hidden, not disabled" -- plus the end-to-end denial experience: a
stale action posted anyway 404s or 403s, names an organisation admin to ask,
and creates nothing.
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.views import OrganisationSectionConfig
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort, OrganisationMember
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    remove_object_role,
)


def _cohorts_list_html(client: Client, organisation: Organisation) -> str:
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )
    return response.content.decode()


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


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


@pytest.mark.django_db
def test_cohort_admin_gets_404_for_a_cohort_in_their_organisation_they_hold_no_grant_on(
    mock_site_context: Site, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    granted_cohort = CohortFactory(organisation=organisation)
    ungranted_cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_object_role(user, granted_cohort, "cohort_admin")
    client = logged_in_client(user)

    response = client.get(
        _interface_url(organisation.slug, f"cohorts/{ungranted_cohort.pk}")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_organisation_admin_with_an_inactive_organisation_member_gets_404(
    mock_site_context: Site, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "organisation_admin")
    OrganisationMember.objects.filter(user=user, organisation=organisation).update(
        is_active=False
    )
    client = logged_in_client(user)

    response = client.get(_interface_url(organisation.slug, "dashboard"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_denied_create_cohort_action_answers_403_naming_an_organisation_admin(
    mock_site_context: Site, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    # cohort_viewer keeps the organisation reachable once organisation_admin
    # is removed below.
    assign_object_role(user, organisation, "organisation_admin")
    assign_object_role(user, cohort, "cohort_viewer")
    client = logged_in_client(user)

    list_response = client.get(_interface_url(organisation.slug, "cohorts"))
    assert list_response.status_code == 200

    remove_object_role(user, organisation, "organisation_admin")

    create_response = client.post(
        _interface_url(organisation.slug, "cohorts/__actions/create_cohort"),
        {"name": "Should not be created"},
        HTTP_HX_REQUEST="true",
    )

    assert create_response.status_code == 403
    html = create_response.content.decode()
    assert "You can't use “Create Cohort” here any more" in html
    assert f"Ask an organisation admin of {organisation.name}." in html
    assert not Cohort.objects.filter(
        organisation=organisation, name="Should not be created"
    ).exists()


@pytest.mark.django_db
def test_denied_context_names_organisation_admins_for_a_viewer_of_organisationmember(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    admin = UserFactory(first_name="Ada", last_name="Admin")
    assign_object_role(admin, organisation, "organisation_admin")
    # A site_admin holds view_organisationmember on every organisation on
    # its site without itself being an organisation_admin, so the asker
    # never appears among the names it is asking for.
    asker = UserFactory()
    assign_site_role(asker, "site_admin", site=mock_site_context)
    request = RequestFactory().get("/")
    request.user = asker
    request.organisation = organisation

    context = OrganisationSectionConfig.get_denied_context(request, None, organisation)

    assert (
        context["who_to_ask"]
        == f"Ask an organisation admin of {organisation.name}: Ada Admin."
    )


@pytest.mark.django_db
def test_denied_context_omits_names_for_an_asker_who_may_not_view_organisationmember(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    admin = UserFactory(first_name="Ada", last_name="Admin")
    assign_object_role(admin, organisation, "organisation_admin")
    asker = UserFactory()
    assign_object_role(asker, cohort, "cohort_viewer")
    request = RequestFactory().get("/")
    request.user = asker
    request.organisation = organisation

    context = OrganisationSectionConfig.get_denied_context(request, None, organisation)

    assert context["who_to_ask"] == f"Ask an organisation admin of {organisation.name}."


@pytest.mark.django_db
def test_stale_delete_on_a_cohort_that_left_scope_answers_the_unavailable_fragment(
    mock_site_context: Site, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    other_cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    # cohort_viewer on another cohort keeps the organisation reachable, while
    # the cohort being deleted leaves scope with organisation_admin.
    assign_object_role(user, organisation, "organisation_admin")
    assign_object_role(user, other_cohort, "cohort_viewer")
    client = logged_in_client(user)
    delete_url = _interface_url(
        organisation.slug,
        f"cohorts/{cohort.pk}/__tabs/details/__panels/details/__actions/delete",
    )
    assert client.get(delete_url, HTTP_HX_REQUEST="true").status_code == 200

    remove_object_role(user, organisation, "organisation_admin")

    response = client.delete(delete_url, HTTP_HX_REQUEST="true")

    assert response.status_code == 404
    html = response.content.decode()
    assert "data-htmx-swap-error" in html
    assert "This is no longer available" in html
    assert cohort.name not in html
    assert Cohort.objects.filter(pk=cohort.pk).exists()
