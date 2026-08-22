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

from types import SimpleNamespace

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role


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
    @pytest.fixture
    def isolation(self, logged_in_client):
        """Two organisations, an educator with a role on A only, and one
        cohort plus one member in each -- so every assertion below can pair
        "B's thing is absent" with "A's thing is present", and an empty page
        cannot pass for isolation."""
        organisation_a = OrganisationFactory(name="Org A")
        organisation_b = OrganisationFactory(name="Org B")
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation_a, "organisation_staff")

        cohort_a = CohortFactory(organisation=organisation_a, name="Cohort A Only")
        member_a = UserFactory(first_name="MemberOfA", last_name="Only")
        CohortMembershipFactory(cohort=cohort_a, user=member_a)

        cohort_b = CohortFactory(organisation=organisation_b, name="Cohort B Only")
        member_b = UserFactory(first_name="MemberOfB", last_name="Only")
        CohortMembershipFactory(cohort=cohort_b, user=member_b)

        # A learner studying through both organisations. Visible to this
        # educator through A, so A's own list legitimately shows the row --
        # what must not appear in it is anything belonging to B.
        shared = UserFactory(first_name="SharedBetween", last_name="Both")
        CohortMembershipFactory(cohort=cohort_a, user=shared)
        CohortMembershipFactory(cohort=cohort_b, user=shared)
        course_a = CourseFactory(title="Course A Only")
        course_b = CourseFactory(title="Course B Only")
        UserCourseRegistrationFactory(
            user=shared, organisation=organisation_a, collection=course_a
        )
        UserCourseRegistrationFactory(
            user=shared, organisation=organisation_b, collection=course_b
        )

        return SimpleNamespace(
            organisation_a=organisation_a,
            organisation_b=organisation_b,
            cohort_a=cohort_a,
            cohort_b=cohort_b,
            member_a=member_a,
            member_b=member_b,
            shared=shared,
            course_a=course_a,
            course_b=course_b,
            client=logged_in_client(educator),
        )

    def test_cohorts_list_for_organisation_a_never_shows_organisation_bs_cohort(
        self, isolation
    ):
        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, "cohorts")
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert isolation.cohort_a.name in content
        assert isolation.cohort_b.name not in content

    def test_cohort_detail_404s_when_requested_through_organisation_a(self, isolation):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug, f"cohorts/{isolation.cohort_b.pk}"
            )
        )

        assert response.status_code == 404

    def test_users_list_for_organisation_a_never_shows_organisation_bs_member(
        self, isolation
    ):
        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, "users")
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert isolation.member_a.first_name in content
        assert isolation.member_b.first_name not in content

    def test_users_list_cohort_cell_never_names_a_cohort_from_organisation_b(
        self, isolation
    ):
        """The row for a learner shared between both organisations is scoped,
        but the Cohorts cell renders a relation of its own that is not."""
        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, "users")
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert isolation.shared.first_name in content
        assert isolation.cohort_a.name in content
        assert isolation.cohort_b.name not in content

    def test_users_list_course_cell_never_names_a_course_registered_through_b(
        self, isolation
    ):
        """Same leak, through the Registered Courses cell."""
        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, "users")
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert isolation.course_a.title in content
        assert isolation.course_b.title not in content

    def test_user_detail_404s_when_requested_through_organisation_a(self, isolation):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug, f"users/{isolation.member_b.pk}"
            )
        )

        assert response.status_code == 404

    def test_cohort_details_panel_fetch_404s_for_a_cohort_outside_organisation_a(
        self, isolation
    ):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug,
                f"cohorts/{isolation.cohort_b.pk}/__tabs/details/__panels/details",
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
        granted_cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
        CohortFactory(organisation=organisation, name="Beta Cohort")
        educator = UserFactory(staff=True)
        assign_object_role(educator, granted_cohort, "instructor")
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation.slug, "cohorts"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Alpha Cohort" in content
        assert "Beta Cohort" not in content

    def test_granted_cohorts_detail_page_is_reachable(self, logged_in_client):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
        educator = UserFactory(staff=True)
        assign_object_role(educator, granted_cohort, "instructor")
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation.slug, f"cohorts/{granted_cohort.pk}")
        )

        assert response.status_code == 200
