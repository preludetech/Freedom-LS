from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartChildDueDateFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    CoursePauseFactory,
    DeadlineExtensionFactory,
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineKind,
    ExtensionTarget,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.queries import (
    canonical_beneath,
    content_default_for,
    layers_beneath,
    open_pause,
    open_pauses_for,
    pauses_for,
)
from freedom_ls.deadlines.resolver import (
    DeadlineLayer,
    DeadlineSource,
    DeadlineValue,
    content_defaults_for_course,
    course_deadlines,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.tests.factories import SiteFactory


def _item_override(**item_columns: object) -> CohortDeadlineOverride:
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    item = collection_item_for(course, topic)
    for name, value in item_columns.items():
        setattr(item, name, value)
    item.save()
    override: CohortDeadlineOverride = CohortDeadlineOverrideFactory(
        cohort_registration=CohortCourseRegistrationFactory(course=course),
        collection_item=item,
    )
    return override


def _time_limit_override(time_limit_days: int | None) -> CohortDeadlineOverride:
    override: CohortDeadlineOverride = CohortDeadlineOverrideFactory(
        cohort_registration=CohortCourseRegistrationFactory(
            course=CourseFactory(time_limit_days=time_limit_days)
        )
    )
    return override


@pytest.mark.django_db
def test_content_default_for_an_item_row_reads_the_item_columns(mock_site_context):
    override = _item_override(due_date=date(2026, 3, 20), due_time=time(17, 0))

    assert content_default_for(override) == DeadlineValue(
        DeadlineKind.FIXED, due_date=date(2026, 3, 20), due_time=time(17, 0)
    )


@pytest.mark.django_db
def test_content_default_for_a_no_due_date_item_is_the_none_value(mock_site_context):
    override = _item_override(no_due_date=True)

    assert content_default_for(override) == DeadlineValue(DeadlineKind.NONE)


@pytest.mark.django_db
def test_canonical_beneath_a_no_due_date_item_is_none(mock_site_context):
    assert canonical_beneath(_item_override(no_due_date=True)) == "none"


@pytest.mark.django_db
def test_content_default_for_an_item_without_a_deadline_is_none(mock_site_context):
    assert content_default_for(_item_override()) is None


@pytest.mark.django_db
def test_content_default_for_a_time_limit_row_reads_the_course(mock_site_context):
    assert content_default_for(_time_limit_override(30)) == DeadlineValue(
        DeadlineKind.RELATIVE, due_days_after_registration=30
    )


@pytest.mark.django_db
def test_content_default_for_a_time_limit_row_without_a_limit_is_none(
    mock_site_context,
):
    assert content_default_for(_time_limit_override(None)) is None


@pytest.mark.django_db
def test_layers_beneath_a_cohort_row_is_the_content_default(mock_site_context):
    override = _item_override(due_days_after_registration=14)

    assert layers_beneath(override) == [
        DeadlineLayer(
            DeadlineSource.CONTENT,
            DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=14),
        )
    ]


@pytest.mark.django_db
def test_canonical_beneath_an_item_row_is_the_default_in_canonical_form(
    mock_site_context,
):
    override = _item_override(due_date=date(2026, 3, 20), due_time=time(9, 0))

    assert canonical_beneath(override) == "fixed:2026-03-20T09:00"


@pytest.mark.django_db
def test_an_extension_leaves_canonical_beneath_unchanged(mock_site_context):
    override, _ = _learner_override(on_cohort=False)
    before = canonical_beneath(override)

    DeadlineExtensionFactory(
        course_progress=override.course_progress,
        target_kind=ExtensionTarget.COLLECTION_ITEM,
        collection_item=override.collection_item,
    )

    assert canonical_beneath(override) == before == "relative:14"


@pytest.mark.django_db
def test_canonical_beneath_a_time_limit_row_is_the_time_limit(mock_site_context):
    assert canonical_beneath(_time_limit_override(30)) == "relative:30"


@pytest.mark.django_db
def test_canonical_beneath_an_item_row_is_empty_when_nothing_is_beneath(
    mock_site_context,
):
    assert canonical_beneath(_item_override()) == ""


@pytest.mark.django_db
def test_canonical_beneath_a_time_limit_row_is_empty_when_no_time_limit_is_set(
    mock_site_context,
):
    assert canonical_beneath(_time_limit_override(None)) == ""


