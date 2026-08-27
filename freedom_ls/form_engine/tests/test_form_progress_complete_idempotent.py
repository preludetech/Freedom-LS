"""Tests for FormProgress.complete() idempotency."""

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
