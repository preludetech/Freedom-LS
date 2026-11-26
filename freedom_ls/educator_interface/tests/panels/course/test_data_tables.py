from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import cast

import lxml.html
import pytest
import pytest_django.fixtures

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.core.paginator import Page
from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience, CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.educator_interface.panels.course.data_tables import CourseDataTable
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _interface_url,
    organisation_admin_viewer,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.retire import retire

# -- Task 5.1: visibility column + interest count -----------------------


def _organisation_request(
    site_aware_request: RequestFactory, organisation: Organisation | None = None
):
    """A request resolved onto an organisation, as interface() leaves it: the
    course table reads the organisation to scope its cohort and learner
    counts."""
    request = site_aware_request.get("/")
    request.user = UserFactory(superuser=True)
    request.organisation = organisation or OrganisationFactory()
    return request


def _find_row(page, course: Course):
    for row in page.object_list:
        if row.pk == course.pk:
            return row
    raise AssertionError("course not found in table rows")


@pytest.mark.django_db
def test_course_table_includes_visibility_label(
    mock_site_context: Site, site_aware_request: RequestFactory
) -> None:
    """Each course row exposes its visibility human label."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    request = _organisation_request(site_aware_request)
    query = CourseDataTable.parse_query(request, "courses")
    page = CourseDataTable.get_rows(
        request, CourseDataTable.get_queryset(request), query
    )

    row = _find_row(page, course)
    assert row.get_visibility_display() == "Coming soon"


@pytest.mark.django_db
def test_course_table_interest_count_matches_interest_rows(
    mock_site_context: Site, site_aware_request: RequestFactory
) -> None:
    """The annotated interest count equals the number of CourseInterest rows."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    CourseInterestFactory(course=course, user=UserFactory())
    CourseInterestFactory(course=course, user=UserFactory())

    other_course = CourseFactory()
    CourseInterestFactory(course=other_course, user=UserFactory())

    request = _organisation_request(site_aware_request)
    query = CourseDataTable.parse_query(request, "courses")
    page = CourseDataTable.get_rows(
        request, CourseDataTable.get_queryset(request), query
    )

    assert _find_row(page, course).interest_count == 2
    assert _find_row(page, other_course).interest_count == 1


