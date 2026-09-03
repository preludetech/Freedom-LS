"""Tests for set_8bit_encoding.

The allauth adapter's own suite covers this through a real password-reset mail.
These pin the primitive directly, because the queueing email backend now applies
it to a message it rebuilt itself, with no adapter involved.
"""

from __future__ import annotations

import email.policy

import pytest

from django.core.mail import EmailMultiAlternatives

from freedom_ls.base.email_encoding import set_8bit_encoding

LONG_URL = "https://example.test/account/password/reset/key/" + "a" * 80 + "/"


def _message_with_long_url() -> EmailMultiAlternatives:
    message = EmailMultiAlternatives(
        subject="Reset your password",
        body=f"Follow this link: {LONG_URL}",
        from_email="noreply@example.test",
        to=["learner@example.test"],
    )
    message.attach_alternative(f'<a href="{LONG_URL}">Reset</a>', "text/html")
    return message


def _body_parts(mime_msg: object) -> list:
    return [
        part
        for part in mime_msg.walk()
        if part.get_content_type() in ("text/plain", "text/html")
    ]


def test_forces_8bit_on_every_text_part() -> None:
    message = _message_with_long_url()
    set_8bit_encoding(message)

    parts = _body_parts(message.message())
    assert parts
    assert all(part["Content-Transfer-Encoding"] == "8bit" for part in parts)


def test_leaves_the_long_url_intact() -> None:
    message = _message_with_long_url()
    set_8bit_encoding(message)

    for part in _body_parts(message.message()):
        assert LONG_URL in part.get_payload()


@pytest.mark.parametrize("soft_break", ["=\n", "=\r\n"])
def test_emits_no_quoted_printable_soft_breaks(soft_break: str) -> None:
    """Quoted-printable wraps past 76 chars with =\\n, which corrupts URLs."""
    message = _message_with_long_url()
    set_8bit_encoding(message)

    for part in _body_parts(message.message()):
        assert soft_break not in part.get_payload()


def test_forwards_the_policy_keyword() -> None:
    """Django's SMTP backend calls message(policy=...), so the patch must accept it."""
    message = _message_with_long_url()
    set_8bit_encoding(message)

    parts = _body_parts(message.message(policy=email.policy.SMTP))
    assert all(part["Content-Transfer-Encoding"] == "8bit" for part in parts)


def test_quoted_printable_is_what_happens_without_it() -> None:
    """The control: the patch is doing something, not passing a test that passes anyway."""
    parts = _body_parts(_message_with_long_url().message())

    assert parts
    assert any(
        part["Content-Transfer-Encoding"] == "quoted-printable" for part in parts
    )
