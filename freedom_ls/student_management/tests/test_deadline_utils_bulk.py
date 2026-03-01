from datetime import timedelta

import pytest

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.student_management.deadline_utils import (
    get_course_deadlines,
    get_effective_deadlines,
)
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    StudentFactory,
)


@pytest.mark.django_db
def test_bulk_returns_course_level_deadline(mock_site_context):
    """Bulk resolution includes course-level deadlines under (None, None) key."""
    student = StudentFactory()
    course: Course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    course_dt = timezone.now() + timedelta(days=7)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_course_deadlines(student, course)

    assert (None, None) in result
    assert len(result[(None, None)]) == 1
    assert result[(None, None)][0].deadline == course_dt


@pytest.mark.django_db
def test_bulk_returns_item_level_deadlines(mock_site_context):
    """Bulk resolution includes item-level deadlines under (ct_id, obj_id) keys."""
    student = StudentFactory()
    course: Course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic1: Topic = TopicFactory(title="T1")
    topic2: Topic = TopicFactory(title="T2")
    course.items.create(child=topic1, order=0)
    course.items.create(child=topic2, order=1)

    topic_ct = ContentType.objects.get_for_model(Topic)
    dt1 = timezone.now() + timedelta(days=5)
    dt2 = timezone.now() + timedelta(days=10)

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic1, deadline=dt1,
    )
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic2, deadline=dt2,
    )

    result = get_course_deadlines(student, course)

    key1 = (topic_ct.id, topic1.id)
    key2 = (topic_ct.id, topic2.id)
    assert key1 in result
    assert key2 in result
    assert result[key1][0].deadline == dt1
    assert result[key2][0].deadline == dt2


@pytest.mark.django_db
def test_bulk_matches_per_item_resolution(mock_site_context):
    """Bulk resolution matches per-item resolution for each item."""
    student = StudentFactory()
    course: Course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    topic: Topic = TopicFactory(title="Match Topic")
    course.items.create(child=topic, order=0)

    topic_ct = ContentType.objects.get_for_model(Topic)
    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    bulk_result = get_course_deadlines(student, course)
    per_item_result = get_effective_deadlines(student, course, content_item=topic)

    key = (topic_ct.id, topic.id)
    assert len(bulk_result.get(key, [])) == len(per_item_result)
    assert bulk_result[key][0].deadline == per_item_result[0].deadline


@pytest.mark.django_db
def test_bulk_empty_when_no_deadlines(mock_site_context):
    """Bulk resolution returns empty dict when there are no deadlines."""
    student = StudentFactory()
    course = CourseFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    result = get_course_deadlines(student, course)

    assert result == {}
