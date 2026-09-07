"""Tests for the queued send -- what fls_run_worker does with a payload."""

from __future__ import annotations

import email.policy

from django.core import mail

from freedom_ls.mail.serialisation import serialise_message
from freedom_ls.mail.tasks import send_serialised_email
from freedom_ls.mail.tests.conftest import LONG_URL, body_parts, make_message


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
