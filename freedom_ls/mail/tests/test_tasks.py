"""Tests for the queued send -- what fls_run_worker does with a row."""

from __future__ import annotations

import email.policy
import json
from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_django.fixtures

from django.core import mail
from django.tasks import TaskResultStatus
from django.utils import timezone

from freedom_ls.mail.errors import UpstreamSendCountZeroError
from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.retry import DEAD_LETTER_MESSAGE
from freedom_ls.mail.serialisation import serialise_message
from freedom_ls.mail.tasks import (
    PERMANENT_FAILURE_MESSAGE,
    enqueue_send,
    send_outbound_email,
    send_serialised_email,
)
from freedom_ls.mail.tests.conftest import (
    BUGGY,
    LONG_URL,
    REFUSING,
    REJECTING,
    ZERO_SENT,
    body_parts,
    make_message,
    run_attempts,
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


@pytest.mark.django_db
class TestPermanentFailure:
    def test_a_permanent_error_ends_the_row_at_one_attempt(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REJECTING
        email = OutboundEmailFactory()

        send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.PERMANENT_FAILURE
        assert email.attempt_count == 1
        assert email.last_error.startswith("smtplib.SMTPDataError")

    def test_a_permanent_error_does_not_fail_the_task(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REJECTING
        email = OutboundEmailFactory()

        result = enqueue_send(email.pk)

        assert result.status == TaskResultStatus.SUCCESSFUL

    def test_a_permanent_error_is_reported_without_recipient_or_error_text(
        self,
        settings: pytest_django.fixtures.SettingsWrapper,
        sentry_events: list[dict],
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REJECTING
        email = OutboundEmailFactory()

        send_outbound_email(str(email.pk))

        assert len(sentry_events) == 1
        assert sentry_events[0]["message"] == PERMANENT_FAILURE_MESSAGE
        serialised = json.dumps(sentry_events[0])
        assert "learner@example.test" not in serialised
        assert "mailbox unavailable" not in serialised

    def test_an_unclassified_error_names_its_cause_on_the_row(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = BUGGY
        email = OutboundEmailFactory()

        with pytest.raises(ValueError, match="bug in our own code"):
            send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.SENDING
        assert email.last_error.startswith("builtins.ValueError")

    def test_an_unclassified_error_fails_the_task(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = BUGGY
        email = OutboundEmailFactory()

        result = enqueue_send(email.pk)

        assert result.status == TaskResultStatus.FAILED


@pytest.mark.django_db
class TestTransientFailure:
    def test_a_refusing_upstream_leaves_the_row_failed_and_due_later(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING
        email = OutboundEmailFactory()

        send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.FAILED
        assert email.attempt_count == 1
        assert OutboundEmail.objects.filter(
            pk=email.pk, next_attempt_at__gt=timezone.now()
        ).exists()
        assert email.last_error.startswith("builtins.ConnectionRefusedError")

    def test_a_refusing_upstream_does_not_fail_the_task(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING
        email = OutboundEmailFactory()

        result = enqueue_send(email.pk)

        assert result.status == TaskResultStatus.SUCCESSFUL

    def test_walking_the_ladder_dead_letters_the_row_at_the_attempt_cap(
        self,
        settings: pytest_django.fixtures.SettingsWrapper,
        sentry_events: list[dict],
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING
        settings.EMAIL_MAX_ATTEMPTS = 3
        email = OutboundEmailFactory()

        run_attempts(email, 4)

        assert email.status == OutboundEmail.Status.DEAD_LETTER
        assert email.attempt_count == 3
        assert [event["message"] for event in sentry_events] == [DEAD_LETTER_MESSAGE]

    @pytest.mark.usefixtures("upstream_locmem")
    def test_a_host_that_comes_back_partway_up_the_ladder_gets_the_message(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = REFUSING
        email = OutboundEmailFactory()
        run_attempts(email, 2)
        settings.EMAIL_UPSTREAM_BACKEND = (
            "django.core.mail.backends.locmem.EmailBackend"
        )

        run_attempts(email, 1)

        assert email.status == OutboundEmail.Status.SENT
        assert email.attempt_count == 3
        assert len(mail.outbox) == 1

    def test_an_upstream_reporting_zero_sent_leaves_the_row_failed(
        self, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.EMAIL_UPSTREAM_BACKEND = ZERO_SENT
        email = OutboundEmailFactory()

        send_outbound_email(str(email.pk))

        email.refresh_from_db()
        assert email.status == OutboundEmail.Status.FAILED
        assert UpstreamSendCountZeroError.__name__ in email.last_error
