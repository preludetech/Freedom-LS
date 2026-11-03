from __future__ import annotations

import json
from collections.abc import Iterator
from unittest import mock

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.transport import Transport

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core.signals import request_finished, request_started
from django.db import close_old_connections
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse

from freedom_ls.deployment.sentry import FILTERED, init_sentry, scrub_authorization


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
    assert kwargs["before_send"] is scrub_authorization


def test_the_scrub_replaces_the_authorization_header():
    event = {"request": {"headers": {"Authorization": "Bearer flsk_x.y", "Host": "a"}}}

    assert scrub_authorization(event, {}) == {
        "request": {"headers": {"Authorization": FILTERED, "Host": "a"}}
    }


@pytest.mark.parametrize(
    "event", [{}, {"request": {}}, {"request": {"headers": {"Host": "a"}}}]
)
def test_the_scrub_leaves_an_event_without_the_header_alone(event):
    assert scrub_authorization(dict(event), {}) == event


class CapturingTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Envelope] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)


@pytest.fixture(params=[False, True], ids=["pii_off", "pii_on"])
def captured_sentry(request: pytest.FixtureRequest) -> Iterator[CapturingTransport]:
    transport = CapturingTransport()
    sentry_sdk.init(
        dsn="https://key@o0.ingest.sentry.io/0",
        transport=transport,
        integrations=[DjangoIntegration()],
        send_default_pii=request.param,
        before_send=scrub_authorization,
    )
    yield transport
    sentry_sdk.init()  # no DSN: the global client is disabled again for later tests


@pytest.mark.django_db
def test_an_event_from_a_request_carries_no_authorization_header(
    staff_client: Client, captured_sentry: CapturingTransport
) -> None:
    # The Django test client skips the WSGI entry point, which is where the
    # SDK attaches request data to events, so the request goes through
    # WSGIHandler directly.
    session_cookie = staff_client.cookies[settings.SESSION_COOKIE_NAME].value
    request = RequestFactory().get(
        reverse("deployment:trigger_error"),
        HTTP_AUTHORIZATION="Bearer flsk_testprefix.testsecretvalue",
        HTTP_COOKIE=f"{settings.SESSION_COOKIE_NAME}={session_cookie}",
    )

    # Closing connections after the request would end the test's transaction.
    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    try:
        WSGIHandler()(request.META, lambda status, headers: None)
    finally:
        request_started.connect(close_old_connections)
        request_finished.connect(close_old_connections)

    events = [
        event
        for envelope in captured_sentry.envelopes
        if (event := envelope.get_event()) is not None
    ]
    assert events
    headers = events[-1]["request"]["headers"]
    # The header name stays; the scrub (and, with PII off, the SDK) replaces its value.
    assert headers.get("Authorization", FILTERED) == FILTERED
    assert "testsecretvalue" not in json.dumps(events[-1])
