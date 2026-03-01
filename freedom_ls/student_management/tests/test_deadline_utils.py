from datetime import timedelta

import pytest

from django.utils import timezone

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.student_management.deadline_utils import (
    get_effective_deadlines,
    is_item_locked_by_deadline,
)
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    StudentCohortDeadlineOverrideFactory,
    StudentCourseRegistrationFactory,
    StudentDeadlineFactory,
    StudentFactory,
)

# --- get_effective_deadlines tests ---


@pytest.mark.django_db
def test_single_cohort_deadline_resolves(mock_site_context):
    """A single cohort deadline for a topic resolves correctly."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    deadline_dt = timezone.now() + timedelta(days=7)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == deadline_dt
    assert result[0].is_hard_deadline is True


@pytest.mark.django_db
def test_override_beats_cohort_deadline(mock_site_context):
    """StudentCohortDeadlineOverride takes precedence over CohortDeadline for that student."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    cohort_dt = timezone.now() + timedelta(days=7)
    override_dt = timezone.now() + timedelta(days=14)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=cohort_dt,
    )
    StudentCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_item=topic,
        deadline=override_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == override_dt


@pytest.mark.django_db
def test_two_cohort_registrations_show_both_deadlines(mock_site_context):
    """Student in two cohorts both registered for the same course sees both deadlines."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()

    cohort_a = CohortFactory(name="Cohort A2")
    cohort_b = CohortFactory(name="Cohort B")
    CohortMembershipFactory(student=student, cohort=cohort_a)
    CohortMembershipFactory(student=student, cohort=cohort_b)

    reg_a = CohortCourseRegistrationFactory(cohort=cohort_a, collection=course)
    reg_b = CohortCourseRegistrationFactory(cohort=cohort_b, collection=course)

    dt_a = timezone.now() + timedelta(days=5)
    dt_b = timezone.now() + timedelta(days=10)

    CohortDeadlineFactory(
        cohort_course_registration=reg_a,
        content_item=topic,
        deadline=dt_a,
    )
    CohortDeadlineFactory(
        cohort_course_registration=reg_b,
        content_item=topic,
        deadline=dt_b,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 2
    deadlines = {r.deadline for r in result}
    assert deadlines == {dt_a, dt_b}


@pytest.mark.django_db
def test_cohort_plus_individual_registration_shows_both(mock_site_context):
    """Student with cohort registration + individual registration sees both deadlines."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )
    student_course_reg = StudentCourseRegistrationFactory(
        student=student, collection=course
    )

    cohort_dt = timezone.now() + timedelta(days=5)
    student_dt = timezone.now() + timedelta(days=10)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=cohort_dt,
    )
    StudentDeadlineFactory(
        student_course_registration=student_course_reg,
        content_item=topic,
        deadline=student_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 2
    deadlines = {r.deadline for r in result}
    assert deadlines == {cohort_dt, student_dt}


@pytest.mark.django_db
def test_item_level_deadline_beats_course_level(mock_site_context):
    """Item-level deadline takes precedence over course-level within the same registration."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    course_dt = timezone.now() + timedelta(days=14)
    item_dt = timezone.now() + timedelta(days=7)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=item_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == item_dt


@pytest.mark.django_db
def test_course_level_deadline_falls_through_when_no_item_level(mock_site_context):
    """Course-level deadline applies when no item-level deadline exists."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    course_dt = timezone.now() + timedelta(days=14)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == course_dt


@pytest.mark.django_db
def test_inactive_registrations_ignored(mock_site_context):
    """Deadlines from inactive registrations are not returned."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course, is_active=False
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 0


@pytest.mark.django_db
def test_course_level_deadline_resolves_for_course(mock_site_context):
    """Course-level deadline resolves when asking for the course itself (no content_item)."""
    student = StudentFactory()
    course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    course_dt = timezone.now() + timedelta(days=7)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_effective_deadlines(student, course, content_item=None)

    assert len(result) == 1
    assert result[0].deadline == course_dt


# --- is_item_locked_by_deadline tests ---


@pytest.mark.django_db
def test_expired_hard_deadline_incomplete_locks_item(mock_site_context):
    """Expired hard deadline + incomplete item = locked."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    assert (
        is_item_locked_by_deadline(student, course, topic, is_completed=False) is True
    )


@pytest.mark.django_db
def test_expired_hard_deadline_completed_not_locked(mock_site_context):
    """Expired hard deadline + completed item = not locked."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    assert (
        is_item_locked_by_deadline(student, course, topic, is_completed=True) is False
    )


@pytest.mark.django_db
def test_soft_deadline_never_locks(mock_site_context):
    """Soft deadlines never lock, even if expired."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(
        cohort=cohort, collection=course
    )

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=False,
    )

    assert (
        is_item_locked_by_deadline(student, course, topic, is_completed=False) is False
    )


@pytest.mark.django_db
def test_most_permissive_deadline_governs_access(mock_site_context):
    """When multiple hard deadlines exist, the latest (most permissive) governs access."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()

    cohort_a = CohortFactory(name="Cohort Lock A")
    cohort_b = CohortFactory(name="Cohort Lock B")
    CohortMembershipFactory(student=student, cohort=cohort_a)
    CohortMembershipFactory(student=student, cohort=cohort_b)

    reg_a = CohortCourseRegistrationFactory(cohort=cohort_a, collection=course)
    reg_b = CohortCourseRegistrationFactory(cohort=cohort_b, collection=course)

    # Cohort A: expired
    CohortDeadlineFactory(
        cohort_course_registration=reg_a,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )
    # Cohort B: not expired yet
    CohortDeadlineFactory(
        cohort_course_registration=reg_b,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
        is_hard_deadline=True,
    )

    assert (
        is_item_locked_by_deadline(student, course, topic, is_completed=False) is False
    )


@pytest.mark.django_db
def test_no_deadlines_not_locked(mock_site_context):
    """No deadlines means the item is not locked."""
    student = StudentFactory()
    course = CourseFactory()
    topic = TopicFactory()

    assert (
        is_item_locked_by_deadline(student, course, topic, is_completed=False) is False
    )