def _learner_override(*, on_cohort: bool) -> tuple[LearnerDeadlineOverride, object]:
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    item = collection_item_for(course, topic)
    item.due_days_after_registration = 14
    item.save()
    registration = CohortCourseRegistrationFactory(course=course)
    record = CourseProgressFactory(
        course=course,
        cohort_registration=registration if on_cohort else None,
        learner_registration=None
        if on_cohort
        else LearnerCourseRegistrationFactory(course=course),
    )
    override: LearnerDeadlineOverride = LearnerDeadlineOverrideFactory(
        course_progress=record, collection_item=item
    )
    return override, registration


@pytest.mark.django_db
def test_layers_beneath_a_learner_row_on_a_cohort_record_has_the_cohort_row_first(
    mock_site_context,
):
    override, registration = _learner_override(on_cohort=True)
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=override.collection_item,
        due_days_after_registration=5,
        replaced_value="relative:14",
    )

    assert layers_beneath(override) == [
        DeadlineLayer(
            DeadlineSource.COHORT_REGISTRATION,
            DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=5),
        ),
        DeadlineLayer(
            DeadlineSource.CONTENT,
            DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=14),
        ),
    ]


@pytest.mark.django_db
def test_layers_beneath_a_learner_row_on_a_cohort_record_without_a_cohort_row(
    mock_site_context,
):
    override, _ = _learner_override(on_cohort=True)

    assert [layer.source for layer in layers_beneath(override)] == [
        DeadlineSource.CONTENT
    ]


@pytest.mark.django_db
def test_layers_beneath_a_learner_row_on_an_individual_record_is_the_content_default(
    mock_site_context,
):
    override, _ = _learner_override(on_cohort=False)

    assert [layer.source for layer in layers_beneath(override)] == [
        DeadlineSource.CONTENT
    ]


@pytest.mark.django_db
def test_canonical_beneath_a_learner_row_is_the_cohort_value_when_there_is_one(
    mock_site_context,
):
    override, registration = _learner_override(on_cohort=True)
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=override.collection_item,
        due_days_after_registration=5,
    )

    assert canonical_beneath(override) == "relative:5"


def _part_row_override(
    **part_row_columns: object,
) -> tuple[CohortDeadlineOverride, ContentCollectionItem, ContentCollectionItem]:
    """A cohort row on a topic row inside a part the course places. Returns the override,
    the course's placement of the part and the topic row."""
    course: Course = CourseFactory()
    part = CoursePartFactory()
    placement = course.items.create(child=part, order=0)
    row = part.items.create(child=TopicFactory(), order=0, **part_row_columns)
    override: CohortDeadlineOverride = CohortDeadlineOverrideFactory(
        cohort_registration=CohortCourseRegistrationFactory(course=course),
        collection_item=row,
    )
    return override, placement, row


@pytest.mark.django_db
def test_content_default_for_a_part_row_is_the_placement_value_when_the_course_sets_one(
    mock_site_context,
):
    override, placement, row = _part_row_override(due_days_after_registration=14)
    CoursePartChildDueDateFactory(
        part_collection_item=placement,
        collection_item=row,
        due_days_after_registration=3,
    )

    assert content_default_for(override) == DeadlineValue(
        DeadlineKind.RELATIVE, due_days_after_registration=3
    )


@pytest.mark.django_db
def test_content_default_for_a_part_row_is_its_own_value_without_a_placement_value(
    mock_site_context,
):
    override, _, _ = _part_row_override(due_days_after_registration=14)

    assert content_default_for(override) == DeadlineValue(
        DeadlineKind.RELATIVE, due_days_after_registration=14
    )


@pytest.mark.django_db
def test_content_default_for_a_no_due_date_placement_value_is_the_none_value(
    mock_site_context,
):
    override, placement, row = _part_row_override(due_days_after_registration=14)
    CoursePartChildDueDateFactory(
        part_collection_item=placement,
        collection_item=row,
        due_days_after_registration=None,
        no_due_date=True,
    )

    assert content_default_for(override) == DeadlineValue(DeadlineKind.NONE)


@pytest.mark.django_db
def test_content_default_for_uses_a_given_mapping_without_querying(
    mock_site_context, django_assert_max_num_queries
):
    override, _, row = _part_row_override(due_days_after_registration=14)
    # Load what the row reads before counting, so only the default's own reads are counted.
    override.collection_item  # noqa: B018
    override.course  # noqa: B018
    given = {
        row.pk: DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=9)
    }

    with django_assert_max_num_queries(0):
        value = content_default_for(override, given)

    assert value == given[row.pk]


