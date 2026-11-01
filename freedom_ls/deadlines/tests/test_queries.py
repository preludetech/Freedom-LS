from __future__ import annotations

from datetime import date, time

import pytest

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
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineKind,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.queries import (
    canonical_beneath,
    content_default_for,
    layers_beneath,
    placement_values_for,
)
from freedom_ls.deadlines.resolver import DeadlineLayer, DeadlineSource, DeadlineValue
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory


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
        override, placement_values=placement_values_for(override.course)
    ) == ("relative:3")


@pytest.mark.django_db
def test_placement_values_for_keys_by_child_row_and_ignores_another_courses_placement(
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

    assert placement_values_for(course_a) == {
        row.pk: DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=3)
    }
