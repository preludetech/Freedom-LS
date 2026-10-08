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

Also: within a single organisation, a course-detail panel narrows further
still, to the cohorts and learners a cohort-scoped educator holds a grant on
-- not merely to the organisation as a whole.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.views import (
    CohortCourseRegistrationDataTable,
    CourseCohortRegistrationDataTable,
    CourseDataTable,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


def _course_panel_region_id(
    organisation_slug: str, course_pk: object, panel_name: str
) -> str:
    """The htmx target that fetches one course-detail panel's own region.

    Mirrors Panel.region_id (panel_framework/panels.py): a panel's region id
    is derived from its base_url, which nests the section's own URL under the
    course instance and then the child segment. Computed rather than
    hardcoded so it can never drift from the URLconf.
    """
    section_url = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": "courses"},
    )
    base_url = f"{section_url}/{course_pk}/__panels/{panel_name}"
    return "panel-" + re.sub(r"[^\w-]+", "-", base_url).strip("-")


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
        assign_object_role(educator, organisation_a, "organisation_admin")

        # Each Learner is built explicitly so the tests can address the row
        # itself: the detail URLs resolve a Learner pk, not a User pk.
        cohort_a = CohortFactory(organisation=organisation_a, name="Cohort A Only")
        member_a = UserFactory(first_name="MemberOfA", last_name="Only")
        learner_a = LearnerFactory(user=member_a, organisation=organisation_a)
        CohortMembershipFactory(cohort=cohort_a, learner=learner_a)

        cohort_b = CohortFactory(organisation=organisation_b, name="Cohort B Only")
        member_b = UserFactory(first_name="MemberOfB", last_name="Only")
        learner_b = LearnerFactory(user=member_b, organisation=organisation_b)
        CohortMembershipFactory(cohort=cohort_b, learner=learner_b)

        # A learner studying through both organisations -- one Learner row per
        # organisation for the one user. Visible to this educator through A, so
        # A's own list legitimately shows the row -- what must not appear in it
        # is anything belonging to B.
        shared = UserFactory(first_name="SharedBetween", last_name="Both")
        shared_in_a = LearnerFactory(user=shared, organisation=organisation_a)
        shared_in_b = LearnerFactory(user=shared, organisation=organisation_b)
        CohortMembershipFactory(cohort=cohort_a, learner=shared_in_a)
        CohortMembershipFactory(cohort=cohort_b, learner=shared_in_b)
        course_a = CourseFactory(title="Course A Only")
        course_b = CourseFactory(title="Course B Only")
        LearnerCourseRegistrationFactory(learner=shared_in_a, course=course_a)
        LearnerCourseRegistrationFactory(learner=shared_in_b, course=course_b)

        return SimpleNamespace(
            organisation_a=organisation_a,
            organisation_b=organisation_b,
            cohort_a=cohort_a,
            cohort_b=cohort_b,
            member_a=member_a,
            member_b=member_b,
            learner_a=learner_a,
            learner_b=learner_b,
            shared=shared,
            course_a=course_a,
            course_b=course_b,
            educator=educator,
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
            _interface_url(isolation.organisation_a.slug, "learners")
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
            _interface_url(isolation.organisation_a.slug, "learners")
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
            _interface_url(isolation.organisation_a.slug, "learners")
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert isolation.course_a.title in content
        assert isolation.course_b.title not in content

    def test_learner_detail_is_reachable_for_organisation_as_own_learner(
        self, isolation
    ):
        """The positive half of the pair below: without it, a 404 proves
        nothing about scoping."""
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug, f"learners/{isolation.learner_a.pk}"
            )
        )

        assert response.status_code == 200

    def test_learner_detail_404s_when_requested_through_organisation_a(self, isolation):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug, f"learners/{isolation.learner_b.pk}"
            )
        )

        assert response.status_code == 404

    def test_cohort_details_panel_fetch_404s_for_a_cohort_outside_organisation_a(
        self, isolation
    ):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug,
                f"cohorts/{isolation.cohort_b.pk}/__tabs/overview/__panels/details",
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "suffix",
        [
            "__tabs/settings",
            "__actions/deactivate",
            "__actions/reactivate",
            "__tabs/settings/__actions/delete",
        ],
    )
    def test_cohort_settings_surfaces_404_for_a_cohort_outside_organisation_a(
        self, isolation, suffix: str
    ):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug,
                f"cohorts/{isolation.cohort_b.pk}/{suffix}",
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "suffix", ["__tabs/courses", "__tabs/courses/__actions/register"]
    )
    def test_cohort_courses_surfaces_404_for_a_cohort_outside_organisation_a(
        self, isolation, suffix: str
    ):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug,
                f"cohorts/{isolation.cohort_b.pk}/{suffix}",
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    def test_register_post_naming_a_coming_soon_course_answers_422_with_no_row(
        self, isolation
    ):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        response = isolation.client.post(
            _interface_url(
                isolation.organisation_a.slug,
                f"cohorts/{isolation.cohort_a.pk}/__tabs/courses/__actions/register",
            ),
            {"course": str(course.pk)},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 422
        assert not isolation.cohort_a.course_registrations.filter(
            course=course
        ).exists()

    def test_register_post_naming_another_sites_course_answers_422_with_no_row(
        self, isolation
    ):
        course = CourseFactory(site=SiteFactory())

        response = isolation.client.post(
            _interface_url(
                isolation.organisation_a.slug,
                f"cohorts/{isolation.cohort_a.pk}/__tabs/courses/__actions/register",
            ),
            {"course": str(course.pk)},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 422
        assert not CohortCourseRegistration.objects.filter(course=course).exists()

    def test_cohort_educators_panel_fetch_404s_for_a_cohort_outside_organisation_a(
        self, isolation
    ):
        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug,
                f"cohorts/{isolation.cohort_b.pk}/__tabs/overview/__panels/educators",
            ),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404

    def test_courses_list_counts_and_links_only_organisation_as_cohorts(
        self, isolation: SimpleNamespace
    ) -> None:
        """Every course is listed, but its cohorts and learner counts are
        read through the organisation in view."""
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_a, course=isolation.course_a
        )
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_b, course=isolation.course_a
        )

        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, "courses")
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert isolation.course_a.title in content
        assert isolation.cohort_a.name in content
        assert isolation.cohort_b.name not in content

    def test_course_table_counts_read_through_the_organisation_in_view(
        self, isolation: SimpleNamespace
    ) -> None:
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_a, course=isolation.course_a
        )
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_b, course=isolation.course_a
        )
        request = RequestFactory().get("/")
        request.user = isolation.educator
        request.organisation = isolation.organisation_a

        query = CourseDataTable.parse_query(request, "courses")
        page = CourseDataTable.get_rows(
            request, CourseDataTable.get_queryset(request), query
        )

        (row,) = [row for row in page.object_list if row.pk == isolation.course_a.pk]
        assert row.cohort_count == 1
        # cohort_a holds learner_a and shared_in_a; learner_b and shared_in_b
        # sit in cohort_b and must not be counted, nor the direct
        # registration shared_in_b holds for course_b.
        assert row.total_learner_count == 2

    def test_course_detail_cohort_registrations_never_show_organisation_bs_cohort(
        self, isolation: SimpleNamespace
    ) -> None:
        """Courses are shared across organisations; the cohorts registered for
        one are not."""
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_a, course=isolation.course_a
        )
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_b, course=isolation.course_a
        )

        response = isolation.client.get(
            _interface_url(
                isolation.organisation_a.slug, f"courses/{isolation.course_a.pk}"
            )
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert isolation.cohort_a.name in content
        assert isolation.cohort_b.name not in content

    def test_hidden_course_registered_only_in_organisation_b_is_absent_from_as_list(
        self, isolation: SimpleNamespace
    ) -> None:
        hidden = CourseFactory(title="Hidden For B", visibility=CourseVisibility.HIDDEN)
        CohortCourseRegistrationFactory(cohort=isolation.cohort_b, course=hidden)

        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, "courses")
        )

        assert response.status_code == 200
        assert isolation.course_a.title in response.content.decode()
        assert hidden.title not in response.content.decode()

    def test_hidden_course_registered_only_in_organisation_b_404s_on_as_detail(
        self, isolation: SimpleNamespace
    ) -> None:
        hidden = CourseFactory(visibility=CourseVisibility.HIDDEN)
        CohortCourseRegistrationFactory(cohort=isolation.cohort_b, course=hidden)

        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, f"courses/{hidden.pk}")
        )

        assert response.status_code == 404

    def test_cohort_list_ignores_a_course_filter_outside_the_visible_courses(
        self, isolation: SimpleNamespace
    ) -> None:
        """A dropped filter leaves the list unfiltered, so A's cohort still
        shows, rather than the filter narrowing it to nothing."""
        hidden = CourseFactory(visibility=CourseVisibility.HIDDEN)
        CohortCourseRegistrationFactory(cohort=isolation.cohort_b, course=hidden)

        response = isolation.client.get(
            _interface_url(isolation.organisation_a.slug, "cohorts")
            + f"?cohorts-course={hidden.pk}"
        )

        assert response.status_code == 200
        assert isolation.cohort_a.name in response.content.decode()

    def test_course_list_and_detail_never_show_organisation_bs_people(
        self, isolation: SimpleNamespace
    ) -> None:
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_a, course=isolation.course_a
        )
        CohortCourseRegistrationFactory(
            cohort=isolation.cohort_b, course=isolation.course_a
        )
        LearnerCourseRegistrationFactory(
            learner=isolation.learner_b, course=isolation.course_a
        )

        pages = [
            isolation.client.get(
                _interface_url(isolation.organisation_a.slug, path)
            ).content.decode()
            for path in ("courses", f"courses/{isolation.course_a.pk}")
        ]

        assert all(isolation.cohort_b.name not in page for page in pages)
        assert all("MemberOfB" not in page for page in pages)

    @pytest.mark.parametrize(
        "data_table",
        [CohortCourseRegistrationDataTable, CourseCohortRegistrationDataTable],
        ids=lambda table: table.__name__,
    )
    def test_registration_table_excludes_another_organisations_rows(
        self, isolation: SimpleNamespace, data_table: type[DataTable]
    ) -> None:
        registration_a = CohortCourseRegistrationFactory(
            cohort=isolation.cohort_a, course=isolation.course_a
        )
        registration_b = CohortCourseRegistrationFactory(
            cohort=isolation.cohort_b, course=isolation.course_a
        )
        request = RequestFactory().get("/")
        request.organisation = isolation.organisation_a
        request.user = isolation.educator

        rows = set(data_table.get_queryset(request))

        assert registration_a in rows
        assert registration_b not in rows


