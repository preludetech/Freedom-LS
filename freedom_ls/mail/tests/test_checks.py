"""Tests for freedom_ls_mail.E001, freedom_ls_mail.E002 and freedom_ls_mail.W001."""

from __future__ import annotations

import pytest

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.mail.backends import QueuedEmailBackend
from freedom_ls.mail.checks import (
    check_email_retry_settings_are_usable,
    check_email_upstream_backend_is_not_the_queue,
    check_task_backend_can_defer_email_retries,
)

QUEUED_BACKEND = "freedom_ls.mail.backends.QueuedEmailBackend"
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
LOCMEM_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


class QueuedEmailBackendSubclass(QueuedEmailBackend):
    """Stand-in for a downstream that subclasses the queueing backend."""


def test_email_upstream_backend_check_is_registered() -> None:
    # Not deploy=True: dev is the configuration that queues by default, so this
    # must fail runserver rather than waiting for check --deploy. That puts it in
    # registered_checks.
    assert (
        check_email_upstream_backend_is_not_the_queue
        in registry.registry.registered_checks
    )


@override_settings(EMAIL_BACKEND=QUEUED_BACKEND, EMAIL_UPSTREAM_BACKEND=QUEUED_BACKEND)
def test_upstream_pointing_back_at_the_queue_returns_an_error() -> None:
    errors = check_email_upstream_backend_is_not_the_queue()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_mail.E001"


@override_settings(
    EMAIL_BACKEND=QUEUED_BACKEND,
    EMAIL_UPSTREAM_BACKEND=(
        "freedom_ls.mail.tests.test_checks.QueuedEmailBackendSubclass"
    ),
)
def test_a_subclass_of_the_queue_backend_is_caught_too() -> None:
    errors = check_email_upstream_backend_is_not_the_queue()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_mail.E001"


@override_settings(EMAIL_BACKEND=QUEUED_BACKEND, EMAIL_UPSTREAM_BACKEND=SMTP_BACKEND)
def test_an_smtp_upstream_returns_no_errors() -> None:
    assert check_email_upstream_backend_is_not_the_queue() == []


@override_settings(EMAIL_BACKEND=LOCMEM_BACKEND, EMAIL_UPSTREAM_BACKEND=QUEUED_BACKEND)
def test_no_error_when_the_queue_is_not_in_use() -> None:
    # Nothing can loop when EMAIL_BACKEND is not the queue -- which is every test
    # in this suite, since Django forces locmem.
    assert check_email_upstream_backend_is_not_the_queue() == []


@override_settings(
    EMAIL_BACKEND=QUEUED_BACKEND, EMAIL_UPSTREAM_BACKEND="nope.NotABackend"
)
def test_an_unimportable_upstream_returns_no_errors() -> None:
    # Django raises on the first send for this; one id, one meaning.
    assert check_email_upstream_backend_is_not_the_queue() == []


IMMEDIATE_TASKS = {
    "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}
}
DATABASE_TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}


def test_deferral_check_is_registered_as_a_deploy_check() -> None:
    assert (
        check_task_backend_can_defer_email_retries
        in registry.registry.deployment_checks
    )


@override_settings(EMAIL_BACKEND=QUEUED_BACKEND, TASKS=IMMEDIATE_TASKS)
def test_queue_on_a_task_backend_that_cannot_defer_warns() -> None:
    messages = check_task_backend_can_defer_email_retries()

    assert [message.id for message in messages] == ["freedom_ls_mail.W001"]


@override_settings(EMAIL_BACKEND=QUEUED_BACKEND, TASKS=DATABASE_TASKS)
def test_queue_on_a_task_backend_that_can_defer_is_quiet() -> None:
    assert check_task_backend_can_defer_email_retries() == []


@override_settings(EMAIL_BACKEND=LOCMEM_BACKEND, TASKS=IMMEDIATE_TASKS)
def test_deferral_check_is_quiet_when_the_queue_is_not_in_use() -> None:
    assert check_task_backend_can_defer_email_retries() == []


def test_email_retry_settings_check_is_registered() -> None:
    assert check_email_retry_settings_are_usable in registry.registry.registered_checks


@override_settings(
    EMAIL_RETRY_DELAYS=[60, 300], EMAIL_MAX_ATTEMPTS=1, EMAIL_RETRY_JITTER_RATIO=0
)
def test_usable_retry_settings_pass() -> None:
    assert check_email_retry_settings_are_usable() == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"EMAIL_RETRY_DELAYS": []},
        {"EMAIL_RETRY_DELAYS": [60, -1]},
        {"EMAIL_RETRY_DELAYS": [60, "300"]},
        {"EMAIL_RETRY_DELAYS": 60},
        {"EMAIL_MAX_ATTEMPTS": 0},
        {"EMAIL_RETRY_JITTER_RATIO": -0.1},
    ],
    ids=[
        "empty_delays",
        "negative_delay",
        "string_delay",
        "delays_not_a_list",
        "zero_attempts",
        "negative_jitter",
    ],
)
def test_unusable_retry_setting_returns_one_error(overrides: dict[str, object]) -> None:
    with override_settings(**overrides):
        errors = check_email_retry_settings_are_usable()

    assert [error.id for error in errors] == ["freedom_ls_mail.E002"]
