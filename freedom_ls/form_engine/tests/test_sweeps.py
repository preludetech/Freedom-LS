"""Tests for the sweep that completes sittings nobody came back to."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from pytest_mock import MockerFixture

from django.db import connection, transaction

from freedom_ls.form_engine.enums import FormStrategy
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import (
    EXPIRY_GRACE,
    CompletionReason,
    FormProgress,
)
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
def test_a_sitting_whose_completion_raises_is_counted_and_the_next_still_completes(
    mock_site_context, mocker: MockerFixture
) -> None:
    first, second = _sitting(), _sitting()
    real_complete = FormProgress.complete

    def complete(
        self: FormProgress,
        reason: CompletionReason = CompletionReason.LEARNER_SUBMITTED,
    ) -> None:
        if self.pk == first.pk:
            raise ValueError("malformed quiz")
        real_complete(self, reason)

    mocker.patch.object(FormProgress, "complete", complete)

    with time_machine.travel(PAST_GRACE, tick=False):
        result = complete_expired_sittings()

    assert result == ExpiredSittingSweep(completed=1, failed=1)
    assert _reload(first).completed_time is None
    assert _reload(second).completed_time is not None


@pytest.mark.django_db(transaction=True)
def test_a_sitting_another_connection_holds_locked_is_skipped(
    mock_site_context,
) -> None:
    sitting = _sitting()
    locked = threading.Event()
    release = threading.Event()

    def hold_lock() -> None:
        try:
            with transaction.atomic():
                FormProgress._base_manager.select_for_update().get(pk=sitting.pk)
                locked.set()
                release.wait(timeout=10)
        finally:
            connection.close()

    holder = threading.Thread(target=hold_lock)
    holder.start()
    assert locked.wait(timeout=10)
    try:
        with time_machine.travel(PAST_GRACE, tick=False):
            result = complete_expired_sittings()
    finally:
        release.set()
        holder.join()

    assert result == ExpiredSittingSweep(completed=0, failed=0)
    assert _reload(sitting).completed_time is None
