"""Tests for the deployment app's declared settings and their defaults."""

from __future__ import annotations

from freedom_ls.deployment.config import config
from freedom_ls.deployment.worker import (
    HEARTBEAT_TICK_SECONDS,
    WATCHDOG_POLL_SECONDS,
)


def _longest_a_task_can_run() -> int:
    """The true ceiling on a task's life, in seconds.

    The worker holds the heartbeat up for WORKER_MAX_TASK_SECONDS, then lets it go
    stale over WORKER_HEARTBEAT_MAX_AGE_SECONDS, and the watchdog still has to come
    round to notice.
    """
    return (
        config.WORKER_MAX_TASK_SECONDS
        + config.WORKER_HEARTBEAT_MAX_AGE_SECONDS
        + WATCHDOG_POLL_SECONDS
    )


class TestWorkerHeartbeatDefaults:
    def test_worker_heartbeat_path_defaults_to_tmp_heartbeat(self) -> None:
        assert config.WORKER_HEARTBEAT_PATH == "/tmp/heartbeat"  # noqa: S108

    def test_worker_heartbeat_max_age_seconds_defaults_to_300(self) -> None:
        assert config.WORKER_HEARTBEAT_MAX_AGE_SECONDS == 300

    def test_worker_max_task_seconds_defaults_to_1800(self) -> None:
        assert config.WORKER_MAX_TASK_SECONDS == 1800

    def test_heartbeat_tick_is_well_inside_the_heartbeat_window(self) -> None:
        # The ticker holds the heartbeat up during a task. Tick slower than the
        # window and it cannot, so the watchdog kills the worker mid-task anyway.
        assert HEARTBEAT_TICK_SECONDS < config.WORKER_HEARTBEAT_MAX_AGE_SECONDS


class TestHousekeepingHeartbeatDefaults:
    def test_housekeeping_heartbeat_path_defaults_to_its_own_file(self) -> None:
        # Distinct from the worker's default: on one shared file a daily sweep would
        # keep a dead worker's heartbeat fresh.
        assert (
            config.HOUSEKEEPING_HEARTBEAT_PATH == "/tmp/housekeeping-heartbeat"  # noqa: S108
        )
        assert config.HOUSEKEEPING_HEARTBEAT_PATH != config.WORKER_HEARTBEAT_PATH

    def test_housekeeping_unpicked_task_max_age_seconds_defaults_to_3600(self) -> None:
        assert config.HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS == 3600

    def test_housekeeping_orphaned_task_max_age_seconds_defaults_to_3600(self) -> None:
        assert config.HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS == 3600

    def test_housekeeping_orphaned_report_max_age_seconds_defaults_to_3600(
        self,
    ) -> None:
        assert config.HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS == 3600

    def test_orphaned_task_window_clears_the_longest_a_task_can_run(self) -> None:
        # Below it, the sweep closes rows a live worker is still inside. The bound
        # is not the heartbeat window alone: the worker holds the heartbeat up for
        # the whole of WORKER_MAX_TASK_SECONDS first.
        assert (
            _longest_a_task_can_run()
            <= config.HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS
        )

    def test_orphaned_report_window_clears_the_longest_a_task_can_run(self) -> None:
        # Same reasoning, for the render rather than the row that scheduled it.
        assert (
            _longest_a_task_can_run()
            <= config.HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS
        )


class TestEmailUpstreamBackendDefault:
    def test_defaults_to_djangos_smtp_backend(self) -> None:
        assert (
            config.EMAIL_UPSTREAM_BACKEND
            == "django.core.mail.backends.smtp.EmailBackend"
        )

    def test_the_default_is_never_the_queueing_backend(self) -> None:
        # A default that pointed at the queue would make every deployment that
        # did not override it enqueue mail forever without sending any.
        from freedom_ls.deployment.settings_defaults import QUEUED_EMAIL_BACKEND

        assert config.EMAIL_UPSTREAM_BACKEND != QUEUED_EMAIL_BACKEND
