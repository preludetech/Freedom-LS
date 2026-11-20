"""Tests for the Staff section: access, navigation and intro."""

from __future__ import annotations

import uuid

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.tests.helpers import (
    _get_quick_view,
    _hold,
    _interface_url,
    _staff_document,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_members_is_a_404_for_a_cohort_role_holder(role_holder_client, role):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, role)

    response = client.get(_interface_url(organisation.slug, "staff"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_site_admin_with_no_role_in_the_organisation_can_open_members(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", mock_site_context
    )

    response = logged_in_client(site_admin).get(
        _interface_url(organisation.slug, "staff")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_member_path_with_an_id_under_it_is_a_404(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    response = client.get(_interface_url(organisation.slug, f"staff/{uuid.uuid4()}"))

    assert response.status_code == 404


VIEWER_ROLE_SECTIONS = [
    "dashboard",
    "learners",
    "cohorts",
    "courses",
    "audit-log",
]


@pytest.mark.django_db
@pytest.mark.parametrize("section", VIEWER_ROLE_SECTIONS)
@pytest.mark.parametrize(
    "role", ["organisation_staff_viewer", "organisation_staff_roles_viewer"]
)
def test_a_staff_viewer_role_gets_404_outside_the_staff_section(
    role_holder_client, role, section
):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, role)

    response = client.get(_interface_url(organisation.slug, section))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_sidebar_of_a_staff_viewer_lists_staff_alone(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_staff_viewer")

    document = _staff_document(client, organisation)

    (nav,) = document.cssselect("#sidebar-nav")
    assert [a.text_content().strip() for a in nav.cssselect("a")] == ["Staff"]


ONLY_STAFF_MEMBER_LINE = "You're the only staff member here."


@pytest.mark.django_db
def test_a_lone_organisation_admin_is_told_they_are_the_only_member(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")

    text = _staff_document(client, organisation).text_content()

    assert ONLY_STAFF_MEMBER_LINE in text


@pytest.mark.django_db
def test_the_only_member_line_goes_once_a_second_member_exists(role_holder_client):
    organisation = OrganisationFactory()
    client = role_holder_client(organisation, "organisation_admin")
    _hold(UserFactory(), "organisation_admin", organisation)

    text = _staff_document(client, organisation).text_content()

    assert ONLY_STAFF_MEMBER_LINE not in text


@pytest.mark.django_db
def test_a_malformed_pk_of_a_staff_row_404s(educator_client, mock_site_context):
    organisation = OrganisationFactory()

    response = _get_quick_view(
        educator_client(organisation), organisation, "staff/not-a-number"
    )

    assert response.status_code == 404
