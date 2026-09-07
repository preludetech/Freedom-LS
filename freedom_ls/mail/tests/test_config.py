"""Tests for the mail app's declared settings."""

from __future__ import annotations

from freedom_ls.mail.config import config


class TestEmailUpstreamBackendDefault:
    def test_defaults_to_djangos_smtp_backend(self) -> None:
        assert (
            config.EMAIL_UPSTREAM_BACKEND
            == "django.core.mail.backends.smtp.EmailBackend"
        )

    def test_the_default_is_never_the_queueing_backend(self) -> None:
        # A default that pointed at the queue would make every deployment that
        # queues mail and did not override it enqueue forever without sending any.
        assert (
            config.EMAIL_UPSTREAM_BACKEND
            != "freedom_ls.mail.backends.QueuedEmailBackend"
        )
