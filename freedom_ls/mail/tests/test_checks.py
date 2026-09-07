"""Tests for freedom_ls_mail.E001."""

from __future__ import annotations

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.mail.backends import QueuedEmailBackend
from freedom_ls.mail.checks import check_email_upstream_backend_is_not_the_queue

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
