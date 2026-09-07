"""Tests for QueuedEmailBackend -- what happens to a message in the request."""

from __future__ import annotations

from email.message import MIMEPart

import pytest
import pytest_django.fixtures

from django.core import mail
from django.core.mail import EmailMessage
from django.db import DatabaseError

from freedom_ls.mail.backends import QueuedEmailBackend, QueuedEmailNotSentError
from freedom_ls.mail.serialisation import deserialise_message
from freedom_ls.mail.tests.conftest import (
    LOCMEM,
    REFUSING,
    make_message,
    raw_attachment_part,
)


@pytest.mark.usefixtures("upstream_locmem")
class TestQueuedEmailBackend:
    def test_send_messages_delivers_end_to_end(self) -> None:
        # TASKS is ImmediateBackend under test settings, so the task runs inline.
        sent = QueuedEmailBackend().send_messages([make_message()])

        assert sent == 1
        assert len(mail.outbox) == 1

    def test_enqueues_one_task_per_message(self, mocker) -> None:
        backend = mocker.patch("freedom_ls.mail.backends.default_task_backend")

        sent = QueuedEmailBackend().send_messages([make_message(), make_message()])

        assert sent == 2
        assert backend.enqueue.call_count == 2

    def test_the_enqueued_payload_is_the_serialised_message(self, mocker) -> None:
        backend = mocker.patch("freedom_ls.mail.backends.default_task_backend")

        QueuedEmailBackend().send_messages([make_message()])

        payload = backend.enqueue.call_args.kwargs["args"][0]
        assert payload["subject"] == "Reset your password"

    def test_a_message_addressed_to_nobody_is_skipped(self, mocker) -> None:
        backend = mocker.patch("freedom_ls.mail.backends.default_task_backend")

        sent = QueuedEmailBackend().send_messages(
            [EmailMessage(subject="s", body="b", to=[])]
        )

        assert sent == 0
        backend.enqueue.assert_not_called()

    def test_an_unqueueable_message_is_sent_inline_rather_than_dropped(
        self, mocker
    ) -> None:
        backend = mocker.patch("freedom_ls.mail.backends.default_task_backend")
        message = make_message()
        part = MIMEPart()
        part.set_content("attached")
        message.attach(part)

        sent = QueuedEmailBackend().send_messages([message])

        assert sent == 1
        backend.enqueue.assert_not_called()
        assert len(mail.outbox) == 1

    def test_a_real_attachment_takes_the_inline_path_with_its_file_intact(
        self, mocker
    ) -> None:
        """The case the fallback exists for, with a part built as callers build one."""
        backend = mocker.patch("freedom_ls.mail.backends.default_task_backend")
        message = make_message()
        message.attach(raw_attachment_part())

        sent = QueuedEmailBackend().send_messages([message])

        assert sent == 1
        backend.enqueue.assert_not_called()
        assert len(mail.outbox) == 1
        # The file itself, not just an attachment-shaped object: the bug this
        # covers queued a text part named "Content-Type" and dropped the PDF.
        attachment = mail.outbox[0].attachments[0]
        assert attachment.get_filename() == "report.pdf"
        assert attachment.get_content() == b"%PDF-1.4 \x00\x01\x02"

    def test_an_unreachable_queue_raises(self, mocker) -> None:
        # The database being down means whatever triggered the mail has already
        # failed, so this surfaces rather than delivering a link to a row that
        # was never written.
        mocker.patch(
            "freedom_ls.mail.backends.default_task_backend.enqueue",
            side_effect=DatabaseError("connection refused"),
        )

        with pytest.raises(DatabaseError):
            QueuedEmailBackend().send_messages([make_message()])

    def test_an_unreachable_queue_is_swallowed_when_fail_silently(self, mocker) -> None:
        mocker.patch(
            "freedom_ls.mail.backends.default_task_backend.enqueue",
            side_effect=DatabaseError("connection refused"),
        )

        sent = QueuedEmailBackend(fail_silently=True).send_messages([make_message()])

        assert sent == 0
        assert mail.outbox == []

    def test_a_failed_inline_send_raises(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        # TASKS is ImmediateBackend under test settings, so the send has already
        # been attempted and failed by the time enqueue() returns.
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING

        with pytest.raises(QueuedEmailNotSentError, match="ConnectionRefusedError"):
            QueuedEmailBackend().send_messages([make_message()])

    def test_a_failed_inline_send_is_swallowed_when_fail_silently(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING

        sent = QueuedEmailBackend(fail_silently=True).send_messages([make_message()])

        assert sent == 0


@pytest.mark.django_db
def test_payload_survives_the_database_task_backend(
    settings: pytest_django.fixtures.SettingsWrapper,
) -> None:
    """The production path: the payload has to round-trip through Postgres JSON.

    Nothing else in the suite exercises DatabaseBackend, which is what production
    uses -- ImmediateBackend never serialises anything to a column.
    """
    from django_tasks_db.models import DBTaskResult

    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
    settings.EMAIL_UPSTREAM_BACKEND = LOCMEM

    sent = QueuedEmailBackend().send_messages([make_message()])

    row = DBTaskResult.objects.get()
    stored = row.args_kwargs["args"][0]
    assert deserialise_message(stored).subject == "Reset your password"
    assert mail.outbox == [], "the worker sends it, not the request"
    # The task has not run, so its result is READY rather than FAILED: a queue the
    # request cannot see the outcome of still counts the message as accepted.
    assert sent == 1
