from __future__ import annotations

import sentry_sdk
from sentry_sdk.types import Event, Hint

from freedom_ls.deployment.config import config

# The SDK's own marker for a value it has removed.
FILTERED = "[Filtered]"


def scrub_authorization(event: Event, hint: Hint) -> Event:
    """Drop the Authorization header, which carries an API key, from every event.

    The SDK filters it only while send_default_pii is off; a deployment that
    opts into personal data must still never send a live key.
    """
    request = event.get("request")
    if request is None:
        return event
    headers = request.get("headers")
    if isinstance(headers, dict) and "Authorization" in headers:
        headers["Authorization"] = FILTERED
    return event


def init_sentry() -> None:
    dsn = config.SENTRY_DSN
    if not dsn:
        return  # no DSN ⇒ Sentry disabled (dev / unconfigured deploys)
    sentry_sdk.init(
        dsn=dsn,
        environment=config.SENTRY_ENVIRONMENT,  # sourced from config for discoverability
        release=config.SENTRY_RELEASE,  # None ⇒ no release tag
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=config.SENTRY_SEND_DEFAULT_PII,
        before_send=scrub_authorization,
    )
