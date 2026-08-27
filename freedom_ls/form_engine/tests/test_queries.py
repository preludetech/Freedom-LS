"""Tests for the form_engine query helpers that read an attempt's verdict."""

from __future__ import annotations

import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormProgress, FormStrategy
from freedom_ls.form_engine.queries import attempt_completes_form, quiz_verdict

# A scores dict written under another strategy: populated, but with no quiz
# score to read. `qa_complete_form` used to write exactly this onto quiz forms.
NON_QUIZ_SCORES = {"Satisfaction": 5, "Recommendation": 3}


def _quiz_attempt_with_non_quiz_scores() -> FormProgress:
    """A completed QUIZ attempt holding scores that were not written by score_quiz."""
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=80)
    page = FormPageFactory(form=form, title="Quiz Page", order=0)
    FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    attempt: FormProgress = FormProgressFactory(
        user=UserFactory(),
        form=form,
        completed_time=timezone.now(),
        scores=NON_QUIZ_SCORES,
    )
    return attempt


@pytest.mark.django_db
def test_attempt_completes_form_treats_non_quiz_shaped_scores_as_complete(
    mock_site_context,
):
    """An attempt with no readable percentage has nothing to measure against the
    pass mark, so it counts as complete — the same treatment an unscored attempt
    already gets."""
    attempt = _quiz_attempt_with_non_quiz_scores()

    assert attempt_completes_form(attempt) is True


@pytest.mark.django_db
def test_quiz_verdict_returns_none_for_non_quiz_shaped_scores(mock_site_context):
    """No readable percentage means no verdict to give, rather than an exception
    escaping into the course outline."""
    attempt = _quiz_attempt_with_non_quiz_scores()

    assert quiz_verdict(attempt.form, attempt) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("strategy", "pass_percentage", "scores"),
    [
        (FormStrategy.QUIZ, 80, {"score": 5, "max_score": 5}),  # a pass
        (FormStrategy.QUIZ, 80, {"score": 1, "max_score": 5}),  # a fail
        (FormStrategy.QUIZ, None, {"score": 1, "max_score": 5}),  # no bar to clear
        (FormStrategy.CATEGORY_VALUE_SUM, None, NON_QUIZ_SCORES),  # a survey
        (FormStrategy.QUIZ, 80, NON_QUIZ_SCORES),  # no percentage to read
        (FormStrategy.QUIZ, 80, None),  # never scored
    ],
)
def test_attempt_completes_form_is_the_positive_spelling_of_quiz_verdict(
    mock_site_context, strategy, pass_percentage, scores
):
    """One rule, two spellings: the finished question and the may-move-on question
    must never reach different answers about the same sitting."""
    form = FormFactory(strategy=strategy, quiz_pass_percentage=pass_percentage)
    attempt: FormProgress = FormProgressFactory(
        user=UserFactory(), form=form, completed_time=timezone.now(), scores=scores
    )

    assert attempt_completes_form(attempt) is (
        quiz_verdict(attempt.form, attempt) is not False
    )
