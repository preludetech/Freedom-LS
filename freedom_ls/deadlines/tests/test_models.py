from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
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
    CoursePauseFactory,
    DeadlineExtensionFactory,
    LearnerCourseRegistrationDeadlineConfigFactory,
    LearnerDeadlineOverrideFactory,
    OrganisationDeadlineConfigFactory,
    SiteDeadlineConfigFactory,
)
from freedom_ls.deadlines.models import (
    MAX_EXTENSION_DAYS,
    SWITCH_FIELDS,
    CohortDeadlineOverride,
    CoursePause,
    DeadlineExtension,
    DeadlineKind,
    ExtensionTarget,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.resolver import DeadlineValue, course_deadlines
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.tests.factories import SiteFactory

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


def _pause_record() -> CourseProgress:
    record: CourseProgress = CourseProgressFactory()
    return record


@pytest.mark.django_db
def test_a_course_progress_record_cannot_hold_two_unended_pauses(mock_site_context):
    record = _pause_record()
    CoursePauseFactory(course_progress=record)

    with pytest.raises(IntegrityError), transaction.atomic():
        CoursePauseFactory(course_progress=record)


@pytest.mark.django_db
def test_a_course_progress_record_can_hold_an_ended_pause_beside_an_open_one(
    mock_site_context,
):
    record = _pause_record()
    started = datetime(2026, 3, 1, tzinfo=UTC)
    CoursePauseFactory(
        course_progress=record, started_at=started, ended_at=started + timedelta(days=1)
    )

    CoursePauseFactory(course_progress=record)

    assert record.pauses.count() == 2


@pytest.mark.django_db
def test_a_pause_cannot_end_before_it_starts(mock_site_context):
    started = datetime(2026, 3, 1, tzinfo=UTC)

    with pytest.raises(IntegrityError), transaction.atomic():
        CoursePauseFactory(started_at=started, ended_at=started - timedelta(seconds=1))


def test_end_instant_is_none_for_a_pause_with_no_end_and_no_planned_resume():
    pause = CoursePause(started_at=datetime(2026, 3, 1, tzinfo=UTC))

    assert pause.end_instant(JOHANNESBURG) is None


def test_end_instant_prefers_the_recorded_end_when_it_is_earlier():
    pause = CoursePause(
        started_at=datetime(2026, 3, 1, tzinfo=UTC),
        ended_at=datetime(2026, 3, 3, 8, 0, tzinfo=UTC),
        planned_resume_on=date(2026, 3, 10),
    )

    assert pause.end_instant(JOHANNESBURG) == datetime(2026, 3, 3, 8, 0, tzinfo=UTC)


def test_a_planned_resume_is_midnight_of_its_day_in_the_site_zone():
    pause = CoursePause(
        started_at=datetime(2026, 3, 1, tzinfo=UTC), planned_resume_on=date(2026, 3, 10)
    )

    assert pause.end_instant(JOHANNESBURG) == datetime(2026, 3, 9, 22, 0, tzinfo=UTC)


def test_the_planned_resume_ends_a_pause_that_was_never_closed():
    pause = CoursePause(
        started_at=datetime(2026, 3, 1, tzinfo=UTC), planned_resume_on=date(2026, 3, 10)
    )
    before = datetime(2026, 3, 9, 21, 0, tzinfo=UTC)
    after = datetime(2026, 3, 9, 23, 0, tzinfo=UTC)

    assert pause.is_open(before, JOHANNESBURG) is True
    assert pause.is_open(after, JOHANNESBURG) is False


def test_an_open_pause_counts_its_days_up_to_now():
    pause = CoursePause(started_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC))

    assert pause.paused_days(datetime(2026, 3, 3, 13, 0, tzinfo=UTC), JOHANNESBURG) == 3


def test_an_ended_pause_stops_counting_at_its_end():
    pause = CoursePause(
        started_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        ended_at=datetime(2026, 3, 2, 12, 0, tzinfo=UTC),
    )

    assert pause.paused_days(datetime(2026, 4, 1, tzinfo=UTC), JOHANNESBURG) == 1


