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
    WORKER_HEARTBEAT_PATH: str
    WORKER_HEARTBEAT_MAX_AGE_SECONDS: int
    HOUSEKEEPING_HEARTBEAT_PATH: str
    HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS: int

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
        # The worker's heartbeat: fls_run_worker touches the path once per poll and its
        # watchdog exits the process when the mtime falls behind the max age.
        # Under /tmp because the image runs as a non-root user. The max age is
        # also the longest a task may run before being killed mid-flight.
        "WORKER_HEARTBEAT_PATH": Setting(default="/tmp/heartbeat"),  # noqa: S108  # nosec B108
        "WORKER_HEARTBEAT_MAX_AGE_SECONDS": Setting(default=300),
        # The housekeeping command's heartbeat. A separate path setting from the worker's,
        # and a distinct default, so a deployment that co-locates the two processes is
        # safe without configuring anything: sharing one file, a daily sweep would keep
        # a dead worker's heartbeat fresh and the liveness probe green over it.
        "HOUSEKEEPING_HEARTBEAT_PATH": Setting(default="/tmp/housekeeping-heartbeat"),  # noqa: S108  # nosec B108
        "HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS": Setting(default=3600),
    }


config = DeploymentSettings()
