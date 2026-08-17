"""Cross-organisation isolation for the educator interface.

Two Organisations under one Site, a user with a role on Organisation A only,
and assertions that every educator list view, detail view and HTMX partial
returns nothing (list) or 404 (detail/partial) for Organisation B.
Structural precedent: the existing cross-site isolation test in
test_course_visibility_and_interest.py, generalised from "other site" to
"other organisation".

Plus the lock-out case: an educator holding only per-cohort guardian grants
and no organisation role can still enter the interface and sees exactly
their cohorts.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.student_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
)


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


@pytest.mark.django_db
class TestCrossOrganisationIsolation:
    def _setup(self):
        organisation_a = OrganisationFactory(name="Org A")
        organisation_b = OrganisationFactory(name="Org B")
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation_a, "organisation_staff")
        cohort_b = CohortFactory(organisation=organisation_b, name="Cohort B Only")
        member_b = UserFactory(first_name="MemberOfB", last_name="Only")
        CohortMembershipFactory(cohort=cohort_b, user=member_b)
        return organisation_a, organisation_b, educator, cohort_b, member_b

    def test_cohorts_list_for_organisation_a_never_shows_organisation_bs_cohort(
        self, logged_in_client
    ):
        organisation_a, _organisation_b, educator, cohort_b, _member_b = self._setup()
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "cohorts"))

        assert response.status_code == 200
        assert cohort_b.name.encode() not in response.content

    def test_cohort_detail_404s_when_requested_through_organisation_a(
        self, logged_in_client
    ):
        organisation_a, _organisation_b, educator, cohort_b, _member_b = self._setup()
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation_a.slug, f"cohorts/{cohort_b.pk}")
        )

        assert response.status_code == 404

    def test_cohort_detail_404s_when_requested_through_organisation_b_itself(
        self, logged_in_client
    ):
        """The educator has no access to Organisation B at all, so even a
        URL naming B's own slug for B's own cohort still 404s."""
        _organisation_a, organisation_b, educator, cohort_b, _member_b = self._setup()
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation_b.slug, f"cohorts/{cohort_b.pk}")
        )

        assert response.status_code == 404

    def test_users_list_for_organisation_a_never_shows_organisation_bs_member(
        self, logged_in_client
    ):
        organisation_a, _organisation_b, educator, _cohort_b, member_b = self._setup()
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "users"))

        assert response.status_code == 200
        assert member_b.first_name.encode() not in response.content

    def test_user_detail_404s_when_requested_through_organisation_a(
        self, logged_in_client
    ):
        organisation_a, _organisation_b, educator, _cohort_b, member_b = self._setup()
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation_a.slug, f"users/{member_b.pk}")
        )

        assert response.status_code == 404

    def test_cohort_details_panel_fetch_404s_for_a_cohort_outside_organisation_a(
        self, logged_in_client
    ):
        organisation_a, _organisation_b, educator, cohort_b, _member_b = self._setup()
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(
                organisation_a.slug,
                f"cohorts/{cohort_b.pk}/__tabs/details/__panels/details",
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestGuardianGrantOnlyEducatorIsNotLockedOut:
    """No organisation role at all — only a per-cohort guardian grant. Must
    still be able to enter the interface, and must see exactly the cohorts
    they hold a grant on, nothing more."""

    def test_can_reach_the_bare_root_redirect(self, logged_in_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        educator = UserFactory(staff=True)
        assign_object_role(educator, cohort, "instructor")
        client = logged_in_client(educator)

        response = client.get(reverse("educator_interface:root"))

        assert response.status_code == 302
        assert organisation.slug in response.url

    def test_sees_exactly_the_granted_cohorts_and_no_others(self, logged_in_client):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Granted")
        CohortFactory(organisation=organisation, name="Not Granted")
        educator = UserFactory(staff=True)
        assign_object_role(educator, granted_cohort, "instructor")
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation.slug, "cohorts"))

        assert response.status_code == 200
        assert b"Granted" in response.content
        assert b"Not Granted" not in response.content

    def test_granted_cohorts_detail_page_is_reachable(self, logged_in_client):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Granted")
        educator = UserFactory(staff=True)
        assign_object_role(educator, granted_cohort, "instructor")
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation.slug, f"cohorts/{granted_cohort.pk}")
        )

        assert response.status_code == 200
