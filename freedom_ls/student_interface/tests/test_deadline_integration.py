import pytest
from datetime import timedelta
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.student_management.factories import (
    StudentFactory,
    CohortFactory,
    CohortMembershipFactory,
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
)
from freedom_ls.student_interface.utils import get_course_index, BLOCKED


@pytest.fixture
def course(mock_site_context):
    return CourseFactory(title="Test Course", slug="test-course")


@pytest.fixture
def topic(mock_site_context):
    return TopicFactory(title="Test Topic", slug="test-topic")


@pytest.fixture
def student(mock_site_context):
    return StudentFactory()


@pytest.fixture
def cohort(mock_site_context):
    return CohortFactory(name="Test Cohort")


@pytest.fixture
def setup_cohort_registration(mock_site_context, student, cohort, course):
    """Set up student in a cohort registered for a course."""
    CohortMembershipFactory(student=student, cohort=cohort)
    return CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_course_index_includes_deadline_data(
    mock_site_context, student, course, topic, setup_cohort_registration
):
    """get_course_index includes deadline info in child dicts."""
    course.items.create(child=topic, order=0)
    deadline_dt = timezone.now() + timedelta(days=7)

    CohortDeadlineFactory(
        cohort_course_registration=setup_cohort_registration,
        content_item=topic,
        deadline=deadline_dt,
    )

    children = get_course_index(user=student.user, course=course)

    assert len(children) == 1
    assert "deadlines" in children[0]
    assert len(children[0]["deadlines"]) == 1
    assert children[0]["deadlines"][0]["deadline"] == deadline_dt


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_expired_hard_deadline_locks_incomplete_item(
    mock_site_context, student, course, topic, setup_cohort_registration
):
    """Expired hard deadline + incomplete item = BLOCKED with no URL."""
    course.items.create(child=topic, order=0)

    CohortDeadlineFactory(
        cohort_course_registration=setup_cohort_registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    children = get_course_index(user=student.user, course=course)

    assert children[0]["status"] == BLOCKED
    assert children[0]["url"] is None


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_soft_deadline_does_not_lock(
    mock_site_context, student, course, topic, setup_cohort_registration
):
    """Soft deadlines never change the access status."""
    course.items.create(child=topic, order=0)

    CohortDeadlineFactory(
        cohort_course_registration=setup_cohort_registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=False,
    )

    children = get_course_index(user=student.user, course=course)

    # First item should be READY, not BLOCKED
    assert children[0]["status"] != BLOCKED


@pytest.mark.django_db
def test_no_deadlines_no_deadline_key(
    mock_site_context, student, course, topic, setup_cohort_registration
):
    """When no deadlines exist, child dicts have empty deadlines list."""
    course.items.create(child=topic, order=0)

    children = get_course_index(user=student.user, course=course)

    assert children[0]["deadlines"] == []


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_view_course_item_redirects_if_locked(
    client, student, course, topic, setup_cohort_registration, mock_site_context
):
    """Direct URL access to a locked item redirects to the course home."""
    course.items.create(child=topic, order=0)

    CohortDeadlineFactory(
        cohort_course_registration=setup_cohort_registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    client.force_login(student.user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert course.slug in response.url


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=False)
def test_get_course_index_skips_deadlines_when_inactive(
    mock_site_context, student, course, topic, setup_cohort_registration
):
    """When DEADLINES_ACTIVE=False, deadlines list is empty and item is not BLOCKED."""
    course.items.create(child=topic, order=0)

    CohortDeadlineFactory(
        cohort_course_registration=setup_cohort_registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    children = get_course_index(user=student.user, course=course)

    assert children[0]["deadlines"] == []
    assert children[0]["status"] != BLOCKED


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=False)
def test_view_course_item_skips_lock_check_when_deadlines_inactive(
    client, student, course, topic, setup_cohort_registration, mock_site_context
):
    """When DEADLINES_ACTIVE=False, expired hard deadline does not redirect."""
    course.items.create(child=topic, order=0)

    CohortDeadlineFactory(
        cohort_course_registration=setup_cohort_registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    client.force_login(student.user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
