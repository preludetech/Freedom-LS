"""Tests for the housekeeping sweeps and the fls_run_housekeeping command.

Every test in this file overrides HOUSEKEEPING_HEARTBEAT_PATH to a path under
tmp_path. The setting's real default is the literal /tmp/heartbeat, the same
default the worker uses, so a test that left it alone would write a file
outside tmp_path and could read the worker tests' own heartbeat mtime.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
import pytest_django.fixtures
import time_machine
from django_tasks import TaskResultStatus
from django_tasks_db.models import DBTaskResult, get_date_max

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from freedom_ls.deployment.housekeeping import (
    find_late_unpicked_tasks,
    run_housekeeping_sweeps,
)


@pytest.fixture(autouse=True)
def _heartbeat_path_under_tmp(
    settings: pytest_django.fixtures.SettingsWrapper, tmp_path: Path
) -> None:
    settings.HOUSEKEEPING_HEARTBEAT_PATH = str(tmp_path / "heartbeat")


@pytest.fixture
def database_task_backend(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Switch TASKS to the real database backend.

    The test settings default TASKS to ImmediateBackend, under which
    prune_db_task_results always raises CommandError regardless of the data
    present. Tests that need a clean sweep take this fixture; the tests that
    exercise that failure path deliberately don't.
    """
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}


def _create_task_result(
    *, status: str = TaskResultStatus.READY, run_after: object
) -> DBTaskResult:
    return DBTaskResult.objects.create(
        status=status,
        args_kwargs={"args": [], "kwargs": {}},
        task_path="freedom_ls.deployment.tests.test_housekeeping.dummy_task",
        backend_name="default",
        run_after=run_after,
    )


@pytest.mark.django_db
class TestFindLateUnpickedTasks:
    def test_ready_task_with_no_schedule_enqueued_long_ago_is_late(self) -> None:
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            task = _create_task_result(run_after=get_date_max())

        assert task in find_late_unpicked_tasks(max_age_seconds=3600)

    def test_ready_task_scheduled_in_the_future_is_not_late(self) -> None:
        task = _create_task_result(run_after=timezone.now() + timedelta(hours=1))

        assert task not in find_late_unpicked_tasks(max_age_seconds=3600)

    def test_ready_task_scheduled_long_ago_is_late(self) -> None:
        task = _create_task_result(run_after=timezone.now() - timedelta(hours=2))

        assert task in find_late_unpicked_tasks(max_age_seconds=3600)

    def test_successful_task_of_any_age_is_not_late(self) -> None:
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            task = _create_task_result(
                status=TaskResultStatus.SUCCESSFUL, run_after=get_date_max()
            )

        assert task not in find_late_unpicked_tasks(max_age_seconds=3600)


@pytest.mark.django_db
class TestRunHousekeepingSweepsIndependence:
    def test_prune_failure_still_runs_session_sweep(self, mocker) -> None:
        def fake_call_command(command_name: str, **kwargs: object) -> None:
            if command_name == "prune_db_task_results":
                raise CommandError("prune is broken")

        mock_call_command = mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=fake_call_command,
        )
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")

        run_housekeeping_sweeps()

        ran_commands = [call.args[0] for call in mock_call_command.call_args_list]
        assert "clearsessions" in ran_commands

    def test_clearsessions_failure_still_runs_prune(self, mocker) -> None:
        def fake_call_command(command_name: str, **kwargs: object) -> None:
            if command_name == "clearsessions":
                raise CommandError("clearsessions is broken")

        mock_call_command = mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=fake_call_command,
        )
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")

        run_housekeeping_sweeps()

        ran_commands = [call.args[0] for call in mock_call_command.call_args_list]
        assert "prune_db_task_results" in ran_commands

    def test_unanticipated_exception_from_a_sweep_propagates(self, mocker) -> None:
        def fake_call_command(command_name: str, **kwargs: object) -> None:
            if command_name == "prune_db_task_results":
                raise ValueError("not a sweep failure")

        mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=fake_call_command,
        )

        with pytest.raises(ValueError, match="not a sweep failure"):
            run_housekeeping_sweeps()

    def test_both_sweep_failures_each_reach_sentry(self, mocker) -> None:
        mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=CommandError("boom"),
        )
        mock_sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")

        run_housekeeping_sweeps()

        assert mock_sentry.capture_exception.call_count == 2


@pytest.mark.django_db
class TestLateTaskReporting:
    def test_late_unpicked_task_reported_to_sentry_and_returned_as_failure(
        self, mocker, database_task_backend: None
    ) -> None:
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            _create_task_result(run_after=get_date_max())
        mock_sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")

        failures = run_housekeeping_sweeps()

        mock_sentry.capture_message.assert_called_once()
        assert len(failures) == 1
        assert "unpicked" in failures[0]


@pytest.mark.django_db
class TestSessionSweep:
    def test_expired_sessions_deleted_and_live_sessions_kept(
        self, database_task_backend: None
    ) -> None:
        Session.objects.create(
            session_key="expired-session",
            session_data="",
            expire_date=timezone.now() - timedelta(days=1),
        )
        Session.objects.create(
            session_key="live-session",
            session_data="",
            expire_date=timezone.now() + timedelta(days=1),
        )

        run_housekeeping_sweeps()

        remaining = set(Session.objects.values_list("session_key", flat=True))
        assert remaining == {"live-session"}


@pytest.mark.django_db
class TestFlsRunHousekeepingCommand:
    def test_prune_failure_raises_and_leaves_heartbeat_untouched(
        self, tmp_path: Path
    ) -> None:
        heartbeat = tmp_path / "heartbeat"

        with pytest.raises(CommandError):
            call_command("fls_run_housekeeping", stdout=StringIO())

        assert not heartbeat.exists()

    def test_clearsessions_failure_raises_and_leaves_heartbeat_untouched(
        self, mocker, tmp_path: Path
    ) -> None:
        heartbeat = tmp_path / "heartbeat"

        def fake_call_command(command_name: str, **kwargs: object) -> None:
            if command_name == "clearsessions":
                raise CommandError("clearsessions is broken")

        mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=fake_call_command,
        )

        with pytest.raises(CommandError):
            call_command("fls_run_housekeeping", stdout=StringIO())

        assert not heartbeat.exists()

    def test_clean_run_touches_heartbeat(
        self, database_task_backend: None, tmp_path: Path
    ) -> None:
        heartbeat = tmp_path / "heartbeat"

        call_command("fls_run_housekeeping", stdout=StringIO())

        assert heartbeat.exists()
