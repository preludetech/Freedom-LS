"""Tests for course helper functions in learner_interface.utils."""

from datetime import UTC, datetime, timedelta

import pytest

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.resolver import (
    NO_DEADLINE,
    CourseDeadlines,
    DeadlineSource,
    ResolvedDeadline,
)
from freedom_ls.learner_interface.tests.helpers import topic_completion
from freedom_ls.learner_interface.utils import (
    get_all_courses,
    get_completed_courses,
    get_course_index,
    get_current_courses,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.tests.helpers import course_progress_record

# --- get_all_courses ---


@pytest.mark.django_db
def test_get_all_courses_returns_all(mock_site_context):
    """get_all_courses returns all courses regardless of user."""
    courses = CourseFactory.create_batch(3)
    result = get_all_courses()
    # get_all_courses carries no ordering contract, so compare membership
    # rather than row order.
    assert set(result) == set(courses)


@pytest.mark.django_db
def test_get_all_courses_returns_empty_when_none_exist(mock_site_context):
    """get_all_courses returns empty queryset when no courses exist."""
    result = get_all_courses()
    assert list(result) == []


# --- get_completed_courses ---


@pytest.mark.django_db
def test_get_completed_courses_anonymous_user(mock_site_context):
    """get_completed_courses returns empty list for anonymous user."""
    CourseFactory.create_batch(2)
    result = get_completed_courses(AnonymousUser())
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_user_without_registrations(mock_site_context):
    """get_completed_courses returns empty list for user without registrations."""
    CourseFactory.create_batch(2)
    user = UserFactory()
    result = get_completed_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_no_completed(mock_site_context):
    """get_completed_courses returns empty list when no courses are completed."""
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    result = get_completed_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_returns_completed(mock_site_context):
    """get_completed_courses returns only completed courses."""
    user = UserFactory()
    course_a = CourseFactory()
    course_b = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_a)
    LearnerCourseRegistrationFactory(learner__user=user, course=course_b)

    # Complete course_a only
    course_progress_record(course_a, user, completed_time=timezone.now())

    result = get_completed_courses(user)
    assert result == [course_a]


# --- get_current_courses ---


@pytest.mark.django_db
def test_get_current_courses_anonymous_user(mock_site_context):
    """get_current_courses returns empty list for anonymous user."""
    CourseFactory.create_batch(2)
    result = get_current_courses(AnonymousUser())
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_user_without_registrations(mock_site_context):
    """get_current_courses returns empty list for user without registrations."""
    CourseFactory.create_batch(2)
    user = UserFactory()
    result = get_current_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_returns_non_completed_registered(mock_site_context):
    """get_current_courses returns registered courses that are not completed."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    result = get_current_courses(user)
    assert len(result) == 1
    assert result[0] == course


@pytest.mark.django_db
def test_get_current_courses_excludes_completed(mock_site_context):
    """get_current_courses excludes courses that are completed."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    course_progress_record(course, user, completed_time=timezone.now())

    result = get_current_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_have_progress_percentage(mock_site_context):
    """get_current_courses attaches progress_percentage to each course."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    result = get_current_courses(user)
    assert len(result) == 1
    assert result[0].progress_percentage == 0


# --- get_course_index deadline keys ---


def _resolved(due_at: datetime | None) -> ResolvedDeadline:
    return ResolvedDeadline(due_at, DeadlineSource.CONTENT, False)


@pytest.mark.django_db
def test_get_course_index_rows_carry_the_collection_item_id_and_deadline(
    mock_site_context,
):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    record = course_progress_record(course, user)
    item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        now=due + timedelta(days=1),
    )

    assert row["collection_item_id"] == item.pk
    assert row["due_at"] == due
    assert row["is_overdue"] is True


@pytest.mark.django_db
def test_get_course_index_row_is_not_overdue_before_the_due_instant(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    record = course_progress_record(course, user)
    item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        now=due - timedelta(days=1),
    )

    assert row["due_at"] == due
    assert row["is_overdue"] is False


@pytest.mark.django_db
def test_get_course_index_completed_row_is_not_overdue(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    topic_completion(course, user, topic, complete_time=timezone.now())
    record = course_progress_record(course, user)
    item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        now=due + timedelta(days=1),
    )

    assert row["status"] == "COMPLETE"
    assert row["is_overdue"] is False


@pytest.mark.django_db
def test_get_course_index_without_deadlines_carries_no_date(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)

    (row,) = get_course_index(user, course, can_access_content=True)

    assert row["due_at"] is None
    assert row["is_overdue"] is False


@pytest.mark.django_db
def test_get_course_index_part_rows_carry_no_due_at_but_their_children_do(
    mock_site_context,
):
    user = UserFactory()
    course = CourseFactory()
    part = CoursePartFactory()
    topic = TopicFactory()
    course.items.create(child=part, order=0)
    part.items.create(child=topic, order=0)
    record = course_progress_record(course, user)
    part_item = course.collection_items()[0]
    topic_item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (part_row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={topic_item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        now=due,
    )

    assert part_row["collection_item_id"] == part_item.pk
    assert "due_at" not in part_row
    assert part_row["children"][0]["due_at"] == due
    assert part_row["children"][0]["collection_item_id"] == topic_item.pk