@pytest.mark.django_db
def test_course_table_interest_count_is_site_scoped(
    mock_site_context: Site, site_aware_request: RequestFactory
) -> None:
    """Interest on a course belonging to another site never leaks into the table."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    CourseInterestFactory(course=course, user=UserFactory())

    other_site = SiteFactory(name="OtherSite")
    other_course = CourseFactory(site=other_site)
    CourseInterestFactory(
        course=other_course,
        user=UserFactory(site=other_site),
        site=other_site,
    )

    request = _organisation_request(site_aware_request)
    query = CourseDataTable.parse_query(request, "courses")
    page = CourseDataTable.get_rows(
        request, CourseDataTable.get_queryset(request), query
    )

    row_pks = {row.pk for row in page.object_list}
    assert other_course.pk not in row_pks
    assert _find_row(page, course).interest_count == 1


@pytest.mark.django_db
def test_course_table_renders_visibility_and_interest_columns(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    """The rendered table shows the visibility label and interest count."""
    course = CourseFactory(
        title="Demand Course", visibility=CourseVisibility.COMING_SOON
    )
    CourseInterestFactory(course=course, user=UserFactory())
    organisation = OrganisationFactory()
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_admin")
    CohortCourseRegistrationFactory(
        cohort=CohortFactory(organisation=organisation), course=course
    )

    html = (
        logged_in_client(educator)
        .get(
            reverse(
                "educator_interface:interface",
                kwargs={
                    "organisation_slug": organisation.slug,
                    "path_string": "courses",
                },
            )
        )
        .content.decode()
    )

    assert "Coming soon" in html
    assert "Interest" in html
    assert "Visibility" in html


# -- Query cost: total_learner_count must not grow with N ---------------


def _add_registrations(course: Course, organisation: Organisation, count: int) -> None:
    """Give ``course`` ``count`` cohort registrations and ``count`` direct ones,
    each held by a learner of its own."""
    for _ in range(count):
        cohort = CohortFactory(organisation=organisation, name=f"Cohort {uuid.uuid4()}")
        CohortMembershipFactory(cohort=cohort, learner__organisation=organisation)
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
        LearnerCourseRegistrationFactory(
            learner__organisation=organisation, course=course, is_active=True
        )


@pytest.mark.django_db
class TestCourseTableTotalLearnerCountQueryCost:
    """total_learner_count unions cohort members with direct registrants to
    count unique people. The prefetch in CourseDataTable.get_queryset is what
    keeps that union's cost from growing with how many cohorts or direct
    registrations a course carries."""

    @pytest.mark.parametrize("registration_count", [1, 4])
    def test_query_count_does_not_grow_with_registration_count(
        self,
        mock_site_context: Site,
        site_aware_request: RequestFactory,
        django_assert_max_num_queries: pytest_django.fixtures.DjangoAssertNumQueries,
        registration_count: int,
    ) -> None:
        course = CourseFactory()
        organisation = OrganisationFactory()
        _add_registrations(course, organisation, registration_count)

        request = _organisation_request(site_aware_request, organisation)
        query = CourseDataTable.parse_query(request, "courses")

        with django_assert_max_num_queries(8):
            CourseDataTable.get_rows(
                request, CourseDataTable.get_queryset(request), query
            )


@pytest.mark.django_db
class TestInactiveCohortsDoNotCountAsActive:
    def test_active_cohorts_and_learners_skip_an_inactive_cohort(
        self, mock_site_context: Site, site_aware_request: RequestFactory
    ) -> None:
        organisation = OrganisationFactory()
        course = CourseFactory()
        active = CohortFactory(organisation=organisation)
        inactive = CohortFactory(organisation=organisation, is_active=False)
        CohortMembershipFactory(cohort=active, learner__organisation=organisation)
        CohortMembershipFactory(cohort=inactive, learner__organisation=organisation)
        CohortCourseRegistrationFactory(cohort=active, course=course)
        CohortCourseRegistrationFactory(cohort=inactive, course=course)
        request = _organisation_request(site_aware_request, organisation)
        query = CourseDataTable.parse_query(request, "courses")

        page = CourseDataTable.get_rows(
            request, CourseDataTable.get_queryset(request), query
        )

        row = _find_row(page, course)
        assert row.cohort_count == 1
        assert row.total_learner_count == 1


@pytest.mark.django_db
def test_course_page_cohort_table_shows_cohort_status_and_registration_status(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_admin")
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation, is_active=False)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)

    document = lxml.html.fromstring(
        logged_in_client(educator)
        .get(
            reverse(
                "educator_interface:interface",
                kwargs={
                    "organisation_slug": organisation.slug,
                    "path_string": f"courses/{course.pk}",
                },
            )
        )
        .content.decode()
    )

    headers = [th.text_content().strip() for th in document.cssselect("th")]
    badges = [b.text_content().strip() for b in document.cssselect("td span")]
    assert "Cohort status" in headers
    assert "Status" in headers
    assert "Inactive" in badges
    assert "Active" in badges


@pytest.mark.django_db
def test_the_courses_list_renders_its_empty_state_when_no_course_is_available(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    organisation = OrganisationFactory()
    CourseFactory(audience=CourseAudience.PUBLIC).organisations.add(
        OrganisationFactory()
    )
    client = logged_in_client(organisation_admin_viewer(organisation))

    response = client.get(_interface_url(organisation.slug, "courses"))

    assert CourseDataTable.empty_message in response.content.decode()


@pytest.mark.django_db
def test_courses_list_names_the_owner_under_a_shared_course_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    """Two courses with one title looked identical in the Title column."""
    organisation = OrganisationFactory(name="Harbour College")
    own = CourseFactory(title="Own Safety", audience=CourseAudience.PUBLIC)
    own.organisations.add(organisation)
    shared = CourseFactory(title="Shared Safety", audience=CourseAudience.PUBLIC)
    shared.organisations.add(OrganisationFactory(name="Northwind Logistics"))
    shared.shared_with.add(organisation)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(client, _interface_url(organisation.slug, "courses"))

    notes = {
        element.text_content().strip()
        for element in document.cssselect("[data-testid='shared-by']")
    }
    assert notes == {"Shared by Northwind Logistics"}


def _badge_labels(page: Page, course: Course) -> list[str]:
    column = next(c for c in CourseDataTable.get_columns() if c.header == "Status")
    badge = column.badge(_find_row(page, course))
    return [badge.label] if badge else []


@pytest.mark.django_db
def test_course_table_lists_a_retired_course_with_a_retired_badge(
    mock_site_context: Site, site_aware_request: RequestFactory
) -> None:
    course = retire(cast(Course, CourseFactory()))

    request = _organisation_request(site_aware_request)
    query = CourseDataTable.parse_query(request, "courses")
    page = CourseDataTable.get_rows(
        request, CourseDataTable.get_queryset(request), query
    )

    assert _badge_labels(page, course) == ["Retired"]


@pytest.mark.django_db
def test_course_table_shows_no_badge_for_a_live_course(
    mock_site_context: Site, site_aware_request: RequestFactory
) -> None:
    course = CourseFactory()

    request = _organisation_request(site_aware_request)
    query = CourseDataTable.parse_query(request, "courses")
    page = CourseDataTable.get_rows(
        request, CourseDataTable.get_queryset(request), query
    )

    assert _badge_labels(page, course) == []


@pytest.mark.django_db
def test_course_cards_leave_out_the_status_label_for_a_live_course(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    """A live course's card showed a bare "Status" label with no value beside it."""
    organisation = OrganisationFactory()
    live = CourseFactory(title="Live Safety")
    live.organisations.add(organisation)
    gone = retire(cast(Course, CourseFactory(title="Gone Safety")))
    gone.organisations.add(organisation)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(client, _interface_url(organisation.slug, "courses"))

    status_labels_by_card = {
        "Gone Safety" in card.text_content(): [
            dt.text_content().strip()
            for dt in card.cssselect("dt")
            if dt.text_content().strip() == "Status"
        ]
        for card in document.cssselect("li.panel-data-table-card")
    }
    assert status_labels_by_card == {True: ["Status"], False: []}
