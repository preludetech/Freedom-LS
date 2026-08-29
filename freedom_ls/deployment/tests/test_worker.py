"""Tests for the worker's heartbeat file, its watchdog, and fls_run_worker.

Every test in this file overrides WORKER_HEARTBEAT_PATH to a path under tmp_path.
The setting's real default is the literal /tmp/heartbeat, and a test that left it
alone would write a file on the developer's machine that nothing cleans up.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import django_tasks_db
import pytest
import pytest_django.fixtures

from django.core.management import call_command

from freedom_ls.deployment.worker import check_worker_heartbeat, touch_heartbeat


@pytest.fixture(autouse=True)
def _heartbeat_path_under_tmp(
    settings: pytest_django.fixtures.SettingsWrapper, tmp_path: Path
) -> None:
    settings.WORKER_HEARTBEAT_PATH = str(tmp_path / "heartbeat")


class TestTouchHeartbeat:
    def test_creates_file_when_absent(self, tmp_path: Path) -> None:
        heartbeat = tmp_path / "nested" / "heartbeat"

        touch_heartbeat(heartbeat)

        assert heartbeat.exists()

    def test_advances_mtime_of_existing_file(self, tmp_path: Path) -> None:
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()
        old_time = time.time() - 1000
        os.utime(heartbeat, (old_time, old_time))

        touch_heartbeat(heartbeat)

        assert heartbeat.stat().st_mtime > old_time


class TestCheckWorkerHeartbeat:
    def test_stale_heartbeat_reports_to_sentry_then_exits(
        self, mocker, tmp_path: Path
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()
        old_time = time.time() - 1000
        os.utime(heartbeat, (old_time, old_time))
        call_order: list[str] = []
        mock_sentry = mocker.patch("freedom_ls.deployment.worker.sentry_sdk")
        mock_sentry.capture_message.side_effect = lambda *a, **k: call_order.append(
            "capture_message"
        )
        mock_sentry.flush.side_effect = lambda *a, **k: call_order.append("flush")
        mock_exit = mocker.patch("freedom_ls.deployment.worker.os._exit")
        mock_exit.side_effect = lambda *a, **k: call_order.append("exit")

        check_worker_heartbeat(str(heartbeat), max_age_seconds=300)

        assert call_order == ["capture_message", "flush", "exit"]

    def test_fresh_heartbeat_reports_nothing(self, mocker, tmp_path: Path) -> None:
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()
        mock_sentry = mocker.patch("freedom_ls.deployment.worker.sentry_sdk")
        mock_exit = mocker.patch("freedom_ls.deployment.worker.os._exit")

        check_worker_heartbeat(str(heartbeat), max_age_seconds=300)

        mock_sentry.capture_message.assert_not_called()
        mock_exit.assert_not_called()

    def test_absent_heartbeat_counts_as_stale(self, mocker, tmp_path: Path) -> None:
        heartbeat = tmp_path / "never-touched"
        mock_sentry = mocker.patch("freedom_ls.deployment.worker.sentry_sdk")
        mocker.patch("freedom_ls.deployment.worker.os._exit")

        check_worker_heartbeat(str(heartbeat), max_age_seconds=300)

        mock_sentry.capture_message.assert_called_once()


def test_django_tasks_db_is_pinned_to_the_version_the_worker_loop_was_copied_from() -> (
    None
):
    assert django_tasks_db.__version__ == "0.12.0", (
        "django_tasks_db was upgraded past the version freedom_ls/deployment/"
        "worker.py's HeartbeatWorker.run() was copied from. Re-check the copied "
        "loop against the new upstream Worker.run() before moving this pin."
    )


def test_fls_run_worker_processes_every_queue(mocker) -> None:
    mocker.patch(
        "freedom_ls.deployment.management.commands.fls_run_worker.start_watchdog"
    )
    mock_worker_cls = mocker.patch(
        "freedom_ls.deployment.management.commands.fls_run_worker.HeartbeatWorker"
    )
    mock_worker_cls.return_value.run.return_value = None

    call_command("fls_run_worker")

    _args, kwargs = mock_worker_cls.call_args
    assert kwargs["queue_names"] == ["*"]
