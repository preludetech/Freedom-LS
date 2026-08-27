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
    ("strategy", "pass_percentage", "scores", "expected_verdict", "expected_complete"),
    [
        (FormStrategy.QUIZ, 80, {"score": 5, "max_score": 5}, True, True),
        (FormStrategy.QUIZ, 80, {"score": 1, "max_score": 5}, False, False),
        (FormStrategy.QUIZ, None, {"score": 1, "max_score": 5}, None, True),
        (FormStrategy.CATEGORY_VALUE_SUM, None, NON_QUIZ_SCORES, None, True),
        (FormStrategy.QUIZ, 80, NON_QUIZ_SCORES, None, True),
        (FormStrategy.QUIZ, 80, None, None, True),
    ],
    ids=[
        "a pass",
        "a fail",
        "no bar to clear",
        "a survey",
        "no percentage to read",
        "never scored",
    ],
)
def test_only_a_failed_quiz_leaves_its_form_unfinished(
    mock_site_context,
    strategy,
    pass_percentage,
    scores,
    expected_verdict,
    expected_complete,
):
    """One rule, two spellings. `quiz_verdict` answers "did they clear the bar",
    `attempt_completes_form` answers "may they move on", and the only sitting
    that stops a learner is an outright fail -- an unmarkable score is not one.

    Both answers are written out here rather than derived from each other, so a
    change that moved the two in step would still fail.
    """
    form = FormFactory(strategy=strategy, quiz_pass_percentage=pass_percentage)
    attempt: FormProgress = FormProgressFactory(
        user=UserFactory(), form=form, completed_time=timezone.now(), scores=scores
    )

    assert quiz_verdict(attempt.form, attempt) is expected_verdict
    assert attempt_completes_form(attempt) is expected_complete
