from __future__ import annotations

import uuid

import pytest

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.educator_interface.views import CourseDataTable
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.organisations.factories import OrganisationFactory

# Direct-creation stopgap for Learner-based enrolment models: learner_management
# factories still import the pre-rename model names and are rewritten in a
# later batch, so those factories cannot be used here yet.

# -- Task 5.1: visibility column + interest count -----------------------


def _find_row(page, course: Course):
    for row in page.object_list:
        if row.pk == course.pk:
            return row
    raise AssertionError("course not found in table rows")


@pytest.mark.django_db
def test_course_table_includes_visibility_label(mock_site_context, site_aware_request):
    """Each course row exposes its visibility human label."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    request = site_aware_request.get("/")
    columns = CourseDataTable._prepare_columns()
    page = CourseDataTable.get_rows(request, columns)

    row = _find_row(page, course)
    assert row.get_visibility_display() == "Coming soon"


@pytest.mark.django_db
def test_course_table_interest_count_matches_interest_rows(
    mock_site_context, site_aware_request
):
    """The annotated interest count equals the number of CourseInterest rows."""
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    CourseInterestFactory(course=course, user=UserFactory())
    CourseInterestFactory(course=course, user=UserFactory())

    other_course = CourseFactory()
    CourseInterestFactory(course=other_course, user=UserFactory())

    request = site_aware_request.get("/")
    columns = CourseDataTable._prepare_columns()
    page = CourseDataTable.get_rows(request, columns)

    assert _find_row(page, course).interest_count == 2
    assert _find_row(page, other_course).interest_count == 1


@pytest.mark.django_db
def test_course_table_interest_count_is_site_scoped(
    mock_site_context, site_aware_request
):
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

    request = site_aware_request.get("/")
    columns = CourseDataTable._prepare_columns()
    page = CourseDataTable.get_rows(request, columns)

    row_pks = {row.pk for row in page.object_list}
    assert other_course.pk not in row_pks
    assert _find_row(page, course).interest_count == 1


@pytest.mark.django_db
def test_course_table_renders_visibility_and_interest_columns(
    mock_site_context, panel_request
):
    """The rendered table shows the visibility label and interest count."""
    course = CourseFactory(
        title="Demand Course", visibility=CourseVisibility.COMING_SOON
    )
    CourseInterestFactory(course=course, user=UserFactory())

    html = CourseDataTable.render(panel_request())

    assert "Coming soon" in html
    assert "Interest" in html
    assert "Visibility" in html


# -- Query cost: total_learner_count must not grow with N ---------------


@pytest.mark.django_db
class TestCourseTableTotalLearnerCountQueryCost:
    """total_learner_count unions cohort members with direct registrants to
    count unique people. The prefetch in CourseDataTable.get_queryset is what
    keeps that union's cost from growing with how many cohorts or direct
    registrations a course carries."""

    @pytest.mark.parametrize("registration_count", [1, 4])
    def test_query_count_does_not_grow_with_registration_count(
        self,
        mock_site_context,
        site_aware_request,
        django_assert_max_num_queries,
        registration_count,
    ):
        course = CourseFactory()
        organisation = OrganisationFactory()
        for _ in range(registration_count):
            cohort = Cohort.objects.create(
                organisation=organisation, name=f"Cohort {uuid.uuid4()}"
            )
            cohort_learner = Learner.objects.create(
                user=UserFactory(), organisation=organisation
            )
            CohortMembership.objects.create(learner=cohort_learner, cohort=cohort)
            CohortCourseRegistration.objects.create(cohort=cohort, collection=course)

            direct_learner = Learner.objects.create(
                user=UserFactory(), organisation=organisation
            )
            LearnerCourseRegistration.objects.create(
                learner=direct_learner, collection=course, is_active=True
            )

        request = site_aware_request.get("/")
        columns = CourseDataTable._prepare_columns()

        with django_assert_max_num_queries(8):
            CourseDataTable.get_rows(request, columns)


def test_course_instance_view_has_no_interest_panel():
    """The interested-learners drill-down panel is gone; CourseInterest is
    curated through the Django admin instead."""
    from freedom_ls.educator_interface.views import CourseInstanceView

    assert "interest" not in CourseInstanceView.panels


# -- Task 5.3: visibility is content-file-only, not educator/admin editable --


def test_course_details_panel_does_not_edit_visibility():
    """The educator course details panel never exposes visibility for editing."""
    from freedom_ls.educator_interface.views import CourseDetailsPanel

    assert "visibility" not in CourseDetailsPanel.fields
