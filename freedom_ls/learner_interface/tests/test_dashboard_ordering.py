"""Tests for the deterministic ordering of in-progress, completed and
recommended courses on the learner dashboard.
"""

import datetime

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.learner_interface.utils import (
    get_completed_courses,
    get_current_courses,
)
from freedom_ls.learner_interface.views import _visible_recommendations
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

from .conftest import course_progress_record


def _at(day: int) -> datetime.datetime:
    return datetime.datetime(2026, 1, day, tzinfo=datetime.UTC)


# --- get_current_courses ---


@pytest.mark.django_db
def test_started_course_ranks_before_unstarted_course_regardless_of_registration_order(
    mock_site_context,
):
    """A started course outranks an unstarted one even when registered later."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    # course_b is registered first, course_a second -- registration order
    # runs the opposite way to the expected result.
    LearnerCourseRegistrationFactory(learner__user=user, course=course_b)
    course_progress_record(course_a, user, started_at=_at(2))

    result = get_current_courses(user)

    assert result == [course_a, course_b]


@pytest.mark.django_db
def test_started_courses_order_by_most_recent_access(mock_site_context):
    """Within the started bucket, the most recently accessed course leads."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    # course_b started later than course_a but was accessed earlier, so a
    # sort on started_at would rank it first -- ranking must follow
    # last_accessed_time instead.
    course_progress_record(
        course_a, user, started_at=_at(1), last_accessed_time=_at(10)
    )
    course_progress_record(course_b, user, started_at=_at(5), last_accessed_time=_at(2))

    result = get_current_courses(user)

    assert result == [course_a, course_b]


@pytest.mark.django_db
def test_unstarted_courses_order_by_newest_registration(mock_site_context):
    """Within the unstarted bucket, the most recently registered course leads."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    # Both courses have a record (so registered_at is set) but neither has
    # been started.
    course_progress_record(course_a, user, created_at=_at(1))
    course_progress_record(course_b, user, created_at=_at(5))

    result = get_current_courses(user)

    assert result == [course_b, course_a]


# --- get_completed_courses (learning history) ---


@pytest.mark.django_db
def test_learning_history_orders_by_completion_date_descending(mock_site_context):
    """Completed courses list most recently completed first."""
    user = UserFactory()
    course_a = CourseFactory(title="Course A", slug="course-a")
    course_b = CourseFactory(title="Course B", slug="course-b")

    course_progress_record(course_a, user, completed_time=_at(1))
    course_progress_record(course_b, user, completed_time=_at(10))

    result = get_completed_courses(user)

    assert result == [course_b, course_a]


# --- _visible_recommendations ---


@pytest.mark.django_db
def test_recommended_courses_order_newest_first(mock_site_context):
    """Recommendations list the most recently recommended course first."""
    user = UserFactory()
    course_a: Course = CourseFactory(title="Course A", slug="course-a")
    course_b: Course = CourseFactory(title="Course B", slug="course-b")
    older = RecommendedCourseFactory(user=user, course=course_a)
    newer = RecommendedCourseFactory(user=user, course=course_b)
    older.created_at = _at(1)
    older.save(update_fields=["created_at"])
    newer.created_at = _at(10)
    newer.save(update_fields=["created_at"])

    result = _visible_recommendations(user, get_course_access_backend())

    assert [rec.course for rec in result] == [course_b, course_a]


@pytest.mark.django_db
def test_recommended_courses_tie_broken_by_course_slug(mock_site_context):
    """Recommendations created at the same instant fall back to course slug."""
    user = UserFactory()
    course_z: Course = CourseFactory(title="Course Z", slug="course-z")
    course_a: Course = CourseFactory(title="Course A", slug="course-a")
    same_moment = _at(1)
    rec_z = RecommendedCourseFactory(user=user, course=course_z)
    rec_a = RecommendedCourseFactory(user=user, course=course_a)
    rec_z.created_at = same_moment
    rec_z.save(update_fields=["created_at"])
    rec_a.created_at = same_moment
    rec_a.save(update_fields=["created_at"])

    result = _visible_recommendations(user, get_course_access_backend())

    assert [rec.course for rec in result] == [course_a, course_z]
