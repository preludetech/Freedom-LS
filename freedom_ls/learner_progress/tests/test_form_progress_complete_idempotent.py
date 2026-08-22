"""Tests for FormProgress.complete() idempotency and finalise_stale_incomplete."""

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import FormFactory
from freedom_ls.student_progress.factories import FormProgressFactory
from freedom_ls.student_progress.models import FormProgress


@pytest.mark.django_db
def test_complete_sets_completed_time(mock_site_context):
    """Calling complete() sets completed_time on the FormProgress."""
    user = UserFactory()
    form = FormFactory()
    progress = FormProgressFactory(user=user, form=form)

    assert progress.completed_time is None
    progress.complete()
    assert progress.completed_time is not None


@pytest.mark.django_db
def test_complete_twice_does_not_change_completed_time(mock_site_context):
    """Calling complete() twice does not change the completed_time (idempotent)."""
    user = UserFactory()
    form = FormFactory()
    progress = FormProgressFactory(user=user, form=form)

    progress.complete()
    first_completed_time = progress.completed_time

    progress.complete()
    assert progress.completed_time == first_completed_time


@pytest.mark.django_db
def test_complete_twice_does_not_re_score(mock_site_context):
    """Calling complete() twice does not re-run scoring (scores unchanged after second call)."""
    user = UserFactory()
    form = FormFactory()
    progress = FormProgressFactory(user=user, form=form)

    progress.complete()

    # Modify scores manually to detect if re-scoring would overwrite them
    FormProgress.objects.filter(pk=progress.pk).update(
        scores={"score": 999, "max_score": 999}
    )
    progress.refresh_from_db()

    progress.complete()
    # completed_time is still set so complete() should return early without re-scoring
    # scores should remain at the manually set value, not be overwritten
    assert progress.scores == {"score": 999, "max_score": 999}


@pytest.mark.django_db
def test_finalise_stale_incomplete_completes_submit_on_exit_attempt(mock_site_context):
    """finalise_stale_incomplete completes an incomplete attempt for a submit-on-exit form."""
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
    """finalise_stale_incomplete returns None and leaves attempt untouched for save-on-exit forms."""
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
    """finalise_stale_incomplete returns None when there is no incomplete attempt."""
    user = UserFactory()
    form = FormFactory(submit_on_exit=True)
    # No incomplete attempt exists

    result = FormProgress.finalise_stale_incomplete(user, form)

    assert result is None
