import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from freedom_ls.content_engine.models import Topic
from freedom_ls.student_management.models import CohortDeadline
from freedom_ls.student_management.deadline_utils import (
    get_course_deadlines,
    get_effective_deadlines,
)


@pytest.mark.django_db
def test_bulk_returns_course_level_deadline(
    mock_site_context, student, course, cohort_course_reg, cohort_membership
):
    """Bulk resolution includes course-level deadlines under (None, None) key."""
    course_dt = timezone.now() + timedelta(days=7)
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=course_dt,
    )

    result = get_course_deadlines(student, course)

    assert (None, None) in result
    assert len(result[(None, None)]) == 1
    assert result[(None, None)][0].deadline == course_dt


@pytest.mark.django_db
def test_bulk_returns_item_level_deadlines(
    mock_site_context, student, course, cohort_course_reg, cohort_membership
):
    """Bulk resolution includes item-level deadlines under (ct_id, obj_id) keys."""
    topic1 = Topic.objects.create(title="T1", slug="t1")
    topic2 = Topic.objects.create(title="T2", slug="t2")
    course.items.create(child=topic1, order=0)
    course.items.create(child=topic2, order=1)

    topic_ct = ContentType.objects.get_for_model(Topic)
    dt1 = timezone.now() + timedelta(days=5)
    dt2 = timezone.now() + timedelta(days=10)

    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic1.id, deadline=dt1,
    )
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic2.id, deadline=dt2,
    )

    result = get_course_deadlines(student, course)

    key1 = (topic_ct.id, topic1.id)
    key2 = (topic_ct.id, topic2.id)
    assert key1 in result
    assert key2 in result
    assert result[key1][0].deadline == dt1
    assert result[key2][0].deadline == dt2


@pytest.mark.django_db
def test_bulk_matches_per_item_resolution(
    mock_site_context, student, course, cohort_course_reg, cohort_membership
):
    """Bulk resolution matches per-item resolution for each item."""
    topic = Topic.objects.create(title="Match Topic", slug="match-topic")
    course.items.create(child=topic, order=0)

    topic_ct = ContentType.objects.get_for_model(Topic)
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct, object_id=topic.id,
        deadline=timezone.now() + timedelta(days=7),
    )

    bulk_result = get_course_deadlines(student, course)
    per_item_result = get_effective_deadlines(student, course, content_item=topic)

    key = (topic_ct.id, topic.id)
    assert len(bulk_result.get(key, [])) == len(per_item_result)
    assert bulk_result[key][0].deadline == per_item_result[0].deadline


@pytest.mark.django_db
def test_bulk_empty_when_no_deadlines(
    mock_site_context, student, course, cohort_course_reg, cohort_membership
):
    """Bulk resolution returns empty dict when there are no deadlines."""
    result = get_course_deadlines(student, course)

    assert result == {}
