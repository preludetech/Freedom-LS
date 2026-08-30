"""Tests for the deployment app's declared settings and their defaults."""

from __future__ import annotations

from freedom_ls.deployment.config import config


class TestWorkerHeartbeatDefaults:
    def test_worker_heartbeat_path_defaults_to_tmp_heartbeat(self) -> None:
        assert config.WORKER_HEARTBEAT_PATH == "/tmp/heartbeat"  # noqa: S108

    def test_worker_heartbeat_max_age_seconds_defaults_to_300(self) -> None:
        assert config.WORKER_HEARTBEAT_MAX_AGE_SECONDS == 300


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
