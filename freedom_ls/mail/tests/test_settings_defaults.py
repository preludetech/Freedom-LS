"""Tests for how config/settings_prod.py resolves the email settings."""

from __future__ import annotations

import importlib

import pytest

from freedom_ls.mail import settings_defaults


def test_prod_settings_queue_email_when_no_backend_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default backend is the contract under test: production queues unless told otherwise."""
    monkeypatch.setenv("HOST_DOMAIN", "example.test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", "test-webhook-salt")
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)

    prod = importlib.reload(importlib.import_module("config.settings_prod"))

    assert prod.EMAIL_BACKEND == "freedom_ls.mail.backends.QueuedEmailBackend"
    assert prod.EMAIL_TIMEOUT == settings_defaults.EMAIL_TIMEOUT_SECONDS


def test_prod_settings_let_a_deployment_send_through_smtp_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A deployment that runs no worker sets the SMTP backend and sends in the request.
    monkeypatch.setenv("HOST_DOMAIN", "example.test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", "test-webhook-salt")
    monkeypatch.setenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

    prod = importlib.reload(importlib.import_module("config.settings_prod"))

    assert prod.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"


def test_email_timeout_default_is_a_positive_int() -> None:
    assert isinstance(settings_defaults.EMAIL_TIMEOUT_SECONDS, int)
    assert settings_defaults.EMAIL_TIMEOUT_SECONDS > 0


def test_email_timeout_is_well_inside_the_worker_task_ceiling() -> None:
    # A hung SMTP socket holds the single worker for this long. Anywhere near
    # WORKER_MAX_TASK_SECONDS and one wedged mail host stalls the whole queue.
    from freedom_ls.deployment.config import config

    assert settings_defaults.EMAIL_TIMEOUT_SECONDS < config.WORKER_MAX_TASK_SECONDS / 10
