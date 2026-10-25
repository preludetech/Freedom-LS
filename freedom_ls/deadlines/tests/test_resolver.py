from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
import time_machine

from django.conf import settings

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import DeadlineKind
from freedom_ls.deadlines.resolver import (
    NO_DEADLINE,
    DeadlineLayer,
    DeadlineSource,
    DeadlineValue,
    ResolvedDeadline,
    course_deadlines,
    course_deadlines_for,
    due_instant,
    is_overdue,
    registration_date_of,
    resolve_deadline,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.tests.factories import SiteFactory

JOHANNESBURG = ZoneInfo("Africa/Johannesburg")
AMSTERDAM = ZoneInfo("Europe/Amsterdam")

FIXED = DeadlineValue(DeadlineKind.FIXED, due_date=date(2026, 3, 20))
RELATIVE = DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=14)


def _layer(source: DeadlineSource, value: DeadlineValue | None) -> DeadlineLayer:
    return DeadlineLayer(source, value)


# --- DeadlineValue ---


def test_from_columns_prefers_the_fixed_date():
    value = DeadlineValue.from_columns(date(2026, 3, 20), time(9, 0), 5)

    assert value == DeadlineValue(
        DeadlineKind.FIXED, due_date=date(2026, 3, 20), due_time=time(9, 0)
    )


def test_from_columns_reads_a_relative_offset():
    value = DeadlineValue.from_columns(None, time(9, 0), 5)

    assert value == DeadlineValue(
        DeadlineKind.RELATIVE, due_time=time(9, 0), due_days_after_registration=5
    )


def test_from_columns_reads_a_zero_day_offset():
    value = DeadlineValue.from_columns(None, None, 0)

    assert value is not None
    assert value.due_days_after_registration == 0


def test_from_columns_is_none_when_no_column_holds_a_deadline():
    assert DeadlineValue.from_columns(None, time(9, 0), None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (DeadlineValue(DeadlineKind.NONE), "none"),
        (FIXED, "fixed:2026-03-20"),
        (
            DeadlineValue(
                DeadlineKind.FIXED, due_date=date(2026, 3, 20), due_time=time(9, 5)
            ),
            "fixed:2026-03-20T09:05",
        ),
        (RELATIVE, "relative:14"),
        (
            DeadlineValue(
                DeadlineKind.RELATIVE,
                due_time=time(17, 0),
                due_days_after_registration=14,
            ),
            "relative:14T17:00",
        ),
    ],
)
def test_canonical_names_each_kind(value: DeadlineValue, expected: str):
    assert value.canonical() == expected


def test_canonical_refuses_a_fixed_value_without_a_date():
    with pytest.raises(ValueError, match="date"):
        DeadlineValue(DeadlineKind.FIXED).canonical()


# --- due_instant ---


def test_a_fixed_date_without_a_time_is_due_at_the_end_of_its_day():
    due = due_instant(FIXED, date(2026, 3, 1), JOHANNESBURG)

    assert due == datetime(2026, 3, 20, 23, 59, 59, 999999, tzinfo=JOHANNESBURG)


def test_a_fixed_date_with_a_time_is_due_at_that_time_in_the_zone():
    value = DeadlineValue(
        DeadlineKind.FIXED, due_date=date(2026, 3, 20), due_time=time(9, 30)
    )

    due = due_instant(value, date(2026, 3, 1), JOHANNESBURG)

    assert due == datetime(2026, 3, 20, 7, 30, tzinfo=UTC)


def test_a_relative_value_counts_days_from_the_registration_date():
    due = due_instant(RELATIVE, date(2026, 3, 1), JOHANNESBURG)

    assert due == datetime(2026, 3, 15, 23, 59, 59, 999999, tzinfo=JOHANNESBURG)


def test_a_relative_value_across_the_european_dst_change_lands_on_local_end_of_day():
    value = DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=14)

    due = due_instant(value, date(2026, 3, 20), AMSTERDAM)

    assert due is not None
    assert due == datetime(2026, 4, 3, 23, 59, 59, 999999, tzinfo=AMSTERDAM)
    assert due.utcoffset() == timedelta(hours=2)


def test_a_none_value_has_no_instant():
    assert (
        due_instant(DeadlineValue(DeadlineKind.NONE), date(2026, 3, 1), AMSTERDAM)
        is None
    )


