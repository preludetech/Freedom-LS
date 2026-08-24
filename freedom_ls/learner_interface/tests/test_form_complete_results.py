"""What the results page tells a learner about the answers it marked wrong."""

from __future__ import annotations

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

from .conftest import course_with_form


def _checkbox_quiz(**form_kwargs):
    """A one-question checkbox quiz with two correct options and one incorrect."""
    form = FormFactory(
        title="Multi-Select Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
        quiz_show_incorrect=True,
        **form_kwargs,
    )
    page = FormPageFactory(form=form, title="Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="Which of these are mammals?",
        type="checkboxes",
        order=0,
    )
    dolphin = QuestionOptionFactory(
        question=question, text="Dolphin", value="dolphin", order=0, correct=True
    )
    bat = QuestionOptionFactory(
        question=question, text="Bat", value="bat", order=1, correct=True
    )
    crocodile = QuestionOptionFactory(
        question=question, text="Crocodile", value="crocodile", order=2, correct=False
    )
    return form, question, dolphin, bat, crocodile


def _registered_learner(course):
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user, collection=course, is_active=True
    )
    return user


def _results(client_factory, user, course):
    client = client_factory(user)
    return client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )


@pytest.mark.django_db
def test_a_question_left_blank_is_named_in_the_review_section(
    mock_site_context, logged_in_client
):
    """Failing a learner over a blank question and then not naming it tells them nothing."""
    form, _question, _dolphin, _bat, _crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Blank Course", slug="blank-course")
    user = _registered_learner(course)
    FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )

    content = _results(logged_in_client, user, course).content.decode()

    assert 'data-testid="incorrect-answers-section"' in content
    assert "Which of these are mammals?" in content
    assert "did not answer" in content


@pytest.mark.django_db
def test_a_correctly_ticked_option_is_not_marked_as_an_error(
    mock_site_context, logged_in_client
):
    """The answer as a whole is wrong, but the ticks that were right must not read as wrong."""
    form, question, dolphin, bat, crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Glyph Course", slug="glyph-course")
    user = _registered_learner(course)
    attempt = FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat, crocodile)

    response = _results(logged_in_client, user, course)

    content = response.content.decode()
    your_answer = content.split('data-testid="learner-answer-')[1].split(
        'data-testid="correct-answer-'
    )[0]
    assert your_answer.count("Marked correct") == 2
    assert your_answer.count("Marked incorrect") == 1
    # The answer as a whole is still wrong; the verdict moves to the question.
    assert "Marked wrong" in content


@pytest.mark.django_db
def test_a_stale_stored_score_is_explained(mock_site_context, logged_in_client):
    """A score frozen under the old marking contradicts the review list below it."""
    form, question, dolphin, bat, crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Legacy Course", slug="legacy-course")
    user = _registered_learner(course)
    attempt = FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        # What ticking every option scored before checkbox marking became exact.
        scores={"score": 1, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat, crocodile)

    response = _results(logged_in_client, user, course)

    assert response.context["stored_score_outdated"] is True
    assert "not been re-marked" in response.content.decode()


@pytest.mark.django_db
def test_a_current_score_carries_no_stale_score_note(
    mock_site_context, logged_in_client
):
    """An attempt scored under the current rules has nothing to explain away."""
    form, question, dolphin, bat, _crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Current Course", slug="current-course")
    user = _registered_learner(course)
    attempt = FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat)

    response = _results(logged_in_client, user, course)

    assert response.context["stored_score_outdated"] is False
    assert "not been re-marked" not in response.content.decode()


@pytest.mark.django_db
def test_a_changed_question_count_is_explained(mock_site_context, logged_in_client):
    """A quiz that lost a question shows a stale percentage the score alone cannot catch."""
    form, question, dolphin, bat, _crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Shrunk Course", slug="shrunk-course")
    user = _registered_learner(course)
    attempt = FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        # 1 of 2 when it was sat; the second question has since been removed, so
        # the same answers score 1 of 1 today — right score, wrong total.
        scores={"score": 1, "max_score": 2},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat)

    response = _results(logged_in_client, user, course)

    assert response.context["stored_score_outdated"] is True
    assert "not been re-marked" in response.content.decode()


@pytest.mark.django_db
def test_a_completed_survey_does_not_promise_marking(
    mock_site_context, logged_in_client
):
    """Nothing marks a CATEGORY_VALUE_SUM form, so the page must not say marking is coming."""
    form = FormFactory(
        title="Confidence Survey", strategy=FormStrategy.CATEGORY_VALUE_SUM
    )
    course = course_with_form(form, title="Survey Course", slug="survey-course")
    user = _registered_learner(course)
    FormProgressFactory(user=user, form=form, completed_time=timezone.now(), scores={})

    content = _results(logged_in_client, user, course).content.decode()

    assert "marking is in progress" not in content
    assert "being reviewed" not in content
    assert "Confidence Survey" in content
