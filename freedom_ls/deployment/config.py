from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class DeploymentSettings(AppSettings):
    POSTHOG_API_KEY: str | None
    POSTHOG_API_HOST: str
    POSTHOG_UI_HOST: str | None
    SENTRY_DSN: str | None
    SENTRY_ENVIRONMENT: str | None
    SENTRY_RELEASE: str | None
    SENTRY_TRACES_SAMPLE_RATE: float
    SENTRY_SEND_DEFAULT_PII: bool

    declared_settings = {
        # PostHog: declared here to own the region-host default; the client-side
        # snippet (context processor + _base.html) reads these.
        "POSTHOG_API_KEY": Setting(default=None),
        "POSTHOG_API_HOST": Setting(default="https://us.i.posthog.com"),
        "POSTHOG_UI_HOST": Setting(default=None),
        # Sentry: read by init_sentry() in AppConfig.ready().
        "SENTRY_DSN": Setting(default=None),
        "SENTRY_ENVIRONMENT": Setting(default=None),
        "SENTRY_RELEASE": Setting(default=None),
        "SENTRY_TRACES_SAMPLE_RATE": Setting(default=0.1),
        "SENTRY_SEND_DEFAULT_PII": Setting(default=False),
    }


config = DeploymentSettings()