@pytest.mark.django_db
class TestGuardianGrantOnlyEducatorIsNotLockedOut:
    """No organisation role at all — only a per-cohort guardian grant. Must
    still be able to enter the interface, and must see exactly the cohorts
    they hold a grant on, nothing more."""

    def test_can_reach_the_bare_root_redirect(self, logged_in_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        educator = UserFactory(staff=True)
        assign_object_role(educator, cohort, "cohort_admin")
        client = logged_in_client(educator)

        response = client.get(reverse("educator_interface:root"))

        assert response.status_code == 302
        assert organisation.slug in response.url

    def test_sees_exactly_the_granted_cohorts_and_no_others(self, logged_in_client):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
        CohortFactory(organisation=organisation, name="Beta Cohort")
        educator = UserFactory(staff=True)
        assign_object_role(educator, granted_cohort, "cohort_admin")
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
        assign_object_role(educator, granted_cohort, "cohort_admin")
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation.slug, f"cohorts/{granted_cohort.pk}")
        )

        assert response.status_code == 200

    def test_learners_list_cohort_cell_names_only_the_granted_cohort(
        self, logged_in_client
    ):
        """The learner row is legitimately visible through the granted cohort,
        but the Cohorts cell renders a relation of its own. Organisation
        scoping does not narrow it -- both cohorts belong to the same
        organisation -- so only the grant can."""
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
        ungranted_cohort = CohortFactory(organisation=organisation, name="Beta Cohort")
        learner = LearnerFactory(
            user=UserFactory(first_name="Studies", last_name="InBoth"),
            organisation=organisation,
        )
        CohortMembershipFactory(cohort=granted_cohort, learner=learner)
        CohortMembershipFactory(cohort=ungranted_cohort, learner=learner)
        educator = UserFactory(staff=True)
        assign_object_role(educator, granted_cohort, "cohort_admin")
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation.slug, "learners"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Studies" in content
        assert "Alpha Cohort" in content
        assert "Beta Cohort" not in content


