from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fsrs import Rating

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import FormQuestionFactory, QuestionOptionFactory
from freedom_ls.form_engine.models import FormProgress, FormQuestion, QuestionAnswer
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.revision import scheduler
from freedom_ls.revision.factories import RevisionScheduleFactory
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.revision.services import (
    GuessRefused,
    RevisionSessionState,
    build_session,
    mark_guessed,
    record_answer,
    session_summary,
    shuffled_options,
)
from freedom_ls.revision.tests.helpers import (
    finish_topic,
    place_topic,
    question_testing_topic,
)

NOW = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def _correct_ids(question) -> set:
    return {o.id for o in question.options.all() if o.correct}


def _wrong_ids(question) -> set:
    return {o.id for o in question.options.all() if not o.correct}


@pytest.fixture
def banked(mock_site_context: Site) -> tuple[User, CourseProgress, FormQuestion]:
    """A learner who has finished a topic with one question, and that question."""
    course: Course = CourseFactory()
    topic, _ = place_topic(course)
    question = question_testing_topic(topic)
    user: User = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    return user, record, question


@pytest.mark.django_db
def test_first_answer_creates_the_schedule(banked) -> None:
    user, record, question = banked

    record_answer(user, record, question, _correct_ids(question), NOW)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert (schedule.reps, schedule.lapses, schedule.due > NOW) == (1, 0, True)


@pytest.mark.django_db
def test_second_answer_updates_the_same_schedule(banked) -> None:
    user, record, question = banked
    record_answer(user, record, question, _correct_ids(question), NOW)

    record_answer(user, record, question, _wrong_ids(question), NOW + timedelta(days=1))

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert RevisionSchedule.objects.count() == 1
    assert schedule.reps == 2


@pytest.mark.django_db
def test_wrong_answer_to_a_learned_card_counts_a_lapse(banked) -> None:
    user, record, question = banked
    record_answer(user, record, question, _correct_ids(question), NOW)
    schedule = RevisionSchedule.objects.get(user=user, question=question)
    schedule.state = 2
    schedule.save()

    record_answer(user, record, question, _wrong_ids(question), schedule.due)

    schedule.refresh_from_db()
    assert schedule.lapses == 1


@pytest.mark.django_db
def test_topic_in_two_courses_has_one_shared_schedule(mock_site_context) -> None:
    topic_course = CourseFactory()
    other_course = CourseFactory()
    topic, _ = place_topic(topic_course)
    other_course.items.create(child=topic, order=0)
    question = question_testing_topic(topic)
    user = UserFactory()
    first = course_progress_record(topic_course, user)
    second = course_progress_record(other_course, user)

    record_answer(user, first, question, _correct_ids(question), NOW)
    record_answer(user, second, question, _correct_ids(question), NOW)

    assert RevisionSchedule.objects.filter(user=user, question=question).count() == 1


@pytest.mark.django_db
def test_editing_an_option_afterwards_leaves_the_stored_marking(banked) -> None:
    user, record, question = banked
    review = record_answer(user, record, question, _correct_ids(question), NOW)

    question.options.update(correct=False)

    review.refresh_from_db()
    assert review.was_correct is True


@pytest.mark.django_db
def test_record_answer_writes_no_quiz_attempt(banked) -> None:
    user, record, question = banked

    record_answer(user, record, question, _correct_ids(question), NOW)

    assert (
        QuestionAnswer.objects.count(),
        FormProgress.objects.count(),
        RevisionReview.objects.count(),
    ) == (0, 0, 1)


@pytest.mark.django_db
def test_build_session_holds_at_most_the_configured_size(
    mock_site_context, settings
) -> None:
    settings.REVISION_SESSION_SIZE = 2
    course = CourseFactory()
    topic, _ = place_topic(course)
    for _ in range(3):
        question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)

    state = build_session(user, record, NOW)

    assert len(state.question_ids) == 2


@pytest.mark.django_db
def test_build_session_for_a_section_holds_only_that_sections_questions(
    mock_site_context,
) -> None:
    course = CourseFactory()
    wanted, _ = place_topic(course, order=0)
    other, _ = place_topic(course, order=1)
    question = question_testing_topic(wanted)
    question_testing_topic(other)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, wanted)
    finish_topic(record, other)

    state = build_session(user, record, NOW, wanted)

    assert state.question_ids == (question.pk,)


def test_state_past_its_last_question_has_no_current_question() -> None:
    state = RevisionSessionState(
        question_ids=(uuid4(),), seeds=(1,), started_at=NOW, index=0
    )

    assert state.advanced().current_question_id is None


