"""Tests for the queued send -- what fls_run_worker does with a row."""

from __future__ import annotations

import email.policy
from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_django.fixtures

from django.core import mail
from django.tasks import TaskResultStatus
from django.utils import timezone

from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.serialisation import serialise_message
from freedom_ls.mail.tasks import (
    enqueue_send,
    send_outbound_email,
    send_serialised_email,
)
from freedom_ls.mail.tests.conftest import (
    LONG_URL,
    REFUSING,
    body_parts,
    make_message,
)


class TestWorkerSend:
    """What fls_run_worker does with a queued payload."""

    def test_delivers_through_the_upstream_backend(self, upstream_locmem: None) -> None:
        send_serialised_email(serialise_message(make_message()))

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
        send_serialised_email(serialise_message(make_message()))

        parts = body_parts(mail.outbox[0].message(policy=email.policy.SMTP))
        assert parts
        for part in parts:
            assert part["Content-Transfer-Encoding"] == "8bit"
            assert "=\n" not in part.get_payload()
            assert LONG_URL in part.get_payload()


@pytest.mark.django_db
@pytest.mark.usefixtures("upstream_locmem")
class TestSendOutboundEmail:
    def test_a_pending_row_is_sent_and_its_body_removed(self) -> None:
        email = OutboundEmailFactory()

        send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert len(mail.outbox) == 1
        assert email.status == OutboundEmail.Status.SENT
        assert email.sent_at is not None
        assert email.scrubbed_at is not None
        assert email.payload == {}
        assert email.attempt_count == 1

    def test_a_second_call_for_the_same_id_sends_nothing_more(self) -> None:
        email = OutboundEmailFactory()

        send_outbound_email(str(email.pk))
        send_outbound_email(str(email.pk))

        assert len(mail.outbox) == 1

    def test_a_sent_row_is_never_sent_again(self) -> None:
        email = OutboundEmailFactory(sent=True)

        send_outbound_email(str(email.pk))

        assert mail.outbox == []

    def test_a_failed_row_not_yet_due_is_left_alone(self) -> None:
        email = OutboundEmailFactory(
            failed=True, next_attempt_at=timezone.now() + timedelta(hours=1)
        )

        send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert mail.outbox == []
        assert email.status == OutboundEmail.Status.FAILED

    def test_an_unknown_id_returns_without_raising(self) -> None:
        send_outbound_email(str(uuid4()))

        assert mail.outbox == []

    def test_an_upstream_error_propagates_and_leaves_the_row_sending(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING
        email = OutboundEmailFactory()

        with pytest.raises(ConnectionRefusedError):
            send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.SENDING

    def test_an_upstream_error_fails_the_task_under_the_task_backend(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING
        email = OutboundEmailFactory()

        result = enqueue_send(email.pk)

        assert result.status == TaskResultStatus.FAILED
