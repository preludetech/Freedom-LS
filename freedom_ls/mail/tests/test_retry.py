"""Tests for the retry ladder."""

from __future__ import annotations

import random
from datetime import timedelta

import pytest
import pytest_django.fixtures
import time_machine

from django.core.mail import EmailMessage

from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.retry import (
    DEAD_LETTER_MESSAGE,
    next_attempt_delay,
    schedule_retry,
)

NOW = "2026-01-01T12:00:00Z"
LADDER = [10, 20, 30]


@pytest.fixture
def ladder(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    settings.EMAIL_RETRY_DELAYS = LADDER
    settings.EMAIL_RETRY_JITTER_RATIO = 0


@pytest.mark.usefixtures("ladder")
@pytest.mark.parametrize(
    ("attempt_count", "seconds"),
    [(1, 10), (2, 20), (3, 30), (4, 30), (9, 30)],
)
def test_the_delay_follows_the_ladder_and_repeats_its_last_step(
    attempt_count: int, seconds: int
) -> None:
    assert next_attempt_delay(attempt_count) == timedelta(seconds=seconds)


@pytest.mark.usefixtures("ladder")
@pytest.mark.parametrize("seed", range(10))
def test_jitter_only_ever_lengthens_the_delay_within_the_ratio(
    seed: int, settings: pytest_django.fixtures.SettingsWrapper
) -> None:
    settings.EMAIL_RETRY_JITTER_RATIO = 0.5
    random.seed(seed)

    delay = next_attempt_delay(1)

    assert timedelta(seconds=10) <= delay <= timedelta(seconds=15)


@pytest.mark.django_db
@pytest.mark.usefixtures("ladder")
class TestScheduleRetry:
    @time_machine.travel(NOW, tick=False)
    def test_below_the_cap_the_row_is_failed_and_due_after_the_delay(self) -> None:
        email = OutboundEmailFactory(sending=True)

        schedule_retry(email, ConnectionRefusedError("down"))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.FAILED
        assert email.next_attempt_at.isoformat() == "2026-01-01T12:00:10+00:00"
        assert email.last_error == "builtins.ConnectionRefusedError: down"

    def test_under_a_deferring_backend_the_next_attempt_is_enqueued_with_the_row_id(
        self, database_task_backend: None
    ) -> None:
        from django_tasks_db.models import DBTaskResult

        email = OutboundEmailFactory(sending=True)

        schedule_retry(email, ConnectionRefusedError("down"))

        email.refresh_from_db()
        queued = DBTaskResult.objects.get()
        assert queued.args_kwargs == {"args": [str(email.pk)], "kwargs": {}}
        assert queued.run_after == email.next_attempt_at

    def test_under_the_immediate_backend_the_row_stays_failed_and_is_not_sent(
        self, mailoutbox: list[EmailMessage]
    ) -> None:
        email = OutboundEmailFactory(sending=True)

        schedule_retry(email, ConnectionRefusedError("down"))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.FAILED
        assert mailoutbox == []

    def test_at_the_cap_the_row_is_dead_lettered_and_reported_once(
        self,
        settings: pytest_django.fixtures.SettingsWrapper,
        database_task_backend: None,
        sentry_events: list[dict],
    ) -> None:
        from django_tasks_db.models import DBTaskResult

        settings.EMAIL_MAX_ATTEMPTS = 4
        email = OutboundEmailFactory(sending=True, attempt_count=4)

        schedule_retry(email, ConnectionRefusedError("down"))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.DEAD_LETTER
        assert DBTaskResult.objects.count() == 0
        assert [event["message"] for event in sentry_events] == [DEAD_LETTER_MESSAGE]
