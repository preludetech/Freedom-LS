"""Factory for OutboundEmail. Plain, because the model is not site-aware."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from django.core.mail import EmailMessage
from django.utils import timezone

from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.serialisation import SerialisedMessage, serialise_message

Status = OutboundEmail.Status


def _default_payload() -> SerialisedMessage:
    message = EmailMessage(
        subject="Reset your password",
        body="Follow this link to reset your password.",
        from_email="noreply@example.test",
        to=["learner@example.test"],
    )
    return serialise_message(message)


class OutboundEmailFactory(DjangoModelFactory):
    class Meta:
        model = OutboundEmail

    message_id = factory.Sequence(lambda n: f"<message-{n}@example.test>")
    recipients = factory.LazyFunction(lambda: ["learner@example.test"])
    subject = "Reset your password"
    payload = factory.LazyFunction(_default_payload)
    status = Status.PENDING
    next_attempt_at = factory.LazyFunction(timezone.now)

    class Params:
        sending = factory.Trait(
            status=Status.SENDING,
            attempt_count=1,
            last_attempt_at=factory.LazyFunction(timezone.now),
        )
        failed = factory.Trait(
            status=Status.FAILED,
            attempt_count=1,
            last_attempt_at=factory.LazyFunction(timezone.now),
            last_error="builtins.ConnectionRefusedError: mail host is not listening",
        )
        sent = factory.Trait(
            status=Status.SENT,
            attempt_count=1,
            last_attempt_at=factory.LazyFunction(timezone.now),
            sent_at=factory.LazyFunction(timezone.now),
            scrubbed_at=factory.LazyFunction(timezone.now),
            payload=factory.LazyFunction(dict),
        )
        permanent_failure = factory.Trait(
            status=Status.PERMANENT_FAILURE,
            attempt_count=1,
            last_attempt_at=factory.LazyFunction(timezone.now),
            last_error="smtplib.SMTPDataError: (550, b'mailbox unavailable')",
        )
        dead_letter = factory.Trait(
            status=Status.DEAD_LETTER,
            attempt_count=6,
            last_attempt_at=factory.LazyFunction(timezone.now),
            last_error="builtins.ConnectionRefusedError: mail host is not listening",
        )
        scrubbed = factory.Trait(
            scrubbed_at=factory.LazyFunction(timezone.now),
            payload=factory.LazyFunction(dict),
        )
