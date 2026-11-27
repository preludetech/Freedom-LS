"""Tests for the sweep that completes sittings nobody came back to."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from pytest_mock import MockerFixture

from django.contrib.sites.models import Site
from django.db import DatabaseError, connection, transaction

from freedom_ls.form_engine.conditions import SittingPath
from freedom_ls.form_engine.enums import FormStrategy
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import (
    EXPIRY_GRACE,
    CompletionReason,
    Form,
    FormProgress,
)
from freedom_ls.form_engine.signals import form_attempt_completed
from freedom_ls.form_engine.sweeps import (
    ExpiredSittingSweep,
    complete_expired_sittings,
)
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

START = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)
LIMIT_MINUTES = 30
EXPIRY = START + timedelta(minutes=LIMIT_MINUTES)
PAST_GRACE = EXPIRY + EXPIRY_GRACE + timedelta(seconds=1)


def _sitting(limit: int | None = LIMIT_MINUTES) -> FormProgress:
    """An open sitting that started at START, on a form with the given limit."""
    sitting: FormProgress = FormProgressFactory(
        form=FormFactory(strategy=FormStrategy.QUIZ, time_limit_minutes=limit),
        completed_time=None,
    )
    # start_time is auto_now_add, so only an update can place it.
    FormProgress._base_manager.filter(pk=sitting.pk).update(start_time=START)
    return sitting


def _reload(sitting: FormProgress) -> FormProgress:
    return FormProgress._base_manager.get(pk=sitting.pk)


@pytest.mark.django_db
def test_expired_sittings_on_every_site_complete_as_time_expired() -> None:
    sittings = []
    for _ in range(2):
        with site_context(SiteFactory()):
            sittings.append(_sitting())

    with time_machine.travel(PAST_GRACE, tick=False):
        result = complete_expired_sittings()

    reloaded = [_reload(sitting) for sitting in sittings]
    assert result == ExpiredSittingSweep(completed=2, failed=0)
    assert [r.completion_reason for r in reloaded] == [
        CompletionReason.TIME_EXPIRED
    ] * 2
    assert [r.completed_time for r in reloaded] == [EXPIRY] * 2


@pytest.mark.django_db
def test_a_sitting_inside_its_grace_window_is_left_open(mock_site_context) -> None:
    sitting = _sitting()

    with time_machine.travel(EXPIRY + EXPIRY_GRACE, tick=False):
        result = complete_expired_sittings()

    assert result == ExpiredSittingSweep(completed=0, failed=0)
    assert _reload(sitting).completed_time is None


@pytest.mark.django_db
def test_an_unexpired_sitting_is_left_open(mock_site_context) -> None:
    sitting = _sitting()

    with time_machine.travel(EXPIRY - timedelta(minutes=1), tick=False):
        result = complete_expired_sittings()

    assert result.completed == 0
    assert _reload(sitting).completed_time is None


@pytest.mark.django_db
def test_an_untimed_sitting_is_left_open(mock_site_context) -> None:
    sitting = _sitting(limit=None)

    with time_machine.travel(PAST_GRACE + timedelta(days=30), tick=False):
        result = complete_expired_sittings()

    assert result.completed == 0
    assert _reload(sitting).completed_time is None


@pytest.mark.django_db
@pytest.mark.parametrize("error", [ValueError, DatabaseError, RuntimeError])
def test_a_sitting_whose_completion_raises_is_counted_and_the_next_still_completes(
    mock_site_context: Site, mocker: MockerFixture, error: type[Exception]
) -> None:
    first, second = _sitting(), _sitting()
    real_score = FormProgress.score

    def score(self: FormProgress, path: SittingPath) -> None:
        if self.pk == first.pk:
            raise error("malformed quiz")
        real_score(self, path)

    mocker.patch.object(FormProgress, "score", score)
    captured = mocker.patch(
        "freedom_ls.form_engine.sweeps.sentry_sdk.capture_exception"
    )

    with time_machine.travel(PAST_GRACE, tick=False):
        result = complete_expired_sittings()

    assert result == ExpiredSittingSweep(completed=1, failed=1)
    assert _reload(first).completed_time is None
    assert _reload(second).completed_time is not None
    assert captured.call_count == 1


@pytest.mark.django_db
def test_a_sitting_whose_limit_was_raised_after_it_was_picked_is_left_open(
    mock_site_context: Site, mocker: MockerFixture
) -> None:
    sitting = _sitting()
    real_complete_if_expired = FormProgress.complete_if_expired

    def raise_the_limit_first(self: FormProgress, now: datetime) -> bool:
        Form._base_manager.filter(pk=sitting.form_id).update(time_limit_minutes=600)
        return real_complete_if_expired(self, now)

    mocker.patch.object(FormProgress, "complete_if_expired", raise_the_limit_first)

    with time_machine.travel(PAST_GRACE, tick=False):
        result = complete_expired_sittings()

    assert result == ExpiredSittingSweep(completed=0, failed=0)
    assert _reload(sitting).completed_time is None


@pytest.mark.django_db(transaction=True)
def test_the_sweep_holds_no_sitting_lock_while_course_progress_is_updated(
    mock_site_context: Site,
) -> None:
    """A receiver of the completion signal, as the course progress update is,
    must find the sitting's row lock already released: a request takes the
    course progress lock first and the sitting's second."""
    sitting = _sitting()
    lockable: list[bool] = []

    def try_the_lock_from_another_connection() -> None:
        try:
            with transaction.atomic():
                lockable.append(
                    FormProgress._base_manager.select_for_update(skip_locked=True)
                    .filter(pk=sitting.pk)
                    .exists()
                )
        finally:
            connection.close()

    def receiver(sender: type[FormProgress], **kwargs: object) -> None:
        other = threading.Thread(target=try_the_lock_from_another_connection)
        other.start()
        other.join(timeout=10)

    form_attempt_completed.connect(receiver)
    try:
        with time_machine.travel(PAST_GRACE, tick=False):
            result = complete_expired_sittings()
    finally:
        form_attempt_completed.disconnect(receiver)

    assert result == ExpiredSittingSweep(completed=1, failed=0)
    assert lockable == [True]
