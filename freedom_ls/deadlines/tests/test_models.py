from __future__ import annotations

from datetime import date, time

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
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
from freedom_ls.deadlines.resolver import DeadlineValue
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress


def _course_item() -> tuple[Course, CohortCourseRegistration, ContentCollectionItem]:
    course: Course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
        course=course
    )
    return course, registration, collection_item_for(course, topic)


def _override(
    registration: CohortCourseRegistration,
    item: ContentCollectionItem | None,
    **fields: object,
) -> CohortDeadlineOverride:
    return CohortDeadlineOverride(
        cohort_registration=registration, collection_item=item, **fields
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "on_item", "error_field"),
    [
        pytest.param(
            {"kind": DeadlineKind.FIXED}, True, "due_date", id="fixed-needs-a-date"
        ),
        pytest.param(
            {"kind": DeadlineKind.RELATIVE},
            True,
            "due_days_after_registration",
            id="relative-needs-days",
        ),
        pytest.param(
            {"kind": DeadlineKind.NONE, "due_date": date(2026, 3, 1)},
            True,
            "kind",
            id="none-takes-no-date",
        ),
        pytest.param(
            {"kind": DeadlineKind.NONE, "due_time": time(9, 0)},
            True,
            "kind",
            id="none-takes-no-time",
        ),
        pytest.param(
            {"kind": DeadlineKind.NONE, "due_days_after_registration": 0},
            True,
            "kind",
            id="none-takes-no-days-even-zero",
        ),
        pytest.param(
            {"kind": DeadlineKind.FIXED, "due_date": date(2026, 3, 1)},
            False,
            "kind",
            id="time-limit-is-not-fixed",
        ),
        pytest.param(
            {
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": 3,
                "due_time": time(9, 0),
            },
            False,
            "due_time",
            id="time-limit-has-no-time",
        ),
        pytest.param(
            {
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": 3,
                "due_date": date(2026, 3, 1),
            },
            True,
            "due_date",
            id="relative-takes-no-date",
        ),
        pytest.param(
            {
                "kind": DeadlineKind.FIXED,
                "due_date": date(2026, 3, 1),
                "due_days_after_registration": 3,
            },
            True,
            "due_days_after_registration",
            id="fixed-takes-no-days",
        ),
    ],
)
def test_clean_refuses_an_inconsistent_shape(
    mock_site_context, fields: dict[str, object], on_item: bool, error_field: str
) -> None:
    _, registration, item = _course_item()
    override = _override(registration, item if on_item else None, **fields)

    with pytest.raises(ValidationError) as caught:
        override.clean()

    assert error_field in caught.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "on_item"),
    [
        pytest.param(
            {"kind": DeadlineKind.FIXED, "due_date": date(2026, 3, 1)}, True, id="fixed"
        ),
        pytest.param(
            {"kind": DeadlineKind.RELATIVE, "due_days_after_registration": 0},
            True,
            id="relative-zero-days",
        ),
        pytest.param({"kind": DeadlineKind.NONE}, True, id="none-on-an-item"),
        pytest.param({"kind": DeadlineKind.NONE}, False, id="none-on-the-time-limit"),
        pytest.param(
            {"kind": DeadlineKind.RELATIVE, "due_days_after_registration": 30},
            False,
            id="time-limit",
        ),
    ],
)
def test_clean_accepts_a_consistent_shape(
    mock_site_context, fields: dict[str, object], on_item: bool
) -> None:
    _, registration, item = _course_item()

    _override(registration, item if on_item else None, **fields).clean()


@pytest.mark.django_db
def test_clean_refuses_a_collection_item_of_another_course(mock_site_context) -> None:
    _, registration, _ = _course_item()
    _, _, foreign_item = _course_item()
    override = _override(
        registration,
        foreign_item,
        kind=DeadlineKind.RELATIVE,
        due_days_after_registration=3,
    )

    with pytest.raises(ValidationError) as caught:
        override.clean()

    assert caught.value.message_dict["collection_item"] == [
        "Pick an item of this course."
    ]


def test_clean_returns_without_error_when_the_parent_is_unset() -> None:
    CohortDeadlineOverride(kind=DeadlineKind.FIXED).clean()