def test_a_relative_value_without_a_day_count_is_refused():
    with pytest.raises(ValueError, match="days"):
        due_instant(DeadlineValue(DeadlineKind.RELATIVE), date(2026, 3, 1), AMSTERDAM)


# --- is_overdue ---


def test_overdue_one_microsecond_after_the_instant_and_not_at_it():
    due = datetime(2026, 3, 20, 23, 59, 59, 999999, tzinfo=JOHANNESBURG)
    resolved = ResolvedDeadline(due, DeadlineSource.CONTENT)

    assert not is_overdue(resolved, completed=False, now=due)
    assert is_overdue(resolved, completed=False, now=due + timedelta(microseconds=1))


def test_a_completed_item_is_never_overdue():
    due = datetime(2026, 3, 20, tzinfo=UTC)
    resolved = ResolvedDeadline(due, DeadlineSource.CONTENT)

    assert not is_overdue(resolved, completed=True, now=due + timedelta(days=30))


def test_no_deadline_is_never_overdue():
    assert not is_overdue(NO_DEADLINE, completed=False, now=datetime.now(UTC))


def test_a_fixed_date_before_registration_is_overdue_at_once():
    registered_on = date(2026, 4, 1)
    resolved = resolve_deadline(
        [_layer(DeadlineSource.CONTENT, FIXED)], registered_on, JOHANNESBURG
    )

    with time_machine.travel(datetime(2026, 4, 1, 8, 0, tzinfo=UTC), tick=False):
        assert is_overdue(resolved, completed=False, now=datetime.now(UTC))


# --- resolve_deadline ---


def test_the_most_specific_layer_with_a_value_wins():
    layers = [
        _layer(DeadlineSource.LEARNER, None),
        _layer(DeadlineSource.COHORT_REGISTRATION, RELATIVE),
        _layer(DeadlineSource.CONTENT, FIXED),
    ]

    resolved = resolve_deadline(layers, date(2026, 3, 1), JOHANNESBURG)

    assert resolved.source == DeadlineSource.COHORT_REGISTRATION
    assert resolved.due_at == due_instant(RELATIVE, date(2026, 3, 1), JOHANNESBURG)


def test_no_layer_with_a_value_resolves_to_no_deadline():
    layers = [
        _layer(DeadlineSource.LEARNER, None),
        _layer(DeadlineSource.CONTENT, None),
    ]

    assert resolve_deadline(layers, date(2026, 3, 1), JOHANNESBURG) == NO_DEADLINE


def test_a_none_kind_override_wins_and_removes_the_deadline():
    layers = [
        _layer(DeadlineSource.LEARNER, DeadlineValue(DeadlineKind.NONE)),
        _layer(DeadlineSource.CONTENT, FIXED),
    ]

    resolved = resolve_deadline(layers, date(2026, 3, 1), JOHANNESBURG)

    assert resolved.due_at is None
    assert resolved.source == DeadlineSource.LEARNER


# --- course_deadlines (ORM) ---


def _course_with_topics(count: int) -> Course:
    course: Course = CourseFactory()
    for order in range(count):
        course.items.create(child=TopicFactory(), order=order)
    return course


@pytest.mark.django_db
def test_course_deadlines_keys_every_viewable_row_and_no_part_row(mock_site_context):
    course = CourseFactory()
    first_part = CoursePartFactory()
    second_part = CoursePartFactory()
    top_topic = TopicFactory()
    part_topics = [TopicFactory(), TopicFactory()]
    course.items.create(child=first_part, order=0)
    course.items.create(child=top_topic, order=1)
    course.items.create(child=second_part, order=2)
    first_part.items.create(child=part_topics[0], order=0)
    second_part.items.create(child=part_topics[1], order=0)
    record = course_progress_record(course, UserFactory())

    deadlines = course_deadlines(record)

    viewable_ids = {
        item.pk for item in Course.objects.get(pk=course.pk).viewable_collection_items()
    }
    assert set(deadlines.items) == viewable_ids
    assert len(viewable_ids) == 3


