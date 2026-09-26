"""Tests for freedom_ls.base system checks."""

from __future__ import annotations

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.base.checks import (
    check_htmx_messages_middleware,
    check_visitor_country_header_is_not_a_meta_key,
)


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


def test_visitor_country_header_check_is_registered_via_app_ready() -> None:
    assert (
        check_visitor_country_header_is_not_a_meta_key
        in registry.registry.registered_checks
    )


def test_meta_key_form_of_visitor_country_header_returns_one_e003() -> None:
    with override_settings(VISITOR_COUNTRY_HEADER="HTTP_X_VISITOR_COUNTRY"):
        errors = check_visitor_country_header_is_not_a_meta_key(None)

    assert [error.id for error in errors] == ["freedom_ls_base.E003"]


def test_visitor_country_meta_key_error_hints_at_the_plain_header_name() -> None:
    with override_settings(VISITOR_COUNTRY_HEADER="HTTP_X_VISITOR_COUNTRY"):
        errors = check_visitor_country_header_is_not_a_meta_key(None)

    assert "X-Visitor-Country" in str(errors[0].hint)


def test_plain_visitor_country_header_name_returns_no_errors() -> None:
    with override_settings(VISITOR_COUNTRY_HEADER="X-Visitor-Country"):
        errors = check_visitor_country_header_is_not_a_meta_key(None)

    assert errors == []


def test_unset_visitor_country_header_returns_no_errors() -> None:
    with override_settings(VISITOR_COUNTRY_HEADER=None):
        errors = check_visitor_country_header_is_not_a_meta_key(None)

    assert errors == []
