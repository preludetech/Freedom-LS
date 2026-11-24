import pytest

from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import FormQuestion, QuestionAnswer
from freedom_ls.form_engine.signals import form_questions_dropped
from freedom_ls.revision.factories import (
    RevisionReviewFactory,
    RevisionScheduleFactory,
)
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.revision.tests.helpers import choice_question


@pytest.fixture
def dropped_question(mock_site_context) -> FormQuestion:
    question = choice_question()
    RevisionScheduleFactory(question=question)
    RevisionReviewFactory(question=question)
    QuestionAnswerFactory(question=question)
    form_questions_dropped.send(sender=FormQuestion, question_ids=[question.pk])
    return question


@pytest.mark.django_db
def test_dropping_a_question_deletes_its_schedules(dropped_question) -> None:
    assert not RevisionSchedule._base_manager.filter(question=dropped_question).exists()


@pytest.mark.django_db
def test_dropping_a_question_deletes_its_reviews(dropped_question) -> None:
    assert not RevisionReview._base_manager.filter(question=dropped_question).exists()


@pytest.mark.django_db
def test_dropping_a_question_keeps_the_question_row(dropped_question) -> None:
    assert FormQuestion._base_manager.filter(pk=dropped_question.pk).exists()


@pytest.mark.django_db
def test_dropping_a_question_keeps_its_quiz_answers(dropped_question) -> None:
    assert QuestionAnswer._base_manager.filter(question=dropped_question).exists()


@pytest.mark.django_db
def test_dropping_a_question_keeps_other_questions_schedules(mock_site_context) -> None:
    other = choice_question()
    RevisionScheduleFactory(question=other)
    dropped = choice_question()

    form_questions_dropped.send(sender=FormQuestion, question_ids=[dropped.pk])

    assert RevisionSchedule._base_manager.filter(question=other).exists()
