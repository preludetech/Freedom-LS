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
from freedom_ls.mail.sweeps import requeue_due_outbound_email

NOW = "2026-01-01T12:00:00+00:00"
GRACE_SECONDS = 300


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
