from __future__ import annotations

from unittest import mock

from django.test import override_settings

from freedom_ls.deployment.sentry import init_sentry


@override_settings(SENTRY_DSN=None)
def test_no_dsn_does_not_initialize_sentry() -> None:
    with mock.patch("freedom_ls.deployment.sentry.sentry_sdk.init") as mock_init:
        init_sentry()

    mock_init.assert_not_called()


@override_settings(
    SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0",
    SENTRY_ENVIRONMENT="staging",
    SENTRY_RELEASE="fls@1.2.3",
    SENTRY_TRACES_SAMPLE_RATE=0.25,
    SENTRY_SEND_DEFAULT_PII=True,
)
def test_dsn_set_initializes_sentry_with_configured_kwargs() -> None:
    with mock.patch("freedom_ls.deployment.sentry.sentry_sdk.init") as mock_init:
        init_sentry()

    mock_init.assert_called_once()
    _, kwargs = mock_init.call_args
    assert kwargs["dsn"] == "https://examplePublicKey@o0.ingest.sentry.io/0"
    assert kwargs["environment"] == "staging"
    assert kwargs["release"] == "fls@1.2.3"
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["send_default_pii"] is True
