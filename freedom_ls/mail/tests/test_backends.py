"""Tests for QueuedEmailBackend -- what happens to a message in the request."""

from __future__ import annotations

from email.message import MIMEPart
from uuid import UUID

import pytest
import pytest_django.fixtures

from django.core import mail
from django.core.mail import EmailMessage
from django.db import DatabaseError, transaction

from freedom_ls.mail.backends import QueuedEmailBackend, QueuedEmailNotSentError
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.serialisation import deserialise_message
from freedom_ls.mail.tests.conftest import (
    LOCMEM,
    REFUSING,
    make_message,
    raw_attachment_part,
)


class _RollBackError(Exception):
    """Raised inside a transaction to force it to roll back."""


def _send_then_roll_back() -> None:
    with transaction.atomic():
        QueuedEmailBackend().send_messages([make_message()])
        raise _RollBackError


@pytest.mark.django_db
@pytest.mark.usefixtures("upstream_locmem")
class TestQueuedEmailBackend:
    def test_send_messages_delivers_end_to_end(
        self, django_capture_on_commit_callbacks
    ) -> None:
        # TASKS is ImmediateBackend under test settings, so the task runs inline.
        with django_capture_on_commit_callbacks(execute=True):
            sent = QueuedEmailBackend().send_messages([make_message()])

        assert sent == 1
        assert len(mail.outbox) == 1
        assert OutboundEmail.objects.get().status == OutboundEmail.Status.SENT

    def test_writes_one_row_per_message(self) -> None:
        sent = QueuedEmailBackend().send_messages([make_message(), make_message()])

        assert sent == 2
        assert OutboundEmail.objects.count() == 2

    def test_a_message_addressed_to_nobody_is_skipped(self) -> None:
        sent = QueuedEmailBackend().send_messages(
            [EmailMessage(subject="s", body="b", to=[])]
        )

        assert sent == 0
        assert OutboundEmail.objects.count() == 0

    def test_an_unqueueable_message_is_sent_inline_rather_than_dropped(self) -> None:
        message = make_message()
        part = MIMEPart()
        part.set_content("attached")
        message.attach(part)

        sent = QueuedEmailBackend().send_messages([message])

        assert sent == 1
        assert OutboundEmail.objects.count() == 0
        assert len(mail.outbox) == 1

    def test_a_real_attachment_takes_the_inline_path_with_its_file_intact(
        self,
    ) -> None:
        """The case the fallback exists for, with a part built as callers build one."""
        message = make_message()
        message.attach(raw_attachment_part())

        sent = QueuedEmailBackend().send_messages([message])

        assert sent == 1
        assert OutboundEmail.objects.count() == 0
        assert len(mail.outbox) == 1
        # The file itself, not just an attachment-shaped object: the bug this
        # covers queued a text part named "Content-Type" and dropped the PDF.
        attachment = mail.outbox[0].attachments[0]
        assert attachment.get_filename() == "report.pdf"
        assert attachment.get_content() == b"%PDF-1.4 \x00\x01\x02"

    def test_an_unreachable_database_raises(self, mocker) -> None:
        # The database being down means whatever triggered the mail has already
        # failed, so this surfaces rather than delivering a link to a row that
        # was never written.
        mocker.patch(
            "freedom_ls.mail.backends.OutboundEmail.objects.create",
            side_effect=DatabaseError("connection refused"),
        )

        with pytest.raises(DatabaseError):
            QueuedEmailBackend().send_messages([make_message()])

    def test_an_unreachable_database_is_swallowed_when_fail_silently(
        self, mocker
    ) -> None:
        mocker.patch(
            "freedom_ls.mail.backends.OutboundEmail.objects.create",
            side_effect=DatabaseError("connection refused"),
        )

        sent = QueuedEmailBackend(fail_silently=True).send_messages([make_message()])

        assert sent == 0
        assert mail.outbox == []

    @pytest.mark.usefixtures("database_task_backend")
    def test_the_row_holds_recipients_subject_and_a_pinned_message_id(self) -> None:
        QueuedEmailBackend().send_messages([make_message()])

        email = OutboundEmail.objects.get()
        assert email.recipients == [
            "learner@example.test",
            "educator@example.test",
            "audit@example.test",
        ]
        assert email.subject == "Reset your password"
        assert email.message_id.startswith("<")
        assert email.payload["extra_headers"]["Message-ID"] == email.message_id

    @pytest.mark.usefixtures("database_task_backend")
    @pytest.mark.parametrize("header", ["Message-ID", "Message-Id", "message-id"])
    def test_a_message_id_the_caller_set_is_kept_whatever_its_case(
        self, header: str
    ) -> None:
        message = make_message()
        message.extra_headers[header] = "<caller@example.test>"

        QueuedEmailBackend().send_messages([message])

        email = OutboundEmail.objects.get()
        id_headers = {
            name: value
            for name, value in email.payload["extra_headers"].items()
            if name.lower() == "message-id"
        }
        assert email.message_id == "<caller@example.test>"
        assert id_headers == {header: "<caller@example.test>"}

    def test_reusing_one_message_object_gives_each_send_its_own_message_id(
        self,
    ) -> None:
        """A caller looping over recipients with one EmailMessage sends distinct
        messages, and a mail host de-duplicating by Message-ID would drop all but
        the first if they shared one."""
        message = make_message()

        QueuedEmailBackend().send_messages([message])
        QueuedEmailBackend().send_messages([message])

        message_ids = set(OutboundEmail.objects.values_list("message_id", flat=True))
        assert len(message_ids) == 2

    def test_the_callers_message_is_left_without_a_message_id(self) -> None:
        message = make_message()

        QueuedEmailBackend().send_messages([message])

        assert "Message-ID" not in message.extra_headers

    def test_a_rolled_back_transaction_leaves_no_row_and_no_task(
        self,
        settings: pytest_django.fixtures.SettingsWrapper,
        django_capture_on_commit_callbacks,
    ) -> None:
        from django_tasks_db.models import DBTaskResult

        settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}

        with (
            django_capture_on_commit_callbacks(execute=True),
            pytest.raises(_RollBackError),
        ):
            _send_then_roll_back()

        assert OutboundEmail.objects.count() == 0
        assert DBTaskResult.objects.count() == 0

    @pytest.mark.usefixtures("database_task_backend")
    def test_inside_a_transaction_a_durable_task_is_enqueued_only_at_commit(
        self, mocker, django_capture_on_commit_callbacks
    ) -> None:
        enqueue = mocker.patch("freedom_ls.mail.backends.enqueue_send")

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            sent = QueuedEmailBackend().send_messages([make_message()])

        assert sent == 1
        assert len(callbacks) == 1
        enqueue.assert_not_called()

        callbacks[0]()

        enqueue.assert_called_once_with(OutboundEmail.objects.get().pk)