@pytest.mark.django_db
def test_one_override_per_registration_and_item(mock_site_context) -> None:
    _, registration, item = _course_item()
    CohortDeadlineOverrideFactory(
        cohort_registration=registration, collection_item=item
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CohortDeadlineOverrideFactory(
            cohort_registration=registration, collection_item=item
        )


@pytest.mark.django_db
def test_one_time_limit_override_per_registration(mock_site_context) -> None:
    _, registration, _ = _course_item()
    CohortDeadlineOverrideFactory(cohort_registration=registration)

    with pytest.raises(IntegrityError), transaction.atomic():
        CohortDeadlineOverrideFactory(cohort_registration=registration)


@pytest.mark.django_db
def test_an_item_override_and_a_time_limit_override_can_share_a_registration(
    mock_site_context,
) -> None:
    _, registration, item = _course_item()
    CohortDeadlineOverrideFactory(
        cohort_registration=registration, collection_item=item
    )

    CohortDeadlineOverrideFactory(cohort_registration=registration)

    assert registration.deadline_overrides.count() == 2


@pytest.mark.django_db
def test_value_carries_the_row_columns(mock_site_context) -> None:
    override = CohortDeadlineOverrideFactory(
        kind=DeadlineKind.RELATIVE,
        due_days_after_registration=7,
        due_time=time(9, 0),
    )

    assert override.value() == DeadlineValue(DeadlineKind.RELATIVE, None, time(9, 0), 7)


# --- learner override ---


def _record_item() -> tuple[CourseProgress, ContentCollectionItem]:
    course: Course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    record: CourseProgress = CourseProgressFactory(course=course)
    return record, collection_item_for(course, topic)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "on_item", "error_field"),
    [
        pytest.param(
            {"kind": DeadlineKind.FIXED}, True, "due_date", id="fixed-needs-a-date"
        ),
        pytest.param(
            {"kind": DeadlineKind.NONE, "due_days_after_registration": 0},
            True,
            "kind",
            id="none-takes-no-days",
        ),
        pytest.param(
            {"kind": DeadlineKind.FIXED, "due_date": date(2026, 3, 1)},
            False,
            "kind",
            id="time-limit-is-not-fixed",
        ),
        pytest.param(
            {
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": 3,
                "due_time": time(9, 0),
            },
            False,
            "due_time",
            id="time-limit-has-no-time",
        ),
        pytest.param(
            {
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": 3,
                "due_date": date(2026, 3, 1),
            },
            True,
            "due_date",
            id="relative-takes-no-date",
        ),
        pytest.param(
            {
                "kind": DeadlineKind.FIXED,
                "due_date": date(2026, 3, 1),
                "due_days_after_registration": 3,
            },
            True,
            "due_days_after_registration",
            id="fixed-takes-no-days",
        ),
    ],
)
def test_learner_clean_refuses_an_inconsistent_shape(
    mock_site_context, fields: dict[str, object], on_item: bool, error_field: str
) -> None:
    record, item = _record_item()
    override = LearnerDeadlineOverride(
        course_progress=record, collection_item=item if on_item else None, **fields
    )

    with pytest.raises(ValidationError) as caught:
        override.clean()

    assert error_field in caught.value.message_dict


@pytest.mark.django_db
def test_learner_clean_accepts_a_consistent_shape(mock_site_context) -> None:
    record, item = _record_item()

    LearnerDeadlineOverride(
        course_progress=record,
        collection_item=item,
        kind=DeadlineKind.RELATIVE,
        due_days_after_registration=3,
    ).clean()


@pytest.mark.django_db
def test_learner_clean_refuses_a_collection_item_of_another_course(
    mock_site_context,
) -> None:
    record, _ = _record_item()
    _, foreign_item = _record_item()
    override = LearnerDeadlineOverride(
        course_progress=record,
        collection_item=foreign_item,
        kind=DeadlineKind.RELATIVE,
        due_days_after_registration=3,
    )

    with pytest.raises(ValidationError) as caught:
        override.clean()

    assert caught.value.message_dict["collection_item"] == [
        "Pick an item of this course."
    ]


def test_learner_clean_returns_without_error_when_the_parent_is_unset() -> None:
    LearnerDeadlineOverride(kind=DeadlineKind.FIXED).clean()


@pytest.mark.django_db
def test_one_learner_override_per_record_and_item(mock_site_context) -> None:
    record, item = _record_item()
    LearnerDeadlineOverrideFactory(course_progress=record, collection_item=item)

    with pytest.raises(IntegrityError), transaction.atomic():
        LearnerDeadlineOverrideFactory(course_progress=record, collection_item=item)


@pytest.mark.django_db
def test_one_learner_time_limit_override_per_record(mock_site_context) -> None:
    record, _ = _record_item()
    LearnerDeadlineOverrideFactory(course_progress=record)

    with pytest.raises(IntegrityError), transaction.atomic():
        LearnerDeadlineOverrideFactory(course_progress=record)


@pytest.mark.django_db
def test_a_new_record_does_not_carry_the_old_records_overrides(
    mock_site_context,
) -> None:
    record, item = _record_item()
    LearnerDeadlineOverrideFactory(course_progress=record, collection_item=item)
    moved: CourseProgress = CourseProgressFactory(
        course=record.course,
        learner=record.learner,
        learner_registration=None,
        cohort_registration=CohortCourseRegistrationFactory(course=record.course),
    )

    assert record.deadline_overrides.count() == 1
    assert moved.deadline_overrides.count() == 0
