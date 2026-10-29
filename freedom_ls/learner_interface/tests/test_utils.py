"""Tests for course helper functions in learner_interface.utils."""

from datetime import UTC, date, datetime, timedelta

import pytest

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.models import AfterAccessEnded, DeadlineKind
from freedom_ls.deadlines.policy import ResolvedDeadlinePolicy
from freedom_ls.deadlines.resolver import (
    NO_DEADLINE,
    CourseDeadlines,
    DeadlineSource,
    ResolvedDeadline,
    course_deadlines,
)
from freedom_ls.learner_interface.tests.helpers import (
    learner_override,
    topic_completion,
)
from freedom_ls.learner_interface.utils import (
    BLOCKED,
    CLOSED,
    COMPLETE,
    FAILED,
    IN_PROGRESS,
    READY,
    current_entry,
    derive_part_status,
    get_all_courses,
    get_completed_courses,
    get_course_index,
    get_current_courses,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory

GET_CURRENT_COURSES_MAX_QUERIES = 5

# --- get_all_courses ---


@pytest.mark.django_db
def test_get_all_courses_returns_all(mock_site_context):
    """get_all_courses returns all courses regardless of user."""
    courses = CourseFactory.create_batch(3)
    result = get_all_courses()
    # get_all_courses carries no ordering contract, so compare membership
    # rather than row order.
    assert set(result) == set(courses)


@pytest.mark.django_db
def test_get_all_courses_returns_empty_when_none_exist(mock_site_context):
    """get_all_courses returns empty queryset when no courses exist."""
    result = get_all_courses()
    assert list(result) == []


# --- get_completed_courses ---


@pytest.mark.django_db
def test_get_completed_courses_anonymous_user(mock_site_context):
    """get_completed_courses returns empty list for anonymous user."""
    CourseFactory.create_batch(2)
    result = get_completed_courses(AnonymousUser())
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_user_without_registrations(mock_site_context):
    """get_completed_courses returns empty list for user without registrations."""
    CourseFactory.create_batch(2)
    user = UserFactory()
    result = get_completed_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_no_completed(mock_site_context):
    """get_completed_courses returns empty list when no courses are completed."""
    user = UserFactory()
    course = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    result = get_completed_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_returns_completed(mock_site_context):
    """get_completed_courses returns only completed courses."""
    user = UserFactory()
    course_a = CourseFactory()
    course_b = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_a)
    LearnerCourseRegistrationFactory(learner__user=user, course=course_b)

    # Complete course_a only
    course_progress_record(course_a, user, completed_time=timezone.now())

    result = get_completed_courses(user)
    assert result == [course_a]


# --- get_current_courses ---