@pytest.mark.django_db
def test_a_part_placed_in_two_courses_resolves_its_rows_in_both(mock_site_context):
    """The part's item rows belong to the part, so a learner on both courses used to see
    the dates in only one of them: the resolver credited the part to a single course."""
    shared_part = CoursePartFactory()
    topic = TopicFactory()
    row = shared_part.items.create(child=topic, order=0, due_days_after_registration=7)
    course_a = CourseFactory()
    course_b = CourseFactory()
    course_a.items.create(child=shared_part, order=0)
    course_b.items.create(child=shared_part, order=0)
    user = UserFactory()
    record_a = course_progress_record(course_a, user)
    record_b = course_progress_record(course_b, user)

    deadlines = course_deadlines_for([record_a, record_b])

    assert deadlines[record_a.pk].items[row.pk].due_at is not None
    assert deadlines[record_b.pk].items[row.pk].due_at is not None


@pytest.mark.django_db
def test_course_deadlines_resolves_content_defaults_from_the_registration_date(
    mock_site_context,
):
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    course = CourseFactory()
    relative_topic = TopicFactory()
    fixed_topic = TopicFactory()
    plain_topic = TopicFactory()
    for order, topic in enumerate([relative_topic, fixed_topic, plain_topic]):
        course.items.create(child=topic, order=order)
    relative_item = collection_item_for(course, relative_topic)
    relative_item.due_days_after_registration = 14
    relative_item.save()
    fixed_item = collection_item_for(course, fixed_topic)
    fixed_item.due_date = date(2026, 3, 20)
    fixed_item.due_time = time(9, 0)
    fixed_item.save()
    plain_item = collection_item_for(course, plain_topic)
    record = course_progress_record(
        course,
        UserFactory(),
        created_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
    )

    deadlines = course_deadlines(record)

    assert deadlines.items[relative_item.pk].due_at == datetime(
        2026, 3, 15, 23, 59, 59, 999999, tzinfo=JOHANNESBURG
    )
    assert deadlines.items[relative_item.pk].source == DeadlineSource.CONTENT
    assert deadlines.items[fixed_item.pk].due_at == datetime(
        2026, 3, 20, 9, 0, tzinfo=JOHANNESBURG
    )
    assert deadlines.items[plain_item.pk] == NO_DEADLINE


@pytest.mark.django_db
def test_course_deadlines_resolves_the_time_limit(mock_site_context):
    course = CourseFactory(time_limit_days=30)
    record = course_progress_record(
        course, UserFactory(), created_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    )

    deadlines = course_deadlines(record)

    assert deadlines.time_limit.due_at is not None
    assert deadlines.time_limit.due_at.date() == date(2026, 3, 31)
    assert deadlines.time_limit.source == DeadlineSource.CONTENT


@pytest.mark.django_db
def test_a_course_without_a_time_limit_has_no_time_limit_deadline(mock_site_context):
    record = course_progress_record(CourseFactory(), UserFactory())

    assert course_deadlines(record).time_limit == NO_DEADLINE


@pytest.mark.django_db
def test_the_site_zone_drives_the_resolved_instant(mock_site_context):
    SiteTimeZoneConfigFactory(time_zone="Pacific/Auckland")
    course = CourseFactory(time_limit_days=1)
    record = course_progress_record(
        course, UserFactory(), created_at=datetime(2026, 3, 1, 23, 0, tzinfo=UTC)
    )

    deadlines = course_deadlines(record)

    # 23:00 UTC on 1 March is already 2 March in Auckland, so the day after is 3 March.
    assert deadlines.time_limit.due_at is not None
    assert deadlines.time_limit.due_at.astimezone(
        ZoneInfo("Pacific/Auckland")
    ).date() == date(2026, 3, 3)


@pytest.mark.django_db
def test_another_sites_zone_is_not_read(mock_site_context):
    other_site = SiteFactory()
    SiteTimeZoneConfigFactory(site=other_site, time_zone="Pacific/Auckland")
    course = CourseFactory(time_limit_days=1)
    record = course_progress_record(
        course, UserFactory(), created_at=datetime(2026, 3, 1, 23, 0, tzinfo=UTC)
    )

    deadlines = course_deadlines(record)

    assert deadlines.time_limit.due_at is not None
    assert deadlines.time_limit.due_at.tzinfo == ZoneInfo(settings.TIME_ZONE)


