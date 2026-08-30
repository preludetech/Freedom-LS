"""Tests for the worker's heartbeat file, its watchdog, and fls_run_worker.

Every test in this file overrides WORKER_HEARTBEAT_PATH to a path under tmp_path.
The setting's real default is the literal /tmp/heartbeat, and a test that left it
alone would write a file on the developer's machine that nothing cleans up.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import django_tasks_db
import pytest
import pytest_django.fixtures
from django_tasks import DEFAULT_TASK_BACKEND_ALIAS
from django_tasks_db.management.commands.db_worker import Worker

from django.core.management import call_command

from freedom_ls.deployment.worker import (
    HeartbeatWorker,
    check_worker_heartbeat,
    heartbeat_ticker,
    start_watchdog,
    touch_heartbeat,
    touch_until_capped,
)


@pytest.fixture(autouse=True)
def _heartbeat_path_under_tmp(
    settings: pytest_django.fixtures.SettingsWrapper, tmp_path: Path
) -> None:
    settings.WORKER_HEARTBEAT_PATH = str(tmp_path / "heartbeat")


def _worker_kwargs() -> dict[str, object]:
    """The arguments fls_run_worker builds a HeartbeatWorker with."""
    return {
        "queue_names": ["*"],
        "interval": 1,
        "batch": False,
        "backend_name": DEFAULT_TASK_BACKEND_ALIAS,
        "startup_delay": False,
        "max_tasks": None,
        "worker_id": "test-worker",
    }


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

    def test_stale_heartbeat_still_exits_when_the_sentry_report_raises(
        self, mocker, tmp_path: Path
    ) -> None:
        # Reporting the stall is worth attempting; ending the process is the part
        # that must happen. A Sentry call raising must not leave a wedged worker up.
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()
        old_time = time.time() - 1000
        os.utime(heartbeat, (old_time, old_time))
        mock_sentry = mocker.patch("freedom_ls.deployment.worker.sentry_sdk")
        mock_sentry.capture_message.side_effect = RuntimeError("sentry is down")
        mock_exit = mocker.patch("freedom_ls.deployment.worker.os._exit")

        with pytest.raises(RuntimeError):
            check_worker_heartbeat(str(heartbeat), max_age_seconds=300)

        mock_exit.assert_called_once_with(1)


class TestStartWatchdog:
    def test_watchdog_keeps_polling_after_a_heartbeat_check_raises_oserror(
        self, mocker, tmp_path: Path
    ) -> None:
        # An OSError from stat -- a mode change on the parent, a full or read-only
        # filesystem -- used to end the daemon thread and leave the worker running
        # with no watchdog at all, silently.
        # A real, fresh heartbeat: start_watchdog's thread polls forever by design,
        # so it outlives this test. Once mocker restores the real check at teardown,
        # a fresh file is what keeps that thread from calling the real os._exit and
        # taking the whole test run down with it.
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()
        checks: list[str] = []
        logged = threading.Event()

        def _raise_once(*args: object, **kwargs: object) -> None:
            checks.append("checked")
            if len(checks) == 1:
                raise PermissionError("heartbeat directory is not readable")

        mocker.patch(
            "freedom_ls.deployment.worker.check_worker_heartbeat",
            side_effect=_raise_once,
        )
        mocker.patch(
            "freedom_ls.deployment.worker.logger.exception",
            side_effect=lambda *a, **k: logged.set(),
        )

        thread = start_watchdog(str(heartbeat), 300, poll_seconds=0.01)
        logged.wait(timeout=2)
        time.sleep(0.05)

        assert logged.is_set()
        assert thread.is_alive()
        assert len(checks) > 1


class TestTouchUntilCapped:
    def test_a_set_stop_event_ends_the_loop_without_waiting_out_the_tick(
        self, mocker, tmp_path: Path
    ) -> None:
        # The test returning at all is the assertion that Event.wait, and not
        # time.sleep, is the timer: a 30s sleep would hang the suite.
        touch = mocker.patch("freedom_ls.deployment.worker.touch_heartbeat")
        stop = threading.Event()
        stop.set()

        touch_until_capped(
            path=str(tmp_path / "heartbeat"),
            stop=stop,
            deadline=time.monotonic() + 300,
            tick_seconds=30,
        )

        touch.assert_not_called()

    def test_a_deadline_already_passed_touches_nothing(
        self, mocker, tmp_path: Path
    ) -> None:
        # This is what keeps a genuinely hung task killable: past the cap the
        # heartbeat is left to go stale on purpose.
        touch = mocker.patch("freedom_ls.deployment.worker.touch_heartbeat")

        touch_until_capped(
            path=str(tmp_path / "heartbeat"),
            stop=threading.Event(),
            deadline=time.monotonic() - 1,
            tick_seconds=0.01,
        )

        touch.assert_not_called()

    def test_touches_the_heartbeat_while_inside_the_deadline(
        self, mocker, tmp_path: Path
    ) -> None:
        touch = mocker.patch("freedom_ls.deployment.worker.touch_heartbeat")

        touch_until_capped(
            path=str(tmp_path / "heartbeat"),
            stop=threading.Event(),
            deadline=time.monotonic() + 0.03,
            tick_seconds=0.01,
        )

        assert touch.call_count >= 1


class TestHeartbeatTicker:
    def test_ticker_touches_the_heartbeat_while_the_block_runs(
        self, mocker, tmp_path: Path
    ) -> None:
        # The core of the fix: a task longer than the heartbeat window no longer
        # lets the watchdog kill the worker doing legitimate work.
        touched = threading.Event()
        mocker.patch(
            "freedom_ls.deployment.worker.touch_heartbeat",
            side_effect=lambda *a, **k: touched.set(),
        )

        with heartbeat_ticker(str(tmp_path / "heartbeat"), 300, tick_seconds=0.01):
            touched.wait(timeout=2)

        assert touched.is_set()

    def test_ticker_touches_nothing_once_the_block_has_exited(
        self, mocker, tmp_path: Path
    ) -> None:
        touch = mocker.patch("freedom_ls.deployment.worker.touch_heartbeat")

        with heartbeat_ticker(str(tmp_path / "heartbeat"), 300, tick_seconds=0.01):
            time.sleep(0.05)
        settled = touch.call_count
        time.sleep(0.1)

        assert touch.call_count == settled

    def test_ticker_deadline_is_max_seconds_from_when_it_starts(
        self, mocker, tmp_path: Path
    ) -> None:
        # An absolute monotonic deadline, so the cap runs from when the task was
        # handed over rather than from whenever the thread was first scheduled.
        capped = mocker.patch("freedom_ls.deployment.worker.touch_until_capped")
        before = time.monotonic()

        with heartbeat_ticker(str(tmp_path / "heartbeat"), 300):
            pass

        assert 300 <= capped.call_args.kwargs["deadline"] - before < 301


class TestHeartbeatWorkerRunTask:
    def test_run_task_delegates_to_upstream_run_task(self, mocker) -> None:
        upstream = mocker.patch.object(Worker, "run_task")
        mocker.patch("freedom_ls.deployment.worker.heartbeat_ticker")
        worker = HeartbeatWorker(**_worker_kwargs())
        task_result = mocker.Mock()

        worker.run_task(task_result)

        upstream.assert_called_once_with(task_result)

    def test_run_task_runs_the_task_inside_a_heartbeat_ticker(self, mocker) -> None:
        call_order: list[str] = []
        ticker = mocker.patch("freedom_ls.deployment.worker.heartbeat_ticker")
        ticker.return_value.__enter__.side_effect = lambda: call_order.append("enter")
        ticker.return_value.__exit__.side_effect = lambda *a: call_order.append("exit")
        mocker.patch.object(
            Worker, "run_task", side_effect=lambda *a: call_order.append("run_task")
        )
        worker = HeartbeatWorker(**_worker_kwargs())

        worker.run_task(mocker.Mock())

        assert call_order == ["enter", "run_task", "exit"]

    def test_run_task_caps_the_ticker_at_the_configured_maximum(
        self, mocker, settings: pytest_django.fixtures.SettingsWrapper
    ) -> None:
        settings.WORKER_MAX_TASK_SECONDS = 42
        ticker = mocker.patch("freedom_ls.deployment.worker.heartbeat_ticker")
        mocker.patch.object(Worker, "run_task")
        worker = HeartbeatWorker(**_worker_kwargs())

        worker.run_task(mocker.Mock())

        assert ticker.call_args.kwargs["max_seconds"] == 42

    def test_run_task_ticks_the_configured_heartbeat_path(
        self, mocker, tmp_path: Path
    ) -> None:
        ticker = mocker.patch("freedom_ls.deployment.worker.heartbeat_ticker")
        mocker.patch.object(Worker, "run_task")
        worker = HeartbeatWorker(**_worker_kwargs())

        worker.run_task(mocker.Mock())

        assert ticker.call_args.args[0] == str(tmp_path / "heartbeat")

    def test_the_ticker_stops_even_when_the_task_raises(self, mocker) -> None:
        # Defensive: upstream's own run_task swallows BaseException, so this path
        # is not reachable today. It stops a future upstream from leaking a thread.
        ticker = mocker.patch("freedom_ls.deployment.worker.heartbeat_ticker")
        mocker.patch.object(Worker, "run_task", side_effect=RuntimeError("boom"))
        worker = HeartbeatWorker(**_worker_kwargs())

        with pytest.raises(RuntimeError):
            worker.run_task(mocker.Mock())

        ticker.return_value.__exit__.assert_called_once()


def test_django_tasks_db_is_pinned_to_the_version_the_worker_loop_was_copied_from() -> (
    None
):
    assert django_tasks_db.__version__ == "0.12.0", (
        "django_tasks_db was upgraded past the version freedom_ls/deployment/"
        "worker.py's HeartbeatWorker.run() was copied from. Re-check the copied "
        "loop, and run_task's override of it, against the new upstream Worker "
        "before moving this pin."
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
    # The heartbeat touch only runs on every iteration for these two values:
    # upstream's batch and max_tasks branches return before it.
    assert kwargs["batch"] is False
    assert kwargs["max_tasks"] is None


class TestGracefulShutdown:
    """The worker stops claiming new work on SIGTERM and drains the task in hand.

    All of it is upstream's, and HeartbeatWorker's copied run() is what a version
    bump breaks silently, so these pin the parts that make the drain work.
    """

    def test_heartbeat_worker_inherits_upstream_signal_handling(self) -> None:
        assert HeartbeatWorker.shutdown is Worker.shutdown
        assert HeartbeatWorker.configure_signals is Worker.configure_signals

    def test_fls_run_worker_configures_signals_before_running(self, mocker) -> None:
        mocker.patch(
            "freedom_ls.deployment.management.commands.fls_run_worker.start_watchdog"
        )
        mock_worker_cls = mocker.patch(
            "freedom_ls.deployment.management.commands.fls_run_worker.HeartbeatWorker"
        )
        worker = mock_worker_cls.return_value
        calls: list[str] = []
        worker.configure_signals.side_effect = lambda: calls.append("configure_signals")
        worker.run.side_effect = lambda: calls.append("run")

        call_command("fls_run_worker")

        assert calls == ["configure_signals", "run"]

    def test_run_claims_no_work_once_running_is_cleared(
        self, settings: pytest_django.fixtures.SettingsWrapper, tmp_path: Path
    ) -> None:
        """What a drained SIGTERM looks like from the loop's side."""
        heartbeat = tmp_path / "heartbeat"
        settings.WORKER_HEARTBEAT_PATH = str(heartbeat)
        worker = HeartbeatWorker(
            queue_names=["*"],
            interval=1,
            batch=False,
            backend_name=DEFAULT_TASK_BACKEND_ALIAS,
            startup_delay=False,
            max_tasks=None,
            worker_id="test-worker",
        )
        worker.running = False

        worker.run()

        assert not heartbeat.exists()