@pytest.mark.django_db
def test_get_current_courses_anonymous_user(mock_site_context):
    """get_current_courses returns empty list for anonymous user."""
    CourseFactory.create_batch(2)
    result = get_current_courses(AnonymousUser())
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_user_without_registrations(mock_site_context):
    """get_current_courses returns empty list for user without registrations."""
    CourseFactory.create_batch(2)
    user = UserFactory()
    result = get_current_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_returns_non_completed_registered(mock_site_context):
    """get_current_courses returns registered courses that are not completed."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    result = get_current_courses(user)
    assert len(result) == 1
    assert result[0] == course


@pytest.mark.django_db
def test_get_current_courses_excludes_completed(mock_site_context):
    """get_current_courses excludes courses that are completed."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    course_progress_record(course, user, completed_time=timezone.now())

    result = get_current_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_have_progress_percentage(mock_site_context):
    """get_current_courses attaches progress_percentage to each course."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    result = get_current_courses(user)
    assert len(result) == 1
    assert result[0].progress_percentage == 0


# --- get_course_index deadline keys ---


def _policy(
    *,
    mark_overdue: bool = True,
    close_items: bool = False,
    grace_window: timedelta = timedelta(0),
) -> ResolvedDeadlinePolicy:
    return ResolvedDeadlinePolicy(
        mark_overdue=mark_overdue,
        close_items=close_items,
        end_course_access=False,
        notify_educators=False,
        grace_window=grace_window,
        after_access_ended=AfterAccessEnded.OUTLINE_AND_RESULTS,
        sources={},
    )


def _resolved(due_at: datetime | None) -> ResolvedDeadline:
    return ResolvedDeadline(due_at, DeadlineSource.CONTENT)


@pytest.mark.django_db
def test_get_course_index_rows_carry_the_collection_item_id_and_deadline(
    mock_site_context,
):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    record = course_progress_record(course, user)
    item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        deadline_policy=_policy(),
        now=due + timedelta(days=1),
    )

    assert row["collection_item_id"] == item.pk
    assert row["due_at"] == due
    assert row["is_overdue"] is True


@pytest.mark.django_db
def test_get_course_index_row_is_not_overdue_before_the_due_instant(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    record = course_progress_record(course, user)
    item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        deadline_policy=_policy(),
        now=due - timedelta(days=1),
    )

    assert row["due_at"] == due
    assert row["is_overdue"] is False


@pytest.mark.django_db
def test_get_course_index_completed_row_is_not_overdue(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    topic_completion(course, user, topic, complete_time=timezone.now())
    record = course_progress_record(course, user)
    item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        deadline_policy=_policy(),
        now=due + timedelta(days=1),
    )

    assert row["status"] == "COMPLETE"
    assert row["is_overdue"] is False


@pytest.mark.django_db
def test_get_course_index_without_deadlines_carries_no_date(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)

    (row,) = get_course_index(user, course, can_access_content=True)

    assert row["due_at"] is None
    assert row["is_overdue"] is False


@pytest.mark.django_db
def test_get_course_index_part_rows_carry_no_due_at_but_their_children_do(
    mock_site_context,
):
    user = UserFactory()
    course = CourseFactory()
    part = CoursePartFactory()
    topic = TopicFactory()
    course.items.create(child=part, order=0)
    part.items.create(child=topic, order=0)
    record = course_progress_record(course, user)
    part_item = course.collection_items()[0]
    topic_item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (part_row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={topic_item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        deadline_policy=_policy(),
        now=due,
    )

    assert part_row["collection_item_id"] == part_item.pk
    assert "due_at" not in part_row
    assert part_row["children"][0]["due_at"] == due
    assert part_row["children"][0]["collection_item_id"] == topic_item.pk


@pytest.mark.django_db
def test_get_current_courses_stamps_the_card_organisation_from_the_record(
    mock_site_context,
):
    user = UserFactory()
    organisation = OrganisationFactory()
    course: Course = CourseFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user, learner__organisation=organisation, course=course
    )
    course_progress_record(course, user)

    result = get_current_courses(user)

    assert result[0].card_organisation == organisation


@pytest.mark.django_db
def test_get_current_courses_stamps_no_card_organisation_without_a_record(
    mock_site_context,
):
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=CourseFactory())

    result = get_current_courses(user)

    assert result[0].card_organisation is None


@pytest.mark.django_db
def test_get_current_courses_query_count_does_not_grow_with_courses(
    mock_site_context, django_assert_max_num_queries
):
    user = UserFactory()
    for _ in range(6):
        course = CourseFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user,
            learner__organisation=OrganisationFactory(),
            course=course,
        )
        course_progress_record(course, user)

    with django_assert_max_num_queries(GET_CURRENT_COURSES_MAX_QUERIES):
        get_current_courses(user)


@pytest.mark.django_db
def test_get_course_index_row_is_not_overdue_when_the_policy_does_not_mark_overdue(
    mock_site_context,
):
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    record = course_progress_record(course, user)
    item = collection_item_for(course, topic)
    due = datetime(2026, 3, 20, tzinfo=UTC)

    (row,) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={item.pk: _resolved(due)}, time_limit=NO_DEADLINE
        ),
        deadline_policy=_policy(mark_overdue=False),
        now=due + timedelta(days=1),
    )

    assert row["due_at"] == due
    assert row["is_overdue"] is False


def test_current_entry_finds_a_top_level_row():
    index = [{"title": "A"}, {"title": "B", "is_current": True}]

    assert current_entry(index) == {"title": "B", "is_current": True}


def test_current_entry_finds_a_row_nested_in_a_part():
    nested = {"title": "Inner", "is_current": True}
    index = [{"title": "A"}, {"title": "Part", "children": [{"title": "X"}, nested]}]

    assert current_entry(index) is nested


def test_current_entry_is_none_when_no_row_is_current():
    assert current_entry([{"title": "A", "children": [{"title": "B"}]}]) is None


# --- Closing items ---


@pytest.mark.parametrize(
    ("child_statuses", "expected"),
    [
        ([CLOSED], CLOSED),
        ([CLOSED, CLOSED], CLOSED),
        ([COMPLETE, CLOSED], CLOSED),
        ([CLOSED, BLOCKED], CLOSED),
        ([CLOSED, READY], READY),
        ([COMPLETE, CLOSED, READY], IN_PROGRESS),
        ([CLOSED, IN_PROGRESS], IN_PROGRESS),
        ([CLOSED, FAILED], FAILED),
    ],
)
def test_derive_part_status_reads_closed_only_when_no_child_is_open(
    child_statuses, expected
):
    assert derive_part_status(child_statuses) == expected


def _closing_course(topic_count: int = 2):
    """A course of topics in order, a learner with a record, and the record's items."""
    user = UserFactory()
    course = CourseFactory()
    topics = [TopicFactory() for _ in range(topic_count)]
    for order, topic in enumerate(topics):
        course.items.create(child=topic, order=order)
    record = course_progress_record(course, user)
    return user, course, topics, record


