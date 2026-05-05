"""Verify the toast HTMX middleware is registered in the right position."""

from __future__ import annotations

from django.conf import settings


def test_htmx_messages_middleware_is_registered() -> None:
    middleware: list[str] = list(settings.MIDDLEWARE)
    assert "freedom_ls.base.middleware.HtmxMessagesMiddleware" in middleware


def test_htmx_messages_middleware_runs_after_django_message_middleware() -> None:
    """HtmxMessagesMiddleware must come after MessageMiddleware so that the
    request-scoped message storage has already been attached when our
    middleware reads from it."""
    middleware: list[str] = list(settings.MIDDLEWARE)
    msg_index = middleware.index("django.contrib.messages.middleware.MessageMiddleware")
    htmx_index = middleware.index("freedom_ls.base.middleware.HtmxMessagesMiddleware")
    assert htmx_index > msg_index
