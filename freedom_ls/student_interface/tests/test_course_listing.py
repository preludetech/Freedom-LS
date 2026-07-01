"""Unit tests for the get_course_listing helper (Task A1).

Tests cover every classification branch of the helper:
  - not registered
  - registered with 0% progress (CourseProgress row exists)
  - registered with missing CourseProgress row (still 0% → Registered)
  - in progress (>0%, completed_time is None)
  - complete (completed_time set)
  - cross-site isolation (a course on a different site must not appear)
  - anonymous users respect filter_visible (hidden courses not leaked)
"""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.student_interface.utils import (
    CourseListingEntry,
    CourseListingStatus,
    get_course_listing,
)
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_progress.factories import CourseProgressFactory


@pytest.mark.django_db
def test_unregistered_course_has_not_registered_status(mock_site_context):
    """A course with no registration is classified as NOT_REGISTERED with 0% progress."""
    user = UserFactory()
    course = CourseFactory()

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.NOT_REGISTERED
    assert entry.progress_percentage == 0


@pytest.mark.django_db
def test_registered_zero_percent_course_has_registered_status(mock_site_context):
    """A registered course with a 0% CourseProgress row is classified as REGISTERED."""
    user = UserFactory()
    course = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    CourseProgressFactory(user=user, course=course, progress_percentage=0)

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.REGISTERED
    assert entry.progress_percentage == 0


@pytest.mark.django_db
def test_registered_missing_progress_row_has_registered_status(mock_site_context):
    """A registered course with no CourseProgress row is treated as 0% → REGISTERED."""
    user = UserFactory()
    course = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    # Deliberately no CourseProgressFactory call — row is absent.

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.REGISTERED
    assert entry.progress_percentage == 0


@pytest.mark.django_db
def test_in_progress_course_has_in_progress_status(mock_site_context):
    """A registered course with >0% progress and no completed_time is IN_PROGRESS."""
    user = UserFactory()
    course = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    CourseProgressFactory(
        user=user, course=course, progress_percentage=50, completed_time=None
    )

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.IN_PROGRESS
    assert entry.progress_percentage == 50


@pytest.mark.django_db
def test_completed_course_has_complete_status(mock_site_context):
    """A registered course with completed_time set is classified as COMPLETE."""
    user = UserFactory()
    course = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    CourseProgressFactory(
        user=user,
        course=course,
        progress_percentage=100,
        completed_time=timezone.now(),
    )

    entries = get_course_listing(user)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.course == course
    assert entry.status == CourseListingStatus.COMPLETE
    assert entry.progress_percentage == 100


@pytest.mark.django_db
def test_course_on_different_site_excluded_from_listing(mock_site_context):
    """A course belonging to a different site must not appear in the listing.

    This proves that cross-site data does not leak through get_all_courses(),
    get_course_registrations(), or the CourseProgress read.
    """
    user = UserFactory()
    current_site_course = CourseFactory()

    # Create a course on a completely different site (outside mock_site_context).
    other_site = SiteFactory(name="OtherSite")
    other_site_course = CourseFactory(site=other_site)

    entries = get_course_listing(user)

    entry_courses = [e.course for e in entries]
    assert current_site_course in entry_courses
    assert other_site_course not in entry_courses


@pytest.mark.django_db
def test_get_course_listing_returns_course_listing_entries(mock_site_context):
    """get_course_listing returns a list of CourseListingEntry instances."""
    user = UserFactory()
    CourseFactory()

    entries = get_course_listing(user)

    assert isinstance(entries, list)
    assert all(isinstance(e, CourseListingEntry) for e in entries)


@pytest.mark.django_db
def test_multiple_courses_all_classified_independently(mock_site_context):
    """With three courses in different states, each is classified correctly."""
    user = UserFactory()

    not_registered_course = CourseFactory()

    registered_course = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=registered_course)

    complete_course = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=complete_course)
    CourseProgressFactory(
        user=user,
        course=complete_course,
        progress_percentage=100,
        completed_time=timezone.now(),
    )

    entries = get_course_listing(user)
    by_course = {e.course.id: e for e in entries}

    assert (
        by_course[not_registered_course.id].status == CourseListingStatus.NOT_REGISTERED
    )
    assert by_course[registered_course.id].status == CourseListingStatus.REGISTERED
    assert by_course[complete_course.id].status == CourseListingStatus.COMPLETE


@pytest.mark.django_db
def test_anonymous_user_respects_visible_courses_filter(mock_site_context):
    """Anonymous branch of get_course_listing must honour the visible_courses argument.

    A backend that overrides filter_visible to hide a course must not leak that
    course to anonymous visitors. Previously the anonymous branch unconditionally
    iterated get_all_courses(), ignoring visible_courses entirely.
    """
    visible_course = CourseFactory()
    hidden_course = CourseFactory()

    # Simulate a backend whose filter_visible drops hidden_course.
    visible_qs: QuerySet[Course] = Course.objects.filter(pk=visible_course.pk)

    anon = AnonymousUser()
    entries = get_course_listing(anon, visible_courses=visible_qs)

    entry_courses = [e.course for e in entries]
    assert visible_course in entry_courses
    assert hidden_course not in entry_courses


@pytest.mark.django_db
def test_authenticated_listing_query_count_does_not_scale_with_courses(
    mock_site_context,
):
    """The authenticated listing must not issue registration queries per course.

    Regression guard: the access badge comes from the config-only
    backend.get_access_badge (no per-user queries), so the query count for a
    large catalogue must equal that of a small one.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    user = UserFactory()

    CourseFactory()
    with CaptureQueriesContext(connection) as few:
        get_course_listing(user)
    few_count = len(few.captured_queries)

    for _ in range(9):
        CourseFactory()
    with CaptureQueriesContext(connection) as many:
        get_course_listing(user)
    many_count = len(many.captured_queries)

    # 1 course vs 10 courses must issue the same number of queries — a per-course
    # backend.get_access would have added ~2 registration exists() queries each.
    assert many_count == few_count
