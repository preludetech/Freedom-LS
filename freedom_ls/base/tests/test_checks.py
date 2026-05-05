"""Tests for freedom_ls.base system checks."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.base.checks import check_htmx_messages_middleware


def test_passes_when_middleware_registered_after_message_middleware() -> None:
    middleware = [
        "django.contrib.messages.middleware.MessageMiddleware",
        "freedom_ls.base.middleware.HtmxMessagesMiddleware",
    ]
    with override_settings(MIDDLEWARE=middleware):
        assert check_htmx_messages_middleware() == []


def test_errors_when_htmx_middleware_missing() -> None:
    middleware = ["django.contrib.messages.middleware.MessageMiddleware"]
    with override_settings(MIDDLEWARE=middleware):
        errors = check_htmx_messages_middleware()
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_base.E001"


def test_errors_when_htmx_middleware_runs_before_message_middleware() -> None:
    middleware = [
        "freedom_ls.base.middleware.HtmxMessagesMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ]
    with override_settings(MIDDLEWARE=middleware):
        errors = check_htmx_messages_middleware()
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_base.E002"