def _closing_index(user, course, record, due_by_item, *, now, grace=timedelta(0)):
    return get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=CourseDeadlines(
            items={pk: _resolved(due) for pk, due in due_by_item.items()},
            time_limit=NO_DEADLINE,
        ),
        deadline_policy=_policy(close_items=True, grace_window=grace),
        now=now,
    )


DUE = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


@pytest.mark.django_db
def test_a_closed_item_that_sequential_unlock_offers_reads_closed_with_a_url(
    mock_site_context,
):
    user, course, topics, record = _closing_course()
    item = collection_item_for(course, topics[0])

    first, second = _closing_index(
        user, course, record, {item.pk: DUE}, now=DUE + timedelta(days=1)
    )

    assert first["status"] == CLOSED
    assert first["is_closed"] is True
    assert first["closes_at"] == DUE
    assert first["url"]
    assert second["status"] == BLOCKED
    assert second["url"] is None


@pytest.mark.django_db
def test_an_item_inside_the_grace_window_stays_open_and_names_when_it_closes(
    mock_site_context,
):
    user, course, topics, record = _closing_course()
    item = collection_item_for(course, topics[0])
    grace = timedelta(days=3)

    first, _second = _closing_index(
        user, course, record, {item.pk: DUE}, now=DUE + timedelta(days=1), grace=grace
    )

    assert first["status"] == READY
    assert first["is_closed"] is False
    assert first["closes_at"] == DUE + grace


@pytest.mark.django_db
def test_an_item_that_sequential_unlock_withholds_stays_blocked_past_its_close_instant(
    mock_site_context,
):
    user, course, topics, record = _closing_course()
    second_item = collection_item_for(course, topics[1])

    _first, second = _closing_index(
        user, course, record, {second_item.pk: DUE}, now=DUE + timedelta(days=1)
    )

    assert second["status"] == BLOCKED
    assert second["url"] is None


@pytest.mark.django_db
def test_a_completed_item_past_its_close_instant_stays_complete(mock_site_context):
    user, course, topics, _record = _closing_course()
    topic_completion(course, user, topics[0], complete_time=timezone.now())
    record = course_progress_record(course, user)
    item = collection_item_for(course, topics[0])

    first, _second = _closing_index(
        user, course, record, {item.pk: DUE}, now=DUE + timedelta(days=1)
    )

    assert first["status"] == COMPLETE
    assert first["is_closed"] is False


@pytest.mark.django_db
def test_a_part_whose_open_children_are_all_closed_reads_closed(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    part = CoursePartFactory()
    topics = [TopicFactory(), TopicFactory()]
    course.items.create(child=part, order=0)
    for order, topic in enumerate(topics):
        part.items.create(child=topic, order=order)
    record = course_progress_record(course, user)
    due = {collection_item_for(course, topic).pk: DUE for topic in topics}

    (part_row,) = _closing_index(user, course, record, due, now=DUE + timedelta(days=1))

    assert [child["status"] for child in part_row["children"]] == [CLOSED, BLOCKED]
    assert part_row["status"] == CLOSED
    assert part_row["url"] is None


@pytest.mark.django_db
def test_closes_at_moves_with_a_learner_override_of_the_due_date(mock_site_context):
    user, course, topics, record = _closing_course()
    item = collection_item_for(course, topics[0])
    new_due = date(2026, 5, 1)
    learner_override(
        record,
        item,
        kind=DeadlineKind.FIXED,
        due_date=new_due,
        due_days_after_registration=None,
    )

    (first, _second) = get_course_index(
        user,
        course,
        can_access_content=True,
        course_progress=record,
        course_deadlines=course_deadlines(record),
        deadline_policy=_policy(close_items=True, grace_window=timedelta(days=2)),
        now=datetime(2026, 4, 1, tzinfo=UTC),
    )

    assert first["closes_at"].date() == new_due + timedelta(days=2)
    assert first["is_closed"] is False