@pytest.mark.django_db
class TestDueForAnnouncement:
    NOW = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)

    def test_returns_only_due_unannounced_pauses_of_the_given_site(
        self, mock_site_context
    ):
        due = CoursePauseFactory(planned_resume_on=date(2026, 3, 10))
        CoursePauseFactory(planned_resume_on=date(2026, 3, 11))
        CoursePauseFactory(planned_resume_on=None)
        CoursePauseFactory(
            planned_resume_on=date(2026, 3, 1), resume_announced_at=self.NOW
        )
        other_site = SiteFactory()
        CoursePauseFactory(site=other_site, planned_resume_on=date(2026, 3, 1))

        found = CoursePause.objects.due_for_announcement(self.NOW, mock_site_context)

        assert list(found) == [due]

    def test_compares_the_date_in_the_site_zone(self, mock_site_context):
        SiteTimeZoneConfigFactory(
            site=mock_site_context, time_zone="Africa/Johannesburg"
        )
        pause = CoursePauseFactory(planned_resume_on=date(2026, 3, 11))
        late_utc = datetime(2026, 3, 10, 23, 0, tzinfo=UTC)

        assert (
            CoursePause.objects.due_for_announcement(
                late_utc, mock_site_context
            ).first()
            == pause
        )
        assert not CoursePause.objects.due_for_announcement(
            datetime(2026, 3, 10, 21, 0, tzinfo=UTC), mock_site_context
        ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fields",
    [
        pytest.param(
            {"target_kind": ExtensionTarget.COLLECTION_ITEM},
            id="item-kind-without-item",
        ),
        pytest.param(
            {"target_kind": ExtensionTarget.TIME_LIMIT, "with_item": True},
            id="time-limit-with-item",
        ),
        pytest.param(
            {"target_kind": ExtensionTarget.COURSE, "with_item": True},
            id="course-with-item",
        ),
        pytest.param({"days": 0}, id="zero-days"),
        pytest.param({"days": MAX_EXTENSION_DAYS + 1}, id="too-many-days"),
        pytest.param(
            {
                "target_kind": ExtensionTarget.COURSE,
                "requested_date": date(2026, 3, 20),
            },
            id="course-with-requested-date",
        ),
    ],
)
def test_an_extension_row_that_breaks_a_constraint_is_refused(
    mock_site_context, fields: dict[str, object]
) -> None:
    record, item = _record_item()
    columns = dict(fields)
    if columns.pop("with_item", False):
        columns["collection_item"] = item

    with pytest.raises(IntegrityError), transaction.atomic():
        DeadlineExtensionFactory(course_progress=record, **columns)


@pytest.mark.django_db
def test_extensions_stack_without_a_uniqueness_rule(mock_site_context) -> None:
    record, item = _record_item()

    for _ in range(2):
        DeadlineExtensionFactory(
            course_progress=record,
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
        )

    assert record.deadline_extensions.count() == 2


@pytest.mark.django_db
def test_extension_clean_accepts_an_item_of_the_course(mock_site_context) -> None:
    record, item = _record_item()

    DeadlineExtension(
        course_progress=record,
        target_kind=ExtensionTarget.COLLECTION_ITEM,
        collection_item=item,
        days=3,
    ).clean()


@pytest.mark.django_db
def test_extension_clean_refuses_an_item_of_another_course(mock_site_context) -> None:
    record, _ = _record_item()
    _, foreign_item = _record_item()
    extension = DeadlineExtension(
        course_progress=record,
        target_kind=ExtensionTarget.COLLECTION_ITEM,
        collection_item=foreign_item,
        days=3,
    )

    with pytest.raises(ValidationError) as caught:
        extension.clean()

    assert "collection_item" in caught.value.message_dict


@pytest.mark.django_db
def test_an_extension_reads_as_the_learner_the_course_the_days_and_the_target(
    mock_site_context,
) -> None:
    extension = DeadlineExtensionFactory(days=7)

    text = str(extension)

    assert str(extension.course_progress.learner) in text
    assert str(extension.course_progress.course) in text
    assert "+7 days" in text
    assert ExtensionTarget.TIME_LIMIT in text