@pytest.mark.django_db
def test_registration_date_is_read_in_the_site_zone(mock_site_context):
    record = course_progress_record(
        CourseFactory(),
        UserFactory(),
        created_at=datetime(2026, 3, 1, 23, 0, tzinfo=UTC),
    )

    assert registration_date_of(record, JOHANNESBURG) == date(2026, 3, 2)
    assert registration_date_of(record, ZoneInfo("UTC")) == date(2026, 3, 1)


def _warm_process_caches(record: CourseProgress) -> None:
    """Resolve once so the Site and ContentType caches are filled. They outlive a test, so
    without this a query budget would depend on which test ran first."""
    course_deadlines(record)


@pytest.mark.django_db
def test_course_deadlines_cost_the_same_on_a_small_and_a_large_course(
    mock_site_context, django_assert_max_num_queries
):
    small = course_progress_record(_course_with_topics(6), UserFactory())
    large = course_progress_record(_course_with_topics(60), UserFactory())
    _warm_process_caches(small)

    with django_assert_max_num_queries(5):
        assert len(course_deadlines(small).items) == 6
    with django_assert_max_num_queries(5):
        assert len(course_deadlines(large).items) == 60


@pytest.mark.django_db
def test_course_deadlines_for_many_records_costs_the_same_as_for_one(
    mock_site_context, django_assert_max_num_queries
):
    records = [
        course_progress_record(_course_with_topics(4), UserFactory()) for _ in range(3)
    ]
    _warm_process_caches(records[0])

    with django_assert_max_num_queries(5):
        result = course_deadlines_for(records)

    assert set(result) == {record.pk for record in records}


@pytest.mark.django_db
def test_course_deadlines_for_no_records_is_empty(mock_site_context):
    assert course_deadlines_for([]) == {}


# --- cohort override layer ---


