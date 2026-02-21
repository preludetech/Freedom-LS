import pytest
from datetime import timedelta
from django.utils import timezone
from freedom_ls.content_engine.models import Topic
from freedom_ls.student_management.models import (
    Cohort,
    CohortMembership,
    CohortCourseRegistration,
    CohortDeadline,
    StudentDeadline,
    StudentCohortDeadlineOverride,
)
from freedom_ls.student_management.deadline_utils import (
    get_effective_deadlines,
    is_item_locked_by_deadline,
)


@pytest.fixture
def topic2(mock_site_context):
    return Topic.objects.create(title="Test Topic 2", slug="test-topic-2")


# --- get_effective_deadlines tests ---


@pytest.mark.django_db
def test_single_cohort_deadline_resolves(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """A single cohort deadline for a topic resolves correctly."""
    deadline_dt = timezone.now() + timedelta(days=7)
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=deadline_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == deadline_dt
    assert result[0].is_hard_deadline is True


@pytest.mark.django_db
def test_override_beats_cohort_deadline(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """StudentCohortDeadlineOverride takes precedence over CohortDeadline for that student."""
    cohort_dt = timezone.now() + timedelta(days=7)
    override_dt = timezone.now() + timedelta(days=14)

    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=cohort_dt,
    )
    StudentCohortDeadlineOverride.objects.create(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=override_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == override_dt


@pytest.mark.django_db
def test_two_cohort_registrations_show_both_deadlines(
    mock_site_context, student, course, topic, topic_ct
):
    """Student in two cohorts both registered for the same course sees both deadlines."""
    cohort_a = Cohort.objects.create(name="Cohort A2")
    cohort_b = Cohort.objects.create(name="Cohort B")
    CohortMembership.objects.create(student=student, cohort=cohort_a)
    CohortMembership.objects.create(student=student, cohort=cohort_b)

    reg_a = CohortCourseRegistration.objects.create(cohort=cohort_a, collection=course)
    reg_b = CohortCourseRegistration.objects.create(cohort=cohort_b, collection=course)

    dt_a = timezone.now() + timedelta(days=5)
    dt_b = timezone.now() + timedelta(days=10)

    CohortDeadline.objects.create(
        cohort_course_registration=reg_a, content_type=topic_ct, object_id=topic.id, deadline=dt_a
    )
    CohortDeadline.objects.create(
        cohort_course_registration=reg_b, content_type=topic_ct, object_id=topic.id, deadline=dt_b
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 2
    deadlines = {r.deadline for r in result}
    assert deadlines == {dt_a, dt_b}


@pytest.mark.django_db
def test_cohort_plus_individual_registration_shows_both(
    mock_site_context, student, course, cohort_course_reg, cohort_membership,
    student_course_reg, topic, topic_ct
):
    """Student with cohort registration + individual registration sees both deadlines."""
    cohort_dt = timezone.now() + timedelta(days=5)
    student_dt = timezone.now() + timedelta(days=10)

    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic.id, deadline=cohort_dt,
    )
    StudentDeadline.objects.create(
        student_course_registration=student_course_reg,
        content_type=topic_ct, object_id=topic.id, deadline=student_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 2
    deadlines = {r.deadline for r in result}
    assert deadlines == {cohort_dt, student_dt}


@pytest.mark.django_db
def test_item_level_deadline_beats_course_level(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """Item-level deadline takes precedence over course-level within the same registration."""
    course_dt = timezone.now() + timedelta(days=14)
    item_dt = timezone.now() + timedelta(days=7)

    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic.id,
        deadline=item_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == item_dt


@pytest.mark.django_db
def test_course_level_deadline_falls_through_when_no_item_level(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """Course-level deadline applies when no item-level deadline exists."""
    course_dt = timezone.now() + timedelta(days=14)

    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 1
    assert result[0].deadline == course_dt


@pytest.mark.django_db
def test_inactive_registrations_ignored(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """Deadlines from inactive registrations are not returned."""
    cohort_course_reg.is_active = False
    cohort_course_reg.save()

    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic.id,
        deadline=timezone.now() + timedelta(days=7),
    )

    result = get_effective_deadlines(student, course, content_item=topic)

    assert len(result) == 0


@pytest.mark.django_db
def test_course_level_deadline_resolves_for_course(
    mock_site_context, student, course, cohort_course_reg, cohort_membership
):
    """Course-level deadline resolves when asking for the course itself (no content_item)."""
    course_dt = timezone.now() + timedelta(days=7)
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_effective_deadlines(student, course, content_item=None)

    assert len(result) == 1
    assert result[0].deadline == course_dt


# --- is_item_locked_by_deadline tests ---


@pytest.mark.django_db
def test_expired_hard_deadline_incomplete_locks_item(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """Expired hard deadline + incomplete item = locked."""
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic.id,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    assert is_item_locked_by_deadline(student, course, topic, is_completed=False) is True


@pytest.mark.django_db
def test_expired_hard_deadline_completed_not_locked(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """Expired hard deadline + completed item = not locked."""
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic.id,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    assert is_item_locked_by_deadline(student, course, topic, is_completed=True) is False


@pytest.mark.django_db
def test_soft_deadline_never_locks(
    mock_site_context, student, course, cohort_course_reg, cohort_membership, topic, topic_ct
):
    """Soft deadlines never lock, even if expired."""
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic.id,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=False,
    )

    assert is_item_locked_by_deadline(student, course, topic, is_completed=False) is False


@pytest.mark.django_db
def test_most_permissive_deadline_governs_access(
    mock_site_context, student, course, topic, topic_ct
):
    """When multiple hard deadlines exist, the latest (most permissive) governs access."""
    cohort_a = Cohort.objects.create(name="Cohort Lock A")
    cohort_b = Cohort.objects.create(name="Cohort Lock B")
    CohortMembership.objects.create(student=student, cohort=cohort_a)
    CohortMembership.objects.create(student=student, cohort=cohort_b)

    reg_a = CohortCourseRegistration.objects.create(cohort=cohort_a, collection=course)
    reg_b = CohortCourseRegistration.objects.create(cohort=cohort_b, collection=course)

    # Cohort A: expired
    CohortDeadline.objects.create(
        cohort_course_registration=reg_a,
        content_type=topic_ct, object_id=topic.id,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )
    # Cohort B: not expired yet
    CohortDeadline.objects.create(
        cohort_course_registration=reg_b,
        content_type=topic_ct, object_id=topic.id,
        deadline=timezone.now() + timedelta(days=7),
        is_hard_deadline=True,
    )

    assert is_item_locked_by_deadline(student, course, topic, is_completed=False) is False


@pytest.mark.django_db
def test_no_deadlines_not_locked(
    mock_site_context, student, course, topic
):
    """No deadlines means the item is not locked."""
    assert is_item_locked_by_deadline(student, course, topic, is_completed=False) is False
