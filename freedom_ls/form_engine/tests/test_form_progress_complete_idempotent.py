"""Tests for FormProgress.complete() idempotency and finalise_stale_incomplete."""

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import FormProgress


@pytest.mark.django_db
def test_complete_sets_completed_time(mock_site_context):
    """Completing an attempt stamps it with the time it finished."""
    progress = FormProgressFactory(user=UserFactory(), form=FormFactory())

    progress.complete()

    assert progress.completed_time is not None


@pytest.mark.django_db
def test_complete_twice_does_not_change_completed_time(mock_site_context):
    """Completing an already-completed attempt leaves its finishing time alone."""
    progress = FormProgressFactory(user=UserFactory(), form=FormFactory())
    progress.complete()
    first_completed_time = progress.completed_time

    progress.complete()
    assert progress.completed_time == first_completed_time


@pytest.mark.django_db
def test_complete_twice_does_not_re_score(mock_site_context):
    """Completing an already-completed attempt does not re-score it.

    The stored scores are replaced with a value scoring could never produce, so
    a second run would be visible.
    """
    progress = FormProgressFactory(user=UserFactory(), form=FormFactory())
    progress.complete()
    FormProgress.objects.filter(pk=progress.pk).update(
        scores={"score": 999, "max_score": 999}
    )
    progress.refresh_from_db()

    progress.complete()

    assert progress.scores == {"score": 999, "max_score": 999}


@pytest.mark.django_db
def test_finalise_stale_incomplete_completes_submit_on_exit_attempt(mock_site_context):
    """An abandoned attempt at a submit-on-exit form is completed as it stands."""
    user = UserFactory()
    form = FormFactory(submit_on_exit=True)
    incomplete = FormProgressFactory(user=user, form=form)

    result = FormProgress.finalise_stale_incomplete(user, form)

    assert result is not None
    assert result.pk == incomplete.pk
    incomplete.refresh_from_db()
    assert incomplete.completed_time is not None


@pytest.mark.django_db
def test_finalise_stale_incomplete_returns_none_for_save_on_exit_form(
    mock_site_context,
):
    """An abandoned attempt at a save-on-exit form stays open, to be resumed later."""
    user = UserFactory()
    form = FormFactory(submit_on_exit=False)
    incomplete = FormProgressFactory(user=user, form=form)

    result = FormProgress.finalise_stale_incomplete(user, form)

    assert result is None
    incomplete.refresh_from_db()
    assert incomplete.completed_time is None


@pytest.mark.django_db
def test_finalise_stale_incomplete_returns_none_when_no_incomplete_attempt(
    mock_site_context,
):
    """There is nothing to finalise when the learner has no attempt under way."""
    user = UserFactory()
    form = FormFactory(submit_on_exit=True)

    result = FormProgress.finalise_stale_incomplete(user, form)

    assert result is None
