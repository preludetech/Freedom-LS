from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, override_settings

from freedom_ls.deployment import settings_defaults


def test_require_secret_key_missing_env_raises_improperly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ImproperlyConfigured):
        settings_defaults.require_secret_key()


def test_require_secret_key_empty_string_raises_improperly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", "")

    with pytest.raises(ImproperlyConfigured):
        settings_defaults.require_secret_key()


def test_require_secret_key_whitespace_only_raises_improperly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", " ")

    with pytest.raises(ImproperlyConfigured):
        settings_defaults.require_secret_key()


def test_require_secret_key_returns_value_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", "a-real-secret")

    assert settings_defaults.require_secret_key() == "a-real-secret"


def test_require_webhook_encryption_salt_missing_env_raises_improperly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WEBHOOK_ENCRYPTION_SALT", raising=False)

    with pytest.raises(ImproperlyConfigured):
        settings_defaults.require_webhook_encryption_salt()


def test_require_webhook_encryption_salt_empty_string_raises_improperly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", "")

    with pytest.raises(ImproperlyConfigured):
        settings_defaults.require_webhook_encryption_salt()


def test_require_webhook_encryption_salt_whitespace_only_raises_improperly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", " ")

    with pytest.raises(ImproperlyConfigured):
        settings_defaults.require_webhook_encryption_salt()


def test_require_webhook_encryption_salt_returns_value_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", "a-real-salt")

    assert settings_defaults.require_webhook_encryption_salt() == "a-real-salt"


def test_database_ssl_options_prefer() -> None:
    assert settings_defaults.database_ssl_options("prefer") == {"sslmode": "prefer"}


def test_database_ssl_options_disable() -> None:
    assert settings_defaults.database_ssl_options("disable") == {"sslmode": "disable"}


def test_database_ssl_options_require() -> None:
    assert settings_defaults.database_ssl_options("require") == {"sslmode": "require"}


def test_build_logging_config_no_log_dir_has_console_handler() -> None:
    config = settings_defaults.build_logging_config()

    assert config["handlers"]["console"]["class"] == "logging.StreamHandler"


def test_build_logging_config_no_log_dir_has_no_file_handlers() -> None:
    config = settings_defaults.build_logging_config()

    file_handlers = [
        name
        for name, handler in config["handlers"].items()
        if handler["class"] == "logging.handlers.RotatingFileHandler"
    ]
    assert file_handlers == []


@pytest.mark.parametrize(
    "logger_name",
    ["django", "django.request", "django.security", "django.db.backends", "freedom_ls"],
)
def test_build_logging_config_no_log_dir_includes_expected_logger(
    logger_name: str,
) -> None:
    config = settings_defaults.build_logging_config()

    assert logger_name in config["loggers"]


def test_build_logging_config_with_log_dir_file_handler_under_log_dir(
    tmp_path: Path,
) -> None:
    config = settings_defaults.build_logging_config(log_dir=tmp_path)

    filename = Path(config["handlers"]["file"]["filename"])
    assert filename.is_relative_to(tmp_path)


def test_build_logging_config_with_log_dir_still_has_console_handler(
    tmp_path: Path,
) -> None:
    config = settings_defaults.build_logging_config(log_dir=tmp_path)

    assert config["handlers"]["console"]["class"] == "logging.StreamHandler"


def test_build_logging_config_with_log_dir_has_dedicated_security_file_handler(
    tmp_path: Path,
) -> None:
    config = settings_defaults.build_logging_config(log_dir=tmp_path)

    security_file = Path(config["handlers"]["security_file"]["filename"])
    assert security_file.name == "security.log"
    assert security_file.is_relative_to(tmp_path)


def test_build_logging_config_with_log_dir_security_logger_uses_security_file(
    tmp_path: Path,
) -> None:
    config = settings_defaults.build_logging_config(log_dir=tmp_path)

    assert "security_file" in config["loggers"]["django.security"]["handlers"]


def test_secure_proxy_ssl_header_constant() -> None:
    assert settings_defaults.SECURE_PROXY_SSL_HEADER == (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )


def test_secure_redirect_exempt_constant() -> None:
    assert settings_defaults.SECURE_REDIRECT_EXEMPT == [r"^health/"]


@override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_REDIRECT_EXEMPT=settings_defaults.SECURE_REDIRECT_EXEMPT,
)
def test_health_path_exempt_from_ssl_redirect() -> None:
    middleware = SecurityMiddleware(lambda request: HttpResponse())

    response = middleware.process_request(RequestFactory().get("/health/"))

    assert response is None


@override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_REDIRECT_EXEMPT=settings_defaults.SECURE_REDIRECT_EXEMPT,
)
def test_non_health_path_still_redirected_to_https() -> None:
    middleware = SecurityMiddleware(lambda request: HttpResponse())

    response = middleware.process_request(RequestFactory().get("/dashboard/"))

    assert response is not None
    assert response.status_code == 301


def test_conn_health_checks_constant_is_true() -> None:
    assert settings_defaults.CONN_HEALTH_CHECKS is True


def test_conn_max_age_constant_is_positive_int_in_recommended_range() -> None:
    assert isinstance(settings_defaults.CONN_MAX_AGE, int)
    assert 60 <= settings_defaults.CONN_MAX_AGE <= 300


def test_database_tasks_default_backend_path_is_importable() -> None:
    from django.utils.module_loading import import_string

    backend_path = settings_defaults.DATABASE_TASKS["default"]["BACKEND"]

    assert import_string(backend_path) is not None


def test_prod_settings_uses_database_task_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOST_DOMAIN", "example.test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_SALT", "test-webhook-salt")

    prod = importlib.reload(importlib.import_module("config.settings_prod"))

    assert prod.TASKS["default"]["BACKEND"] == "django_tasks_db.DatabaseBackend"


@override_settings(SECURE_PROXY_SSL_HEADER=settings_defaults.SECURE_PROXY_SSL_HEADER)
def test_forwarded_https_header_makes_request_secure() -> None:
    request = RequestFactory().get("/", HTTP_X_FORWARDED_PROTO="https")

    assert request.is_secure() is True


@override_settings(SECURE_PROXY_SSL_HEADER=settings_defaults.SECURE_PROXY_SSL_HEADER)
def test_missing_forwarded_header_leaves_request_insecure() -> None:
    request = RequestFactory().get("/")

    assert request.is_secure() is False