def test_state_with_fewer_seeds_than_questions_is_rejected() -> None:
    with pytest.raises(ValueError, match="same length"):
        RevisionSessionState(question_ids=(uuid4(),), seeds=(), started_at=NOW)


@pytest.mark.django_db
def test_build_session_gives_each_question_a_seed(banked) -> None:
    user, record, _ = banked

    state = build_session(user, record, NOW)

    assert len(state.seeds) == len(state.question_ids) == 1


def _ten_options(*, locked_index: int | None = None) -> FormQuestion:
    question: FormQuestion = FormQuestionFactory(type="multiple_choice")
    for index in range(10):
        QuestionOptionFactory(
            question=question,
            text=f"Option {index}",
            order=index,
            locked=index == locked_index,
        )
    return question


@pytest.mark.django_db
def test_shuffled_options_keep_a_locked_option_at_its_index(mock_site_context) -> None:
    question = _ten_options(locked_index=9)

    options = shuffled_options(question, 12345)

    assert options[9].text == "Option 9"


@pytest.mark.django_db
def test_shuffled_options_for_the_same_seed_are_in_the_same_order(
    mock_site_context,
) -> None:
    question = _ten_options()

    first = shuffled_options(question, 777)
    second = shuffled_options(question, 777)

    assert [o.id for o in first] == [o.id for o in second]


@pytest.mark.django_db
def test_shuffled_options_differ_between_seeds(mock_site_context) -> None:
    question = _ten_options()

    orders = {
        tuple(o.id for o in shuffled_options(question, seed)) for seed in range(5)
    }

    assert len(orders) > 1


def _schedule_columns(schedule) -> tuple:
    return (
        schedule.state,
        schedule.step,
        schedule.stability,
        schedule.difficulty,
        schedule.due,
        schedule.last_review,
    )


def _banked_for(user: User) -> tuple[User, CourseProgress, FormQuestion]:
    course: Course = CourseFactory()
    topic, _ = place_topic(course)
    question = question_testing_topic(topic)
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    return user, record, question


def _due(user: User, question: FormQuestion) -> datetime:
    due: datetime = RevisionSchedule.objects.get(user=user, question=question).due
    return due


@pytest.mark.django_db
def test_guessed_right_answer_is_due_sooner_than_one_left_alone(
    mock_site_context,
) -> None:
    left_user, left_record, left_question = _banked_for(UserFactory())
    user, record, question = _banked_for(UserFactory())
    record_answer(
        left_user, left_record, left_question, _correct_ids(left_question), NOW
    )
    review = record_answer(user, record, question, _correct_ids(question), NOW)

    mark_guessed(review)

    assert _due(user, question) < _due(left_user, left_question)


@pytest.mark.django_db
def test_re_rated_schedule_equals_a_first_time_hard(banked) -> None:
    user, record, question = banked
    review = record_answer(user, record, question, _correct_ids(question), NOW)
    first_time_hard = scheduler.review(scheduler.new_card(NOW), Rating.Hard, NOW)[0]

    mark_guessed(review)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert _schedule_columns(schedule) == tuple(
        scheduler.columns_from_card(first_time_hard).values()
    )


@pytest.mark.django_db
def test_second_tap_restores_the_good_schedule(banked) -> None:
    user, record, question = banked
    review = record_answer(user, record, question, _correct_ids(question), NOW)
    good = _schedule_columns(RevisionSchedule.objects.get(user=user, question=question))
    mark_guessed(review)

    mark_guessed(review)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert (_schedule_columns(schedule), review.guessed, review.rating) == (
        good,
        False,
        int(Rating.Good),
    )


@pytest.mark.django_db
def test_guessing_a_wrong_answer_is_refused(banked) -> None:
    user, record, question = banked
    review = record_answer(user, record, question, _wrong_ids(question), NOW)

    with pytest.raises(GuessRefused):
        mark_guessed(review)


@pytest.mark.django_db
def test_guessing_a_review_a_later_one_replaced_is_refused(banked) -> None:
    user, record, question = banked
    stale = record_answer(user, record, question, _correct_ids(question), NOW)
    record_answer(
        user, record, question, _correct_ids(question), NOW + timedelta(days=3)
    )

    with pytest.raises(GuessRefused):
        mark_guessed(stale)


@pytest.mark.django_db
def test_guessing_leaves_reps_and_lapses_unchanged(banked) -> None:
    user, record, question = banked
    review = record_answer(user, record, question, _correct_ids(question), NOW)

    mark_guessed(review)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert (schedule.reps, schedule.lapses) == (1, 0)


