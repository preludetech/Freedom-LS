"""Tests for the form_engine query helpers that read an attempt's verdict."""

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
from freedom_ls.form_engine.queries import (
    attempt_completes_form,
    completed_form_ids_by_user,
    quiz_verdict,
)

# A scores dict written under another strategy: populated, but with no quiz
# score to read. `qa_complete_form` used to write exactly this onto quiz forms.
NON_QUIZ_SCORES = {"Satisfaction": 5, "Recommendation": 3}


def _quiz_attempt_with_non_quiz_scores(user=None) -> FormProgress:
    """A completed QUIZ attempt holding scores that were not written by score_quiz."""
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=80)
    page = FormPageFactory(form=form, title="Quiz Page", order=0)
    FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    attempt: FormProgress = FormProgressFactory(
        user=user or UserFactory(),
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
def test_completed_form_ids_by_user_does_not_raise_on_non_quiz_shaped_scores(
    mock_site_context,
):
    """Regression: one malformed row used to abort the whole scan with KeyError,
    taking `recalculate_progress_percentages` and cohort reporting down with it."""
    user = UserFactory()
    attempt = _quiz_attempt_with_non_quiz_scores(user=user)

    completed = completed_form_ids_by_user([user.pk])

    assert completed[user.pk] == {attempt.form_id}


@pytest.mark.django_db
def test_quiz_verdict_returns_none_for_non_quiz_shaped_scores(mock_site_context):
    """No readable percentage means no verdict to give, rather than an exception
    escaping into the course outline."""
    attempt = _quiz_attempt_with_non_quiz_scores()

    assert quiz_verdict(attempt.form, attempt) is None
