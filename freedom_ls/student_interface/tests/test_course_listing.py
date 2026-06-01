"""Unit tests for the get_course_listing helper (Task A1).

Tests cover every classification branch of the helper:
  - not registered
  - registered with 0% progress (CourseProgress row exists)
  - registered with missing CourseProgress row (still 0% → Registered)
  - in progress (>0%, completed_time is None)
  - complete (completed_time set)
  - cross-site isolation (a course on a different site must not appear)
"""

from __future__ import annotations

import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
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
