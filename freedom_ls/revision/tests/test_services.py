from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fsrs import Rating

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.form_engine.factories import FormQuestionFactory, QuestionOptionFactory
from freedom_ls.form_engine.models import FormProgress, QuestionAnswer
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.revision import scheduler
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.revision.services import (
    GuessRefused,
    RevisionSessionState,
    build_session,
    mark_guessed,
    record_answer,
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
def banked(mock_site_context):
    """A learner who has finished a topic with one question, and that question."""
    course = CourseFactory()
    topic, _ = place_topic(course)
    question = question_testing_topic(topic)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    return user, record, question


@pytest.mark.django_db
def test_first_answer_creates_the_schedule(banked):
    user, record, question = banked

    record_answer(user, record, question, _correct_ids(question), NOW)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert (schedule.reps, schedule.lapses, schedule.due > NOW) == (1, 0, True)


@pytest.mark.django_db
def test_second_answer_updates_the_same_schedule(banked):
    user, record, question = banked
    record_answer(user, record, question, _correct_ids(question), NOW)

    record_answer(user, record, question, _wrong_ids(question), NOW + timedelta(days=1))

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert RevisionSchedule.objects.count() == 1
    assert schedule.reps == 2


@pytest.mark.django_db
def test_wrong_answer_to_a_learned_card_counts_a_lapse(banked):
    user, record, question = banked
    record_answer(user, record, question, _correct_ids(question), NOW)
    schedule = RevisionSchedule.objects.get(user=user, question=question)
    schedule.state = 2
    schedule.save()

    record_answer(user, record, question, _wrong_ids(question), schedule.due)

    schedule.refresh_from_db()
    assert schedule.lapses == 1


@pytest.mark.django_db
def test_topic_in_two_courses_has_one_shared_schedule(mock_site_context):
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
def test_editing_an_option_afterwards_leaves_the_stored_marking(banked):
    user, record, question = banked
    review = record_answer(user, record, question, _correct_ids(question), NOW)

    question.options.update(correct=False)

    review.refresh_from_db()
    assert review.was_correct is True


@pytest.mark.django_db
def test_record_answer_writes_no_quiz_attempt(banked):
    user, record, question = banked

    record_answer(user, record, question, _correct_ids(question), NOW)

    assert (
        QuestionAnswer.objects.count(),
        FormProgress.objects.count(),
        RevisionReview.objects.count(),
    ) == (0, 0, 1)


@pytest.mark.django_db
def test_build_session_holds_at_most_the_configured_size(mock_site_context, settings):
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


def test_state_past_its_last_question_has_no_current_question():
    state = RevisionSessionState(
        question_ids=(uuid4(),), seeds=(1,), started_at=NOW, index=0
    )

    assert state.advanced().current_question_id is None


def test_state_with_fewer_seeds_than_questions_is_rejected():
    with pytest.raises(ValueError, match="same length"):
        RevisionSessionState(question_ids=(uuid4(),), seeds=(), started_at=NOW)


@pytest.mark.django_db
def test_build_session_gives_each_question_a_seed(banked):
    user, record, _ = banked

    state = build_session(user, record, NOW)

    assert len(state.seeds) == len(state.question_ids) == 1


def _ten_options(*, locked_index: int | None = None):
    question = FormQuestionFactory(type="multiple_choice")
    for index in range(10):
        QuestionOptionFactory(
            question=question,
            text=f"Option {index}",
            order=index,
            locked=index == locked_index,
        )
    return question


@pytest.mark.django_db
def test_shuffled_options_keep_a_locked_option_at_its_index(mock_site_context):
    question = _ten_options(locked_index=9)

    options = shuffled_options(question, 12345)

    assert options[9].text == "Option 9"


@pytest.mark.django_db
def test_shuffled_options_for_the_same_seed_are_in_the_same_order(mock_site_context):
    question = _ten_options()

    first = shuffled_options(question, 777)
    second = shuffled_options(question, 777)

    assert [o.id for o in first] == [o.id for o in second]


@pytest.mark.django_db
def test_shuffled_options_differ_between_seeds(mock_site_context):
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


def _banked_for(user):
    course = CourseFactory()
    topic, _ = place_topic(course)
    question = question_testing_topic(topic)
    record = course_progress_record(course, user)
    finish_topic(record, topic)
    return user, record, question


def _due(user, question):
    return RevisionSchedule.objects.get(user=user, question=question).due


@pytest.mark.django_db
def test_guessed_right_answer_is_due_sooner_than_one_left_alone(mock_site_context):
    left_user, left_record, left_question = _banked_for(UserFactory())
    user, record, question = _banked_for(UserFactory())
    record_answer(
        left_user, left_record, left_question, _correct_ids(left_question), NOW
    )
    review = record_answer(user, record, question, _correct_ids(question), NOW)

    mark_guessed(review)

    assert _due(user, question) < _due(left_user, left_question)


@pytest.mark.django_db
def test_re_rated_schedule_equals_a_first_time_hard(banked):
    user, record, question = banked
    review = record_answer(user, record, question, _correct_ids(question), NOW)
    first_time_hard = scheduler.review(scheduler.new_card(NOW), Rating.Hard, NOW)[0]

    mark_guessed(review)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert _schedule_columns(schedule) == tuple(
        scheduler.columns_from_card(first_time_hard).values()
    )


@pytest.mark.django_db
def test_second_tap_restores_the_good_schedule(banked):
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
def test_guessing_a_wrong_answer_is_refused(banked):
    user, record, question = banked
    review = record_answer(user, record, question, _wrong_ids(question), NOW)

    with pytest.raises(GuessRefused):
        mark_guessed(review)


@pytest.mark.django_db
def test_guessing_a_review_a_later_one_replaced_is_refused(banked):
    user, record, question = banked
    stale = record_answer(user, record, question, _correct_ids(question), NOW)
    record_answer(
        user, record, question, _correct_ids(question), NOW + timedelta(days=3)
    )

    with pytest.raises(GuessRefused):
        mark_guessed(stale)


@pytest.mark.django_db
def test_guessing_leaves_reps_and_lapses_unchanged(banked):
    user, record, question = banked
    review = record_answer(user, record, question, _correct_ids(question), NOW)

    mark_guessed(review)

    schedule = RevisionSchedule.objects.get(user=user, question=question)
    assert (schedule.reps, schedule.lapses) == (1, 0)