def _cohort_and_individual_records(
    course: Course,
) -> tuple[CourseProgress, CourseProgress]:
    """One learner's records for `course`: one under a cohort registration, one under an
    individual registration."""
    cohort = CohortFactory()
    learner = LearnerFactory(organisation=cohort.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
    cohort_record: CourseProgress = CourseProgressFactory(
        learner=learner,
        course=course,
        cohort_registration=registration,
        learner_registration=None,
    )
    individual_record: CourseProgress = CourseProgressFactory(
        learner=learner, course=course
    )
    return cohort_record, individual_record


def _cohort_record_with_item(
    **item_columns: object,
) -> tuple[CourseProgress, ContentCollectionItem]:
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    item = collection_item_for(course, topic)
    for name, value in item_columns.items():
        setattr(item, name, value)
    item.save()
    cohort_record, _ = _cohort_and_individual_records(course)
    return cohort_record, item


@pytest.mark.django_db
def test_the_cohort_layer_beats_the_content_default(mock_site_context):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    CohortDeadlineOverrideFactory(
        cohort_registration=record.cohort_registration,
        collection_item=item,
        due_days_after_registration=3,
    )

    type(record).objects.filter(pk=record.pk).update(
        created_at=datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
    )
    record.refresh_from_db()

    resolved = course_deadlines(record).items[item.pk]

    assert resolved.source == DeadlineSource.COHORT_REGISTRATION
    assert resolved.due_at is not None
    assert resolved.due_at.date() == date(2026, 3, 5)


@pytest.mark.django_db
def test_a_none_override_at_the_cohort_layer_removes_the_date(mock_site_context):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    CohortDeadlineOverrideFactory(
        cohort_registration=record.cohort_registration,
        collection_item=item,
        kind=DeadlineKind.NONE,
        due_days_after_registration=None,
    )

    resolved = course_deadlines(record).items[item.pk]

    assert resolved.due_at is None
    assert resolved.source == DeadlineSource.COHORT_REGISTRATION


@pytest.mark.django_db
def test_a_time_limit_override_beats_the_course_time_limit(mock_site_context):
    record, _ = _cohort_record_with_item()
    Course.objects.filter(pk=record.course_id).update(time_limit_days=30)
    CohortDeadlineOverrideFactory(
        cohort_registration=record.cohort_registration,
        due_days_after_registration=5,
    )

    resolved = course_deadlines(record).time_limit

    assert resolved.source == DeadlineSource.COHORT_REGISTRATION


@pytest.mark.django_db
def test_a_learner_on_an_individual_registration_has_no_cohort_layer(
    mock_site_context,
):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    _, individual_record = _cohort_and_individual_records(record.course)
    CohortDeadlineOverrideFactory(
        cohort_registration=record.cohort_registration,
        collection_item=item,
        due_days_after_registration=3,
    )

    resolved = course_deadlines(individual_record).items[item.pk]

    assert resolved.source == DeadlineSource.CONTENT


@pytest.mark.django_db
def test_another_sites_override_rows_are_not_read(mock_site_context):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    other_site = SiteFactory()
    CohortDeadlineOverrideFactory(
        site=other_site,
        cohort_registration=record.cohort_registration,
        collection_item=item,
        due_days_after_registration=3,
    )

    resolved = course_deadlines(record).items[item.pk]

    assert resolved.source == DeadlineSource.CONTENT


def _record_with_an_override_on_each_of_five_items() -> CourseProgress:
    record, _ = _cohort_record_with_item(due_days_after_registration=14)
    for index in range(4):
        topic = TopicFactory()
        record.course.items.create(child=topic, order=index + 1)
    for collection_item in Course.objects.get(
        pk=record.course_id
    ).viewable_collection_items():
        CohortDeadlineOverrideFactory(
            cohort_registration=record.cohort_registration,
            collection_item=collection_item,
        )
    return record


@pytest.fixture
def record_with_five_overridden_items(mock_site_context) -> CourseProgress:
    return _record_with_an_override_on_each_of_five_items()


@pytest.mark.django_db
def test_override_rows_do_not_change_the_query_count(
    record_with_five_overridden_items, django_assert_max_num_queries
):
    record = record_with_five_overridden_items

    with django_assert_max_num_queries(6):
        result = course_deadlines(record)

    assert len(result.items) == 5


# --- learner override layer ---


@pytest.mark.django_db
def test_the_learner_layer_beats_the_cohort_layer_and_the_content_default(
    mock_site_context,
):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    CohortDeadlineOverrideFactory(
        cohort_registration=record.cohort_registration,
        collection_item=item,
        due_days_after_registration=3,
    )
    LearnerDeadlineOverrideFactory(
        course_progress=record, collection_item=item, due_days_after_registration=1
    )
    type(record).objects.filter(pk=record.pk).update(
        created_at=datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
    )
    record.refresh_from_db()

    resolved = course_deadlines(record).items[item.pk]

    assert resolved.source == DeadlineSource.LEARNER
    assert resolved.due_at is not None
    assert resolved.due_at.date() == date(2026, 3, 3)


@pytest.mark.django_db
def test_a_none_override_at_the_learner_layer_removes_the_date(mock_site_context):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    LearnerDeadlineOverrideFactory(
        course_progress=record,
        collection_item=item,
        kind=DeadlineKind.NONE,
        due_days_after_registration=None,
    )

    resolved = course_deadlines(record).items[item.pk]

    assert resolved.due_at is None
    assert resolved.source == DeadlineSource.LEARNER


@pytest.mark.django_db
def test_a_learner_time_limit_override_beats_the_course_time_limit(mock_site_context):
    record, _ = _cohort_record_with_item()
    Course.objects.filter(pk=record.course_id).update(time_limit_days=30)
    LearnerDeadlineOverrideFactory(
        course_progress=record, due_days_after_registration=5
    )

    assert course_deadlines(record).time_limit.source == DeadlineSource.LEARNER


@pytest.mark.django_db
def test_each_record_of_a_learner_resolves_its_own_overrides(mock_site_context):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    _, individual_record = _cohort_and_individual_records(record.course)
    LearnerDeadlineOverrideFactory(
        course_progress=individual_record,
        collection_item=item,
        due_days_after_registration=1,
    )

    resolved = course_deadlines_for([record, individual_record])

    assert resolved[record.pk].items[item.pk].source == DeadlineSource.CONTENT
    assert (
        resolved[individual_record.pk].items[item.pk].source == DeadlineSource.LEARNER
    )


@pytest.mark.django_db
def test_another_sites_learner_override_rows_are_not_read(mock_site_context):
    record, item = _cohort_record_with_item(due_days_after_registration=14)
    LearnerDeadlineOverrideFactory(
        site=SiteFactory(),
        course_progress=record,
        collection_item=item,
        due_days_after_registration=1,
    )

    assert course_deadlines(record).items[item.pk].source == DeadlineSource.CONTENT