@pytest.mark.django_db
class TestCourseDetailPanelsAreScopedWithinAnOrganisation:
    """One organisation, two cohorts. A cohort_admin holding a grant on only
    one of them must not see the other cohort's course registration, or that
    cohort's learner, on a course-detail panel -- even though both cohorts
    share the same organisation. An organisation_admin still sees both."""

    @pytest.fixture
    def scenario(self):
        organisation = OrganisationFactory()
        cohort_a = CohortFactory(organisation=organisation, name="Granted Cohort")
        cohort_b = CohortFactory(organisation=organisation, name="Other Cohort")
        course = CourseFactory()
        CohortCourseRegistrationFactory(cohort=cohort_a, course=course)
        CohortCourseRegistrationFactory(cohort=cohort_b, course=course)

        learner_a = LearnerFactory(
            user=UserFactory(first_name="InGrantedCohort", last_name="Learner"),
            organisation=organisation,
        )
        learner_b = LearnerFactory(
            user=UserFactory(first_name="InOtherCohort", last_name="Learner"),
            organisation=organisation,
        )
        CohortMembershipFactory(cohort=cohort_a, learner=learner_a)
        CohortMembershipFactory(cohort=cohort_b, learner=learner_b)
        LearnerCourseRegistrationFactory(learner=learner_a, course=course)
        LearnerCourseRegistrationFactory(learner=learner_b, course=course)

        return SimpleNamespace(
            organisation=organisation,
            cohort_a=cohort_a,
            cohort_b=cohort_b,
            learner_a=learner_a,
            learner_b=learner_b,
            course=course,
        )

    @staticmethod
    def _panel_content(
        client: Client, organisation_slug: str, course_pk: object, panel_name: str
    ) -> str:
        response = client.get(
            _interface_url(
                organisation_slug, f"courses/{course_pk}/__panels/{panel_name}"
            ),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET=_course_panel_region_id(
                organisation_slug, course_pk, panel_name
            ),
        )
        assert response.status_code == 200
        return response.content.decode()

    def test_cohort_admin_sees_only_the_granted_cohorts_registration(
        self, scenario: SimpleNamespace, logged_in_client
    ) -> None:
        educator = UserFactory(staff=True)
        assign_object_role(educator, scenario.cohort_a, "cohort_admin")
        client = logged_in_client(educator)

        content = self._panel_content(
            client, scenario.organisation.slug, scenario.course.pk, "cohorts"
        )

        assert scenario.cohort_a.name in content
        assert scenario.cohort_b.name not in content

    def test_cohort_admin_sees_only_the_granted_cohorts_learner(
        self, scenario: SimpleNamespace, logged_in_client
    ) -> None:
        educator = UserFactory(staff=True)
        assign_object_role(educator, scenario.cohort_a, "cohort_admin")
        client = logged_in_client(educator)

        content = self._panel_content(
            client, scenario.organisation.slug, scenario.course.pk, "learners"
        )

        assert scenario.learner_a.user.first_name in content
        assert scenario.learner_b.user.first_name not in content

    def test_organisation_admin_sees_both_cohorts_registrations(
        self, scenario: SimpleNamespace, logged_in_client
    ) -> None:
        educator = UserFactory(staff=True)
        assign_object_role(educator, scenario.organisation, "organisation_admin")
        client = logged_in_client(educator)

        content = self._panel_content(
            client, scenario.organisation.slug, scenario.course.pk, "cohorts"
        )

        assert scenario.cohort_a.name in content
        assert scenario.cohort_b.name in content

    def test_organisation_admin_sees_both_learners(
        self, scenario: SimpleNamespace, logged_in_client
    ) -> None:
        educator = UserFactory(staff=True)
        assign_object_role(educator, scenario.organisation, "organisation_admin")
        client = logged_in_client(educator)

        content = self._panel_content(
            client, scenario.organisation.slug, scenario.course.pk, "learners"
        )

        assert scenario.learner_a.user.first_name in content
        assert scenario.learner_b.user.first_name in content
