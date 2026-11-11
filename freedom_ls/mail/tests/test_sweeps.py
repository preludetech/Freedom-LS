"""Tests for the mail sweeps that housekeeping runs."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
import pytest_django.fixtures
import time_machine
from django_tasks_db.models import DBTaskResult
from pytest_mock import MockerFixture

from django.core.mail import EmailMessage
from django.db import DatabaseError
from django.utils import timezone

from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.sweeps import (
    STUCK_LAST_ERROR,
    STUCK_MESSAGE,
    prune_outbound_email,
    recover_stuck_outbound_email,
    requeue_due_outbound_email,
)
from freedom_ls.mail.tasks import send_outbound_email

NOW = "2026-01-01T12:00:00+00:00"
GRACE_SECONDS = 300
STUCK_WINDOW_SECONDS = 3600
MAX_ATTEMPTS = 6
RETENTION_DAYS = 30
PAYLOAD_DAYS = 3


def hours_ago(hours: int) -> datetime:
    return timezone.now() - timedelta(hours=hours)


@pytest.fixture(autouse=True)
def frozen_now() -> Iterator[None]:
    with time_machine.travel(NOW, tick=False):
        yield


@pytest.fixture(autouse=True)
def pinned_sweep_settings(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    settings.HOUSEKEEPING_DUE_EMAIL_GRACE_SECONDS = GRACE_SECONDS
    settings.HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE = 500
    settings.HOUSEKEEPING_STUCK_EMAIL_MAX_AGE_SECONDS = STUCK_WINDOW_SECONDS
    settings.EMAIL_MAX_ATTEMPTS = MAX_ATTEMPTS
    settings.EMAIL_OUTBOUND_RETENTION_DAYS = RETENTION_DAYS
    settings.EMAIL_FAILED_PAYLOAD_RETENTION_DAYS = PAYLOAD_DAYS


@pytest.mark.django_db
class TestRequeueDueOutboundEmail:
    def test_overdue_failed_row_is_enqueued_with_only_its_id(
        self, database_task_backend: None
    ) -> None:
        email = OutboundEmailFactory(failed=True, next_attempt_at=hours_ago(1))

        requeued = requeue_due_outbound_email()

        queued = DBTaskResult.objects.get()
        assert requeued == 1
        assert queued.args_kwargs == {"args": [str(email.pk)], "kwargs": {}}

    def test_overdue_pending_row_is_enqueued_undeferred(
        self, database_task_backend: None
    ) -> None:
        OutboundEmailFactory(next_attempt_at=hours_ago(1))

        requeue_due_outbound_email()

        queued = DBTaskResult.objects.get()
        assert queued.run_after.year == 9999

    def test_requeued_row_is_due_now(self, database_task_backend: None) -> None:
        email = OutboundEmailFactory(next_attempt_at=hours_ago(1))

        requeue_due_outbound_email()

        email.refresh_from_db()
        assert email.next_attempt_at == timezone.now()

    def test_row_inside_the_grace_period_is_left_alone(
        self, database_task_backend: None
    ) -> None:
        OutboundEmailFactory(
            next_attempt_at=timezone.now() - timedelta(seconds=GRACE_SECONDS - 1)
        )

        requeued = requeue_due_outbound_email()

        assert requeued == 0
        assert DBTaskResult.objects.count() == 0

    def test_row_due_in_the_future_is_left_alone(
        self, database_task_backend: None
    ) -> None:
        OutboundEmailFactory(failed=True, next_attempt_at=hours_ago(-1))

        requeued = requeue_due_outbound_email()

        assert requeued == 0
        assert DBTaskResult.objects.count() == 0

    @pytest.mark.parametrize(
        "trait", ["sending", "sent", "permanent_failure", "dead_letter"]
    )
    def test_overdue_row_in_a_non_retryable_status_is_left_alone(
        self, database_task_backend: None, trait: str
    ) -> None:
        OutboundEmailFactory(next_attempt_at=hours_ago(1), **{trait: True})

        requeued = requeue_due_outbound_email()

        assert requeued == 0
        assert DBTaskResult.objects.count() == 0

    def test_second_run_straight_after_the_first_enqueues_nothing(
        self, database_task_backend: None
    ) -> None:
        OutboundEmailFactory(next_attempt_at=hours_ago(1))
        requeue_due_outbound_email()

        requeued = requeue_due_outbound_email()

        assert requeued == 0
        assert DBTaskResult.objects.count() == 1

    def test_more_overdue_rows_than_the_batch_size_enqueues_the_oldest(
        self,
        database_task_backend: None,
        settings: pytest_django.fixtures.SettingsWrapper,
    ) -> None:
        settings.HOUSEKEEPING_EMAIL_REQUEUE_BATCH_SIZE = 2
        oldest = OutboundEmailFactory(next_attempt_at=hours_ago(3))
        second = OutboundEmailFactory(next_attempt_at=hours_ago(2))
        OutboundEmailFactory(next_attempt_at=hours_ago(1))

        requeued = requeue_due_outbound_email()

        queued_ids = {
            queued.args_kwargs["args"][0] for queued in DBTaskResult.objects.all()
        }
        assert requeued == 2
        assert queued_ids == {str(oldest.pk), str(second.pk)}

    def test_sweep_sends_nothing(
        self, database_task_backend: None, mailoutbox: list[EmailMessage]
    ) -> None:
        OutboundEmailFactory(next_attempt_at=hours_ago(1))

        requeue_due_outbound_email()

        assert mailoutbox == []

    def test_enqueue_failure_leaves_the_due_time_unchanged(
        self, database_task_backend: None, mocker: MockerFixture
    ) -> None:
        email = OutboundEmailFactory(next_attempt_at=hours_ago(1))
        original = email.next_attempt_at
        mocker.patch(
            "freedom_ls.mail.sweeps.enqueue_send", side_effect=DatabaseError("down")
        )

        with pytest.raises(DatabaseError):
            requeue_due_outbound_email()

        assert OutboundEmail.objects.get(pk=email.pk).next_attempt_at == original


def stuck_since(seconds_past_window: int) -> datetime:
    return timezone.now() - timedelta(
        seconds=STUCK_WINDOW_SECONDS + seconds_past_window
    )


@pytest.mark.django_db
class TestRecoverStuckOutboundEmail:
    def test_stuck_row_below_the_cap_becomes_failed_and_due_now(
        self, database_task_backend: None
    ) -> None:
        email = OutboundEmailFactory(
            sending=True, attempt_count=2, last_attempt_at=stuck_since(1)
        )

        dead_lettered = recover_stuck_outbound_email()

        email.refresh_from_db()
        assert dead_lettered == []
        assert email.status == OutboundEmail.Status.FAILED
        assert email.next_attempt_at == timezone.now()

    def test_recovered_row_gets_one_undeferred_task(
        self, database_task_backend: None
    ) -> None:
        email = OutboundEmailFactory(sending=True, last_attempt_at=stuck_since(1))

        recover_stuck_outbound_email()

        queued = DBTaskResult.objects.get()
        assert queued.args_kwargs == {"args": [str(email.pk)], "kwargs": {}}
        assert queued.run_after.year == 9999

    def test_recovered_row_raises_one_sentry_message(
        self, database_task_backend: None, sentry_events: list[dict]
    ) -> None:
        OutboundEmailFactory(sending=True, last_attempt_at=stuck_since(1))

        recover_stuck_outbound_email()

        assert [event["message"] for event in sentry_events] == [STUCK_MESSAGE]

    def test_empty_last_error_becomes_the_stuck_note(
        self, database_task_backend: None
    ) -> None:
        email = OutboundEmailFactory(
            sending=True, last_attempt_at=stuck_since(1), last_error=""
        )

        recover_stuck_outbound_email()

        email.refresh_from_db()
        assert email.last_error == STUCK_LAST_ERROR

    def test_existing_last_error_is_kept(self, database_task_backend: None) -> None:
        email = OutboundEmailFactory(
            sending=True,
            last_attempt_at=stuck_since(1),
            last_error="builtins.TimeoutError: upstream timed out",
        )

        recover_stuck_outbound_email()

        email.refresh_from_db()
        assert email.last_error == "builtins.TimeoutError: upstream timed out"

    def test_stuck_row_at_the_cap_is_dead_lettered_and_returned(
        self, database_task_backend: None
    ) -> None:
        email = OutboundEmailFactory(
            sending=True, attempt_count=MAX_ATTEMPTS, last_attempt_at=stuck_since(1)
        )

        dead_lettered = recover_stuck_outbound_email()

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.DEAD_LETTER
        assert [row.pk for row in dead_lettered] == [email.pk]

    def test_dead_lettered_row_is_not_enqueued(
        self, database_task_backend: None
    ) -> None:
        OutboundEmailFactory(
            sending=True, attempt_count=MAX_ATTEMPTS, last_attempt_at=stuck_since(1)
        )

        recover_stuck_outbound_email()

        assert DBTaskResult.objects.count() == 0

    def test_dead_lettered_row_raises_one_sentry_message(
        self, database_task_backend: None, sentry_events: list[dict]
    ) -> None:
        OutboundEmailFactory(
            sending=True, attempt_count=MAX_ATTEMPTS, last_attempt_at=stuck_since(1)
        )

        recover_stuck_outbound_email()

        assert [event["message"] for event in sentry_events] == [STUCK_MESSAGE]

    def test_row_sending_for_less_than_the_window_is_left_alone(
        self, database_task_backend: None
    ) -> None:
        email = OutboundEmailFactory(sending=True, last_attempt_at=stuck_since(-1))

        dead_lettered = recover_stuck_outbound_email()

        email.refresh_from_db()
        assert dead_lettered == []
        assert email.status == OutboundEmail.Status.SENDING
        assert DBTaskResult.objects.count() == 0

    def test_recovered_row_is_sent_when_its_task_runs_against_a_working_upstream(
        self,
        database_task_backend: None,
        upstream_locmem: None,
        mailoutbox: list[EmailMessage],
    ) -> None:
        email = OutboundEmailFactory(sending=True, last_attempt_at=stuck_since(1))
        recover_stuck_outbound_email()

        send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.SENT
        assert len(mailoutbox) == 1


def created_days_ago(email: OutboundEmail, days: int) -> OutboundEmail:
    # created_at is auto_now_add, so it can only be moved after the insert.
    OutboundEmail.objects.filter(pk=email.pk).update(
        created_at=timezone.now() - timedelta(days=days)
    )
    return email


def attempted_days_ago(email: OutboundEmail, days: int) -> OutboundEmail:
    OutboundEmail.objects.filter(pk=email.pk).update(
        last_attempt_at=timezone.now() - timedelta(days=days)
    )
    return email


@pytest.mark.django_db
class TestPruneOutboundEmail:
    @pytest.mark.parametrize("trait", ["sent", "permanent_failure", "dead_letter"])
    def test_terminal_row_past_retention_is_deleted(self, trait: str) -> None:
        email = OutboundEmailFactory(**{trait: True})
        created_days_ago(email, RETENTION_DAYS + 1)

        prune_outbound_email()

        assert not OutboundEmail.objects.filter(pk=email.pk).exists()

    @pytest.mark.parametrize("trait", ["sent", "permanent_failure", "dead_letter"])
    def test_terminal_row_inside_retention_is_kept(self, trait: str) -> None:
        email = OutboundEmailFactory(**{trait: True})
        created_days_ago(email, RETENTION_DAYS - 1)

        prune_outbound_email()

        assert OutboundEmail.objects.filter(pk=email.pk).exists()

    @pytest.mark.parametrize(
        "traits",
        [{}, {"failed": True}, {"sending": True}],
        ids=["pending", "failed", "sending"],
    )
    def test_unfinished_row_of_any_age_is_neither_deleted_nor_scrubbed(
        self, traits: dict[str, bool]
    ) -> None:
        email = OutboundEmailFactory(**traits)
        created_days_ago(email, RETENTION_DAYS * 10)
        attempted_days_ago(email, RETENTION_DAYS * 10)

        prune_outbound_email()

        email.refresh_from_db()
        assert email.payload != {}
        assert email.scrubbed_at is None

    @pytest.mark.parametrize("trait", ["permanent_failure", "dead_letter"])
    def test_failed_row_past_payload_window_loses_only_its_body(
        self, trait: str
    ) -> None:
        email = OutboundEmailFactory(**{trait: True})
        attempted_days_ago(email, PAYLOAD_DAYS + 1)
        expected_error = email.last_error

        prune_outbound_email()

        email.refresh_from_db()
        assert email.payload == {}
        assert email.scrubbed_at == timezone.now()
        assert email.recipients == ["learner@example.test"]
        assert email.subject == "Reset your password"
        assert email.last_error == expected_error

    @pytest.mark.parametrize("trait", ["permanent_failure", "dead_letter"])
    def test_failed_row_inside_payload_window_keeps_its_body(self, trait: str) -> None:
        email = OutboundEmailFactory(**{trait: True})
        attempted_days_ago(email, PAYLOAD_DAYS - 1)

        prune_outbound_email()

        email.refresh_from_db()
        assert email.payload != {}
        assert email.scrubbed_at is None

    def test_old_failed_row_resent_recently_keeps_its_body(self) -> None:
        email = OutboundEmailFactory(permanent_failure=True)
        created_days_ago(email, PAYLOAD_DAYS + 10)
        attempted_days_ago(email, 1)

        prune_outbound_email()

        email.refresh_from_db()
        assert email.payload != {}