@pytest.mark.django_db
class TestInlineFailureReport:
    """An inline task backend has already attempted the send when the backend returns.

    pytest-django wraps each of these tests in a transaction, so they also cover
    a send made inside the caller's own atomic block.
    """

    def test_a_failed_inline_send_raises(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        # TASKS is ImmediateBackend under test settings, so the send has already
        # been attempted and failed by the time enqueue() returns.
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING

        with pytest.raises(QueuedEmailNotSentError, match="ConnectionRefusedError"):
            QueuedEmailBackend().send_messages([make_message()])

    def test_a_failed_inline_send_leaves_the_row_failed_for_a_later_attempt(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING

        with pytest.raises(QueuedEmailNotSentError):
            QueuedEmailBackend().send_messages([make_message()])

        assert OutboundEmail.objects.get().status == OutboundEmail.Status.FAILED

    def test_a_failed_inline_send_is_swallowed_when_fail_silently(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING

        sent = QueuedEmailBackend(fail_silently=True).send_messages([make_message()])

        assert sent == 0

    def test_a_failed_inline_send_inside_an_atomic_block_raises(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING

        with pytest.raises(QueuedEmailNotSentError), transaction.atomic():
            QueuedEmailBackend().send_messages([make_message()])


# transaction=True: the backend defers enqueue to on_commit inside a transaction, so the task row is only written outside one.
@pytest.mark.django_db(transaction=True)
def test_the_database_task_backend_carries_only_the_row_id(
    settings: pytest_django.fixtures.SettingsWrapper,
) -> None:
    """The production path: the task argument is the row id and no message body.

    Nothing else in the suite exercises DatabaseBackend, which is what production
    uses -- ImmediateBackend never serialises anything to a column.
    """
    from django_tasks_db.models import DBTaskResult

    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
    settings.EMAIL_UPSTREAM_BACKEND = LOCMEM

    sent = QueuedEmailBackend().send_messages([make_message()])

    email = OutboundEmail.objects.get()
    task_args = DBTaskResult.objects.get().args_kwargs
    assert task_args == {"args": [str(email.pk)], "kwargs": {}}
    assert UUID(task_args["args"][0]) == email.pk
    assert deserialise_message(email.payload).subject == "Reset your password"
    assert mail.outbox == [], "the worker sends it, not the request"
    # The task has not run, so its result is READY rather than FAILED: a queue the
    # request cannot see the outcome of still counts the message as accepted.
    assert sent == 1
