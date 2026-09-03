"""Tests for the queueing email backend.

The payload is the contract: it has to survive a JSONField round trip, and the
message rebuilt from it has to be byte-for-byte as sendable as the one handed in.
The 8bit regression matters most -- serialising to primitives is exactly what
discards the patch the adapter installs, so the worker has to reapply it.
"""

from __future__ import annotations

import email.policy
import json
from email.message import MIMEPart

import pytest
import pytest_django.fixtures

from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import DatabaseError

from freedom_ls.deployment.mail import (
    QueuedEmailBackend,
    UnserialisableMessageError,
    deserialise_message,
    send_serialised_email,
    serialise_message,
)

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
LONG_URL = "https://example.test/account/password/reset/key/" + "a" * 80 + "/"


@pytest.fixture
def upstream_locmem(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Send through locmem, so mail.outbox is the record of what went out.

    Django forces EMAIL_BACKEND to locmem under test; this points the backend
    *behind* the queue at it too, so nothing reaches for a real socket.
    """
    settings.EMAIL_UPSTREAM_BACKEND = LOCMEM


def _message() -> EmailMultiAlternatives:
    message = EmailMultiAlternatives(
        subject="Reset your password",
        body=f"Follow this link: {LONG_URL}",
        from_email="noreply@example.test",
        to=["learner@example.test"],
        cc=["educator@example.test"],
        bcc=["audit@example.test"],
        reply_to=["support@example.test"],
        headers={"X-Tenant": "example"},
    )
    message.attach_alternative(f'<a href="{LONG_URL}">Reset</a>', "text/html")
    return message


def _body_parts(mime_msg: object) -> list:
    return [
        part
        for part in mime_msg.walk()
        if part.get_content_type() in ("text/plain", "text/html")
    ]


class TestSerialisation:
    def test_payload_is_json_serialisable(self) -> None:
        # The real constraint: DBTaskResult stores task arguments in a JSONField.
        assert json.loads(json.dumps(serialise_message(_message())))

    def test_round_trip_preserves_subject_body_and_addresses(self) -> None:
        rebuilt = deserialise_message(serialise_message(_message()))

        assert rebuilt.subject == "Reset your password"
        assert LONG_URL in rebuilt.body
        assert rebuilt.from_email == "noreply@example.test"
        assert rebuilt.to == ["learner@example.test"]
        assert rebuilt.cc == ["educator@example.test"]
        assert rebuilt.bcc == ["audit@example.test"]
        assert rebuilt.reply_to == ["support@example.test"]

    def test_round_trip_preserves_extra_headers(self) -> None:
        rebuilt = deserialise_message(serialise_message(_message()))

        assert rebuilt.extra_headers == {"X-Tenant": "example"}

    def test_round_trip_preserves_the_html_alternative(self) -> None:
        rebuilt = deserialise_message(serialise_message(_message()))

        content, mimetype = rebuilt.alternatives[0]
        assert mimetype == "text/html"
        assert isinstance(content, str)
        assert LONG_URL in content

    def test_round_trip_preserves_content_subtype(self) -> None:
        """allauth sets content_subtype="html" when a prefix has no .txt template."""
        message = EmailMessage(
            subject="s", body="<p>hi</p>", to=["learner@example.test"]
        )
        message.content_subtype = "html"

        rebuilt = deserialise_message(serialise_message(message))

        assert rebuilt.content_subtype == "html"
        assert rebuilt.message().get_content_type() == "text/html"

    def test_round_trip_preserves_a_binary_attachment(self) -> None:
        message = _message()
        message.attach("report.pdf", b"%PDF-1.4 \x00\x01\x02", "application/pdf")

        rebuilt = deserialise_message(serialise_message(message))

        filename, content, mimetype = rebuilt.attachments[0]
        assert (filename, content, mimetype) == (
            "report.pdf",
            b"%PDF-1.4 \x00\x01\x02",
            "application/pdf",
        )

    def test_round_trip_keeps_a_text_attachment_as_text(self) -> None:
        # Django stores text/* content as str and everything else as bytes; the
        # two are not interchangeable when the MIME part is built.
        message = _message()
        message.attach("notes.txt", "plain content", "text/plain")

        rebuilt = deserialise_message(serialise_message(message))

        filename, content, mimetype = rebuilt.attachments[0]
        assert content == "plain content"
        assert isinstance(content, str)
        assert (filename, mimetype) == ("notes.txt", "text/plain")

    def test_a_raw_mime_attachment_is_refused(self) -> None:
        message = _message()
        part = MIMEPart()
        part.set_content("attached")
        message.attach(part)

        with pytest.raises(UnserialisableMessageError):
            serialise_message(message)


class TestWorkerSend:
    """What fls_run_worker does with a queued payload."""

    def test_delivers_through_the_upstream_backend(self, upstream_locmem: None) -> None:
        send_serialised_email(serialise_message(_message()))

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Reset your password"

    def test_reapplies_8bit_encoding_after_the_round_trip(
        self, upstream_locmem: None
    ) -> None:
        """The regression this whole design has to not introduce.

        set_8bit_encoding patches the message instance, so serialising to
        primitives drops it. Without the worker reapplying it, quoted-printable
        wraps the reset URL at 76 characters and the link stops working -- with
        mandatory email verification, that blocks registration outright.
        """
        send_serialised_email(serialise_message(_message()))

        parts = _body_parts(mail.outbox[0].message(policy=email.policy.SMTP))
        assert parts
        for part in parts:
            assert part["Content-Transfer-Encoding"] == "8bit"
            assert "=\n" not in part.get_payload()
            assert LONG_URL in part.get_payload()


@pytest.mark.usefixtures("upstream_locmem")
class TestQueuedEmailBackend:
    def test_send_messages_delivers_end_to_end(self) -> None:
        # TASKS is ImmediateBackend under test settings, so the task runs inline.
        sent = QueuedEmailBackend().send_messages([_message()])

        assert sent == 1
        assert len(mail.outbox) == 1

    def test_enqueues_one_task_per_message(self, mocker) -> None:
        backend = mocker.patch("freedom_ls.deployment.mail.default_task_backend")

        sent = QueuedEmailBackend().send_messages([_message(), _message()])

        assert sent == 2
        assert backend.enqueue.call_count == 2

    def test_the_enqueued_payload_is_the_serialised_message(self, mocker) -> None:
        backend = mocker.patch("freedom_ls.deployment.mail.default_task_backend")

        QueuedEmailBackend().send_messages([_message()])

        payload = backend.enqueue.call_args.kwargs["args"][0]
        assert payload["subject"] == "Reset your password"

    def test_a_message_addressed_to_nobody_is_skipped(self, mocker) -> None:
        backend = mocker.patch("freedom_ls.deployment.mail.default_task_backend")

        sent = QueuedEmailBackend().send_messages(
            [EmailMessage(subject="s", body="b", to=[])]
        )

        assert sent == 0
        backend.enqueue.assert_not_called()

    def test_an_unqueueable_message_is_sent_inline_rather_than_dropped(
        self, mocker
    ) -> None:
        backend = mocker.patch("freedom_ls.deployment.mail.default_task_backend")
        message = _message()
        part = MIMEPart()
        part.set_content("attached")
        message.attach(part)

        sent = QueuedEmailBackend().send_messages([message])

        assert sent == 1
        backend.enqueue.assert_not_called()
        assert len(mail.outbox) == 1

    def test_an_unreachable_queue_raises(self, mocker) -> None:
        # The database being down means whatever triggered the mail has already
        # failed, so this surfaces rather than delivering a link to a row that
        # was never written.
        mocker.patch(
            "freedom_ls.deployment.mail.default_task_backend.enqueue",
            side_effect=DatabaseError("connection refused"),
        )

        with pytest.raises(DatabaseError):
            QueuedEmailBackend().send_messages([_message()])

    def test_an_unreachable_queue_is_swallowed_when_fail_silently(self, mocker) -> None:
        mocker.patch(
            "freedom_ls.deployment.mail.default_task_backend.enqueue",
            side_effect=DatabaseError("connection refused"),
        )

        sent = QueuedEmailBackend(fail_silently=True).send_messages([_message()])

        assert sent == 0
        assert mail.outbox == []


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

    QueuedEmailBackend().send_messages([_message()])

    row = DBTaskResult.objects.get()
    stored = row.args_kwargs["args"][0]
    assert deserialise_message(stored).subject == "Reset your password"
    assert mail.outbox == [], "the worker sends it, not the request"
