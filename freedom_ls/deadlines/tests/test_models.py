from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.factories import (
    CohortCourseRegistrationDeadlineConfigFactory,
    CohortDeadlineConfigFactory,
    CohortDeadlineOverrideFactory,
    CourseDeadlineConfigFactory,
    LearnerCourseRegistrationDeadlineConfigFactory,
    LearnerDeadlineOverrideFactory,
    OrganisationDeadlineConfigFactory,
    SiteDeadlineConfigFactory,
)
from freedom_ls.deadlines.models import (
    SWITCH_FIELDS,
    CohortDeadlineOverride,
    DeadlineKind,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.resolver import DeadlineValue, course_deadlines
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory

JOHANNESBURG = ZoneInfo("Africa/Johannesburg")


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
            {
                "kind": DeadlineKind.FIXED,
                "due_date": date(2026, 3, 1),
                "due_time": time(9, 0),
            },
            False,
            "due_time",
            id="fixed-time-limit-has-no-time",
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
        pytest.param(
            {"kind": DeadlineKind.FIXED, "due_date": date(2026, 3, 1)},
            False,
            id="fixed-time-limit",
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
            {
                "kind": DeadlineKind.FIXED,
                "due_date": date(2026, 3, 1),
                "due_time": time(9, 0),
            },
            False,
            "due_time",
            id="fixed-time-limit-has-no-time",
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


CONFIG_FACTORIES = [
    SiteDeadlineConfigFactory,
    OrganisationDeadlineConfigFactory,
    CourseDeadlineConfigFactory,
    CohortDeadlineConfigFactory,
    CohortCourseRegistrationDeadlineConfigFactory,
    LearnerCourseRegistrationDeadlineConfigFactory,
]


@pytest.mark.django_db
@pytest.mark.parametrize("config_factory", CONFIG_FACTORIES)
@pytest.mark.parametrize(
    "bad_values",
    [
        {"mark_overdue": "maybe"},
        {"close_items": "maybe"},
        {"end_course_access": "maybe"},
        {"notify_educators": "maybe"},
        {"after_access_ended": "everything"},
        {"grace_window": timedelta(seconds=-1)},
    ],
)
def test_config_row_with_an_invalid_value_is_refused_by_the_database(
    mock_site_context, config_factory, bad_values
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        config_factory(**bad_values)


@pytest.mark.django_db
@pytest.mark.parametrize("config_factory", CONFIG_FACTORIES)
def test_config_row_with_a_zero_grace_window_saves(
    mock_site_context, config_factory
) -> None:
    row = config_factory(grace_window=timedelta(0))

    row.refresh_from_db()
    assert row.grace_window == timedelta(0)


@pytest.mark.django_db
@pytest.mark.parametrize("config_factory", CONFIG_FACTORIES)
def test_config_row_defaults_to_inherit_everywhere(
    mock_site_context, config_factory
) -> None:
    row = config_factory()

    assert [getattr(row, name) for name in SWITCH_FIELDS] == ["inherit"] * 4
    assert row.after_access_ended == "inherit"
    assert row.grace_window is None


@pytest.mark.django_db
def test_second_site_config_row_is_refused_by_the_database(
    mock_site_context,
) -> None:
    SiteDeadlineConfigFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        SiteDeadlineConfigFactory()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("config_factory", "owner_field"),
    [
        (OrganisationDeadlineConfigFactory, "organisation"),
        (CourseDeadlineConfigFactory, "course"),
        (CohortDeadlineConfigFactory, "cohort"),
        (CohortCourseRegistrationDeadlineConfigFactory, "cohort_registration"),
        (LearnerCourseRegistrationDeadlineConfigFactory, "learner_registration"),
    ],
)
def test_second_config_row_for_one_owner_is_refused_by_the_database(
    mock_site_context, config_factory, owner_field
) -> None:
    first = config_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        config_factory(**{owner_field: getattr(first, owner_field)})


@pytest.mark.django_db
def test_a_cohort_fixed_time_limit_resolves_to_the_end_of_that_day_in_the_site_zone(
    mock_site_context,
) -> None:
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    registration = CohortCourseRegistrationFactory()
    record = CourseProgressFactory(
        course=registration.course,
        cohort_registration=registration,
        learner_registration=None,
    )
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=None,
        kind=DeadlineKind.FIXED,
        due_date=date(2026, 3, 1),
    )

    due_at = course_deadlines(record).time_limit.due_at

    assert due_at == datetime(2026, 3, 1, 23, 59, 59, 999999, tzinfo=JOHANNESBURG)


@pytest.mark.django_db
def test_a_learner_fixed_time_limit_resolves_to_the_end_of_that_day_in_the_site_zone(
    mock_site_context,
) -> None:
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    record = CourseProgressFactory()
    LearnerDeadlineOverrideFactory(
        course_progress=record,
        collection_item=None,
        kind=DeadlineKind.FIXED,
        due_date=date(2026, 3, 1),
    )

    due_at = course_deadlines(record).time_limit.due_at

    assert due_at == datetime(2026, 3, 1, 23, 59, 59, 999999, tzinfo=JOHANNESBURG)
