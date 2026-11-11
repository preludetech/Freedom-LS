"""Tests for OutboundEmail."""

from __future__ import annotations

import pytest

from freedom_ls.mail.factories import OutboundEmailFactory


@pytest.mark.django_db
class TestOutboundEmail:
    def test_save_truncates_last_error_to_1000_characters(self) -> None:
        email = OutboundEmailFactory(last_error="x" * 2000)

        email.refresh_from_db()
        assert len(email.last_error) == 1000

    def test_save_truncates_subject_to_255_characters(self) -> None:
        email = OutboundEmailFactory(subject="s" * 400)

        email.refresh_from_db()
        assert len(email.subject) == 255
