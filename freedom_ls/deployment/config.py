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
    WORKER_MAX_TASK_SECONDS: int
    HOUSEKEEPING_HEARTBEAT_PATH: str
    HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS: int
    HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS: int
    HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS: int

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
        # Under /tmp because the image runs as a non-root user. The max age bounds
        # how long the work loop may go quiet between tasks; how long a single task
        # may run is WORKER_MAX_TASK_SECONDS, separately.
        "WORKER_HEARTBEAT_PATH": Setting(default="/tmp/heartbeat"),  # noqa: S108  # nosec B108
        "WORKER_HEARTBEAT_MAX_AGE_SECONDS": Setting(default=300),
        # The longest a single task may run before the worker stops holding its
        # heartbeat up for it. Past this the heartbeat is deliberately left to go
        # stale so the watchdog kills the process mid-task, which is the whole
        # reason the watchdog exists. The true ceiling on a task's life is this plus
        # WORKER_HEARTBEAT_MAX_AGE_SECONDS plus one WATCHDOG_POLL_SECONDS, because
        # the watchdog still has to notice.
        "WORKER_MAX_TASK_SECONDS": Setting(default=1800),
        # The housekeeping command's heartbeat. A separate path setting from the worker's,
        # and a distinct default, so a deployment that co-locates the two processes is
        # safe without configuring anything: sharing one file, a daily sweep would keep
        # a dead worker's heartbeat fresh and the liveness probe green over it.
        "HOUSEKEEPING_HEARTBEAT_PATH": Setting(default="/tmp/housekeeping-heartbeat"),  # noqa: S108  # nosec B108
        "HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS": Setting(default=3600),
        # How long a worker may hold a claimed task before housekeeping closes the row
        # as failed. Separate from the unpicked window because this one writes: set
        # below the longest legitimate task runtime it marks live work failed. Keep it
        # at or above the true task ceiling -- WORKER_MAX_TASK_SECONDS plus
        # WORKER_HEARTBEAT_MAX_AGE_SECONDS plus one watchdog poll -- which is how long
        # a task can still be running before the watchdog kills the worker holding it.
        "HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS": Setting(default=3600),
        # How long a cohort report may sit in RUNNING before housekeeping closes it as
        # failed. Its own window rather than the task one: a report render is the long
        # task in this system, and while the row sits in RUNNING the partial unique
        # index makes it the one in-flight report that cohort is allowed, so nobody can
        # ask for another. Same ceiling rule as the task window above.
        "HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS": Setting(default=3600),
    }


config = DeploymentSettings()
