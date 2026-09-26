"""Tests for freedom_ls.base system checks."""

from __future__ import annotations

from django.conf import settings
from django.core.checks import registry
from django.test import override_settings

from freedom_ls.base.checks import (
    check_analytics_events_context_processor,
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


def _templates_with(context_processors: list[str]) -> list[dict[str, object]]:
    return [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "OPTIONS": {"context_processors": context_processors},
        }
    ]


def test_analytics_events_processor_check_is_registered_via_app_ready() -> None:
    assert (
        check_analytics_events_context_processor in registry.registry.registered_checks
    )


def test_platform_app_without_analytics_events_processor_returns_one_e004() -> None:
    with override_settings(
        TEMPLATES=_templates_with(
            ["freedom_ls.google_tag.context_processors.google_tag_config"]
        )
    ):
        errors = check_analytics_events_context_processor(None)

    assert [error.id for error in errors] == ["freedom_ls_base.E004"]


def test_platform_app_with_analytics_events_processor_returns_no_errors() -> None:
    with override_settings(
        TEMPLATES=_templates_with(
            ["freedom_ls.base.context_processors.analytics_events"]
        )
    ):
        errors = check_analytics_events_context_processor(None)

    assert errors == []


def test_no_platform_app_installed_returns_no_errors() -> None:
    installed = [
        app
        for app in settings.INSTALLED_APPS
        if app
        not in (
            "freedom_ls.google_tag",
            "freedom_ls.meta_pixel",
            "freedom_ls.tiktok_pixel",
        )
    ]
    with override_settings(INSTALLED_APPS=installed, TEMPLATES=_templates_with([])):
        errors = check_analytics_events_context_processor(None)

    assert errors == []