@pytest.mark.django_db
def test_canonical_beneath_a_part_row_reads_the_placement_value(mock_site_context):
    override, placement, row = _part_row_override(due_days_after_registration=14)
    CoursePartChildDueDateFactory(
        part_collection_item=placement,
        collection_item=row,
        due_days_after_registration=3,
    )

    assert canonical_beneath(override) == "relative:3"
    assert canonical_beneath(
        override, content_defaults=content_defaults_for_course(placement.collection_id)
    ) == ("relative:3")


@pytest.mark.django_db
def test_content_default_for_agrees_with_what_a_learner_is_resolved(mock_site_context):
    """One reading of a content default: the admin column and the learner's resolved
    deadline come from the same code, so a course placing one part twice, each placement
    with its own value, cannot make them disagree."""
    override, placement, row = _part_row_override(due_days_after_registration=14)
    course = Course.objects.get(pk=placement.collection_id)
    second_placement = course.items.create(child=placement.child, order=1)
    for part_placement, days in ((placement, 3), (second_placement, 8)):
        CoursePartChildDueDateFactory(
            part_collection_item=part_placement,
            collection_item=row,
            due_days_after_registration=days,
        )
    registered = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    record = course_progress_record(course, UserFactory(), created_at=registered)

    due_at = course_deadlines(record).items[row.pk].due_at
    shown = content_default_for(override)

    assert due_at is not None
    assert shown is not None
    assert (due_at.date() - registered.date()).days == shown.due_days_after_registration


@pytest.mark.django_db
def test_content_defaults_for_course_keys_by_child_row_and_ignores_another_courses_placement(
    mock_site_context,
):
    course_a: Course = CourseFactory()
    course_b: Course = CourseFactory()
    part = CoursePartFactory()
    placement_a = course_a.items.create(child=part, order=0)
    placement_b = course_b.items.create(child=part, order=0)
    row = part.items.create(child=TopicFactory(), order=0)
    CoursePartChildDueDateFactory(
        part_collection_item=placement_a,
        collection_item=row,
        due_days_after_registration=3,
    )
    CoursePartChildDueDateFactory(
        part_collection_item=placement_b,
        collection_item=row,
        due_days_after_registration=8,
    )

    assert content_defaults_for_course(course_a.pk) == {
        row.pk: DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=3)
    }


def _record() -> CourseProgress:
    record: CourseProgress = CourseProgressFactory()
    return record


NOW = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


@pytest.mark.django_db
def test_pauses_for_reads_open_and_ended_pauses_of_every_record(mock_site_context):
    first, second = _record(), _record()
    ended = CoursePauseFactory(
        course_progress=first,
        started_at=NOW - timedelta(days=9),
        ended_at=NOW - timedelta(days=8),
    )
    open_one = CoursePauseFactory(course_progress=first, started_at=NOW)
    other = CoursePauseFactory(course_progress=second, started_at=NOW)

    result = pauses_for([first, second])

    assert result[first.pk] == [open_one, ended]
    assert result[second.pk] == [other]


@pytest.mark.django_db
def test_pauses_for_costs_one_query_whatever_the_number_of_records(
    mock_site_context, django_assert_num_queries
):
    records = [_record() for _ in range(4)]
    for record in records:
        CoursePauseFactory(course_progress=record)

    with django_assert_num_queries(1):
        pauses_for(records)


@pytest.mark.django_db
def test_pauses_for_ignores_another_sites_pause(mock_site_context):
    record = _record()
    CoursePauseFactory(course_progress=record, site=SiteFactory())

    assert pauses_for([record]) == {}


@pytest.mark.django_db
def test_open_pause_returns_the_unended_pause(mock_site_context):
    record = _record()
    CoursePauseFactory(
        course_progress=record,
        started_at=NOW - timedelta(days=9),
        ended_at=NOW - timedelta(days=8),
    )
    open_one = CoursePauseFactory(course_progress=record, started_at=NOW)

    assert open_pause(record, NOW) == open_one


@pytest.mark.django_db
def test_open_pause_is_none_once_the_planned_resume_has_passed(mock_site_context):
    record = _record()
    CoursePauseFactory(
        course_progress=record,
        started_at=NOW - timedelta(days=5),
        planned_resume_on=(NOW - timedelta(days=2)).date(),
    )

    assert open_pause(record, NOW) is None


@pytest.mark.django_db
def test_open_pauses_for_reads_no_pause_rows_when_given_them(mock_site_context):
    record = _record()
    pause = CoursePauseFactory(course_progress=record, started_at=NOW)
    rows = pauses_for([record])

    with CaptureQueriesContext(connection) as queries:
        result = open_pauses_for([record], NOW, pauses=rows)

    assert result == {record.pk: pause}
    assert not [q for q in queries if "coursepause" in q["sql"]]
