"""Tests for how config/settings_prod.py resolves the email settings."""

from __future__ import annotations

import importlib

import pytest

from freedom_ls.mail import settings_defaults


def test_prod_settings_send_email_in_the_request_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The default has to work for a deployment running nothing but the web process:
    # queued mail with no worker behind it is accepted and never sent.
    monkeypatch.setenv("HOST_DOMAIN", "example.test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", "test-webhook-salt")
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)

    prod = importlib.reload(importlib.import_module("config.settings_prod"))

    assert prod.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
    assert prod.EMAIL_TIMEOUT == settings_defaults.EMAIL_TIMEOUT_SECONDS


def test_prod_settings_let_a_deployment_opt_into_queueing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The other half of the choice: a deployment that runs fls_run_worker turns
    # queueing on here and keeps the SMTP round trip out of the request.
    monkeypatch.setenv("HOST_DOMAIN", "example.test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", "test-webhook-salt")
    monkeypatch.setenv("EMAIL_BACKEND", "freedom_ls.mail.backends.QueuedEmailBackend")

    prod = importlib.reload(importlib.import_module("config.settings_prod"))

    assert prod.EMAIL_BACKEND == "freedom_ls.mail.backends.QueuedEmailBackend"


def test_email_timeout_default_is_a_positive_int() -> None:
    assert isinstance(settings_defaults.EMAIL_TIMEOUT_SECONDS, int)
    assert settings_defaults.EMAIL_TIMEOUT_SECONDS > 0


def test_email_timeout_is_well_inside_the_worker_task_ceiling() -> None:
    # A hung SMTP socket holds the single worker for this long. Anywhere near
    # WORKER_MAX_TASK_SECONDS and one wedged mail host stalls the whole queue.
    from freedom_ls.deployment.config import config

    assert settings_defaults.EMAIL_TIMEOUT_SECONDS < config.WORKER_MAX_TASK_SECONDS / 10
