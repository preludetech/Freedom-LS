"""Tests for the `form_attempt_completed` signal fired by `FormProgress.complete()`.

Course-progress recalculation triggered by this signal is asserted elsewhere, in
the tests owned by the app that defines `CourseProgress`, so this module stays
free of that app's imports.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.form_engine.signals import form_attempt_completed


@pytest.fixture
def completions() -> Iterator[list[tuple[User, Form]]]:
    """Every `form_attempt_completed` send during one test, in order."""
    received: list[tuple[User, Form]] = []

    def _capture(
        sender: type[FormProgress], user: User, form: Form, **kwargs: object
    ) -> None:
        received.append((user, form))

    form_attempt_completed.connect(_capture)
    yield received
    form_attempt_completed.disconnect(_capture)


@pytest.mark.django_db
def test_complete_sends_form_attempt_completed_with_user_and_form(
    mock_site_context, completions
) -> None:
    """Completing an attempt sends `form_attempt_completed` carrying the user and form."""
    user = UserFactory()
    form = FormFactory()
    progress = FormProgressFactory(user=user, form=form)

    progress.complete()

    assert completions == [(user, form)]


@pytest.mark.django_db
def test_complete_sends_exactly_once_per_completion(
    mock_site_context, completions
) -> None:
    """A second call to complete() and the multiple saves inside the first call
    each still produce exactly one send in total, not one per save or per call."""
    progress = FormProgressFactory(user=UserFactory(), form=FormFactory())

    progress.complete()
    progress.complete()

    assert len(completions) == 1