def _three_banked_questions() -> tuple[User, CourseProgress, list[FormQuestion]]:
    course: Course = CourseFactory()
    topic, _ = place_topic(course)
    questions = [question_testing_topic(topic) for _ in range(3)]
    user: User = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    return user, record, questions


@pytest.mark.django_db
def test_build_session_with_nothing_due_asks_the_weakest_question_first(
    mock_site_context,
) -> None:
    user, record, (steady, lapsed, difficult) = _three_banked_questions()
    later = NOW + timedelta(days=5)
    RevisionScheduleFactory(
        user=user, question=steady, due=later, lapses=0, difficulty=2.0
    )
    RevisionScheduleFactory(
        user=user, question=lapsed, due=later, lapses=3, difficulty=2.0
    )
    RevisionScheduleFactory(
        user=user, question=difficult, due=later, lapses=0, difficulty=9.0
    )

    state = build_session(user, record, NOW)

    assert state.question_ids == (lapsed.pk, difficult.pk, steady.pk)


@pytest.mark.django_db
def test_build_session_with_a_question_due_holds_only_the_due_one(
    mock_site_context,
) -> None:
    user, record, (due, later_one, later_two) = _three_banked_questions()
    RevisionScheduleFactory(user=user, question=due, due=NOW - timedelta(days=1))
    for question in (later_one, later_two):
        RevisionScheduleFactory(
            user=user, question=question, due=NOW + timedelta(days=5), lapses=4
        )

    state = build_session(user, record, NOW)

    assert state.question_ids == (due.pk,)


@pytest.mark.django_db
def test_build_session_with_nothing_due_holds_at_most_the_configured_size(
    mock_site_context, settings
) -> None:
    settings.REVISION_SESSION_SIZE = 2
    user, record, questions = _three_banked_questions()
    for question in questions:
        RevisionScheduleFactory(
            user=user, question=question, due=NOW + timedelta(days=5)
        )

    state = build_session(user, record, NOW)

    assert len(state.question_ids) == 2


@pytest.mark.django_db
def test_session_summary_counts_knew_hard_and_forgot(mock_site_context) -> None:
    user, record, (known, guessed, missed) = _three_banked_questions()
    state = build_session(user, record, NOW)
    record_answer(user, record, known, _correct_ids(known), NOW)
    mark_guessed(record_answer(user, record, guessed, _correct_ids(guessed), NOW))
    record_answer(user, record, missed, _wrong_ids(missed), NOW)

    summary = session_summary(user, state, record.course)

    assert (summary.answered, summary.knew, summary.hard, summary.forgot) == (
        3,
        1,
        1,
        1,
    )


@pytest.mark.django_db
def test_session_summary_of_an_unanswered_session_is_all_zero(banked) -> None:
    user, record, _ = banked
    state = build_session(user, record, NOW)

    summary = session_summary(user, state, record.course)

    assert (summary.answered, summary.knew, summary.hard, summary.forgot) == (
        0,
        0,
        0,
        0,
    )


@pytest.mark.django_db
def test_a_second_answer_in_the_same_session_writes_nothing(banked) -> None:
    user, record, question = banked
    first = record_answer(
        user, record, question, _correct_ids(question), NOW, session_started_at=NOW
    )

    second = record_answer(
        user,
        record,
        question,
        _wrong_ids(question),
        NOW + timedelta(seconds=1),
        session_started_at=NOW,
    )

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert (second.pk, RevisionReview.objects.count(), schedule.reps) == (
        first.pk,
        1,
        1,
    )


@pytest.mark.django_db
def test_session_summary_leaves_out_an_answer_given_in_another_course(banked) -> None:
    user, record, question = banked
    state = build_session(user, record, NOW)
    other_record = course_progress_record(CourseFactory(), user)
    record_answer(user, other_record, question, _correct_ids(question), NOW)

    summary = session_summary(user, state, record.course)

    assert summary.answered == 0


@pytest.mark.django_db
def test_second_tap_restores_the_exact_due_of_a_long_review_interval(banked) -> None:
    user, record, question = banked
    when = NOW
    for _ in range(5):
        record_answer(user, record, question, _correct_ids(question), when)
        when = RevisionSchedule.objects.get(user=user, question=question).due
    review = record_answer(user, record, question, _correct_ids(question), when)
    good = _schedule_columns(RevisionSchedule.objects.get(user=user, question=question))
    assert good[4] - when > timedelta(days=7)
    mark_guessed(review)

    mark_guessed(review)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert _schedule_columns(schedule) == good
