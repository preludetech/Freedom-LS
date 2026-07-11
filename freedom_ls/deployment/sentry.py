from __future__ import annotations

import sentry_sdk

from freedom_ls.deployment.config import config


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
    )
