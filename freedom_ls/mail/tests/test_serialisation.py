"""Tests for the queued-message payload.

The payload is the contract: it has to survive a JSONField round trip, and the
message rebuilt from it has to be byte-for-byte as sendable as the one handed in.
The 8bit regression matters most -- serialising to primitives is exactly what
discards the patch the adapter installs, so the worker has to reapply it.
"""

from __future__ import annotations

import json
from email.message import MIMEPart

import pytest

from django.core.mail import EmailMessage

from freedom_ls.mail.serialisation import (
    UnserialisableMessageError,
    deserialise_message,
    serialise_message,
)
from freedom_ls.mail.tests.conftest import (
    LONG_URL,
    make_message,
    raw_attachment_part,
)


class TestSerialisation:
    def test_payload_is_json_serialisable(self) -> None:
        # The real constraint: DBTaskResult stores task arguments in a JSONField.
        assert json.loads(json.dumps(serialise_message(make_message())))

    def test_round_trip_preserves_subject_body_and_addresses(self) -> None:
        rebuilt = deserialise_message(serialise_message(make_message()))

        assert rebuilt.subject == "Reset your password"
        assert LONG_URL in rebuilt.body
        assert rebuilt.from_email == "noreply@example.test"
        assert rebuilt.to == ["learner@example.test"]
        assert rebuilt.cc == ["educator@example.test"]
        assert rebuilt.bcc == ["audit@example.test"]
        assert rebuilt.reply_to == ["support@example.test"]

    def test_round_trip_preserves_extra_headers(self) -> None:
        rebuilt = deserialise_message(serialise_message(make_message()))

        assert rebuilt.extra_headers == {"X-Tenant": "example"}

    def test_round_trip_preserves_the_html_alternative(self) -> None:
        rebuilt = deserialise_message(serialise_message(make_message()))

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
        message = make_message()
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
        message = make_message()
        message.attach("notes.txt", "plain content", "text/plain")

        rebuilt = deserialise_message(serialise_message(message))

        filename, content, mimetype = rebuilt.attachments[0]
        assert content == "plain content"
        assert isinstance(content, str)
        assert (filename, mimetype) == ("notes.txt", "text/plain")

    def test_a_raw_mime_attachment_is_refused(self) -> None:
        message = make_message()
        part = MIMEPart()
        part.set_content("attached")
        message.attach(part)

        with pytest.raises(UnserialisableMessageError):
            serialise_message(message)

    def test_a_raw_mime_attachment_with_three_headers_is_refused(self) -> None:
        """A MIMEPart iterates over its header names, not over a payload.

        A real attachment part carries three of them, so unpacking one as
        (filename, content, mimetype) succeeds and hands back header names --
        which would queue an attachment called "Content-Type" and drop the file.
        """
        message = make_message()
        message.attach(raw_attachment_part())

        with pytest.raises(UnserialisableMessageError):
            serialise_message(message)
