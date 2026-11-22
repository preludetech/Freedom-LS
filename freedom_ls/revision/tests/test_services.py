from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.form_engine.models import FormProgress, QuestionAnswer
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.revision.services import (
    RevisionSessionState,
    build_session,
    record_answer,
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
    state = RevisionSessionState(question_ids=(uuid4(),), started_at=NOW, index=0)

    assert state.advanced().current_question_id is None
