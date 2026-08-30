"""Tests for the housekeeping sweeps and the fls_run_housekeeping command.

Every test in this file overrides HOUSEKEEPING_HEARTBEAT_PATH to a path under
tmp_path. The setting's real default is the literal /tmp/housekeeping-heartbeat,
so a test that left it alone would write a file on the developer's machine that
nothing cleans up.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import cast

import pytest
import pytest_django.fixtures
import time_machine
from django_tasks import TaskResultStatus
from django_tasks_db.models import DBTaskResult, get_date_max
from pytest_mock import MockerFixture

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.utils import timezone

from freedom_ls.deployment.housekeeping import (
    OrphanReapResult,
    find_late_unpicked_tasks,
    find_orphaned_running_reports,
    find_orphaned_running_tasks,
    mark_orphaned_running_reports_failed,
    mark_orphaned_running_tasks_failed,
    run_housekeeping_sweeps,
)
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport


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
    *,
    status: str = TaskResultStatus.READY,
    run_after: object,
    started_at: datetime | None = None,
    worker_ids: list[str] | None = None,
    task_path: str = "freedom_ls.deployment.tests.test_housekeeping.dummy_task",
) -> DBTaskResult:
    # started_at is a plain nullable column, unlike auto_now_add enqueued_at, so a
    # claimed row can be aged by passing a past value rather than travelling in time.
    return DBTaskResult.objects.create(
        status=status,
        args_kwargs={"args": [], "kwargs": {}},
        task_path=task_path,
        backend_name="default",
        run_after=run_after,
        started_at=started_at,
        worker_ids=worker_ids or [],
    )


def _create_orphan(
    *,
    claimed_hours_ago: float = 2,
    worker_ids: list[str] | None = None,
    task_path: str = "freedom_ls.deployment.tests.test_housekeeping.dummy_task",
) -> DBTaskResult:
    return _create_task_result(
        status=TaskResultStatus.RUNNING,
        run_after=get_date_max(),
        started_at=timezone.now() - timedelta(hours=claimed_hours_ago),
        worker_ids=worker_ids,
        task_path=task_path,
    )


def _create_orphaned_report(
    *,
    started_hours_ago: float = 2,
    **kwargs: object,
) -> GeneratedReport:
    """A cohort report left in RUNNING, as a killed worker would leave it."""
    # cast because factory_boy's generated __call__ is untyped, so mypy reads the
    # call as instantiating the factory class rather than the model.
    return cast(
        GeneratedReport,
        GeneratedReportFactory(
            status=GeneratedReport.STATUS_RUNNING,
            started_at=timezone.now() - timedelta(hours=started_hours_ago),
            **kwargs,
        ),
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
class TestFindOrphanedRunningTasks:
    def test_running_task_claimed_long_ago_is_orphaned(self) -> None:
        task = _create_orphan(claimed_hours_ago=2)

        assert task in find_orphaned_running_tasks(max_age_seconds=3600)

    def test_running_task_claimed_recently_is_not_orphaned(self) -> None:
        task = _create_orphan(claimed_hours_ago=0.1)

        assert task not in find_orphaned_running_tasks(max_age_seconds=3600)

    def test_ready_task_of_any_age_is_not_orphaned(self) -> None:
        """The late check owns READY; this one owns RUNNING. They must not overlap."""
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            task = _create_task_result(run_after=get_date_max())

        assert task not in find_orphaned_running_tasks(max_age_seconds=3600)

    def test_failed_task_claimed_long_ago_is_not_orphaned(self) -> None:
        """Nothing re-reaps a row an earlier run already closed."""
        task = _create_task_result(
            status=TaskResultStatus.FAILED,
            run_after=get_date_max(),
            started_at=timezone.now() - timedelta(hours=5),
        )

        assert task not in find_orphaned_running_tasks(max_age_seconds=3600)

    def test_running_task_never_claimed_is_not_orphaned(self) -> None:
        """A NULL started_at never satisfies the comparison, which is correct."""
        task = _create_task_result(
            status=TaskResultStatus.RUNNING, run_after=get_date_max()
        )

        assert task not in find_orphaned_running_tasks(max_age_seconds=3600)


@pytest.mark.django_db
class TestMarkOrphanedRunningTasksFailed:
    def test_orphaned_task_is_marked_failed_and_not_requeued(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        task = _create_orphan()

        mark_orphaned_running_tasks_failed(max_age_seconds=3600)

        task.refresh_from_db()
        assert task.status == TaskResultStatus.FAILED
        assert task.status != TaskResultStatus.READY
        assert task.finished_at is not None

    def test_orphaned_task_records_the_housekeeping_exception_path(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        task = _create_orphan()

        mark_orphaned_running_tasks_failed(max_age_seconds=3600)

        task.refresh_from_db()
        assert (
            task.exception_class_path
            == "freedom_ls.deployment.housekeeping.OrphanedTaskError"
        )
        # The exception is never raised, so format_exception yields the message and
        # no frames. That one line is everything the row will say.
        assert "not requeued" in task.traceback

    def test_orphaned_task_traceback_names_the_worker_that_held_it(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        task = _create_orphan(worker_ids=["worker-abc"])

        mark_orphaned_running_tasks_failed(max_age_seconds=3600)

        task.refresh_from_db()
        assert "worker-abc" in task.traceback

    def test_recently_claimed_task_is_left_running(self, mocker: MockerFixture) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        task = _create_orphan(claimed_hours_ago=0.1)

        mark_orphaned_running_tasks_failed(max_age_seconds=3600)

        task.refresh_from_db()
        assert task.status == TaskResultStatus.RUNNING
        assert task.finished_at is None

    def test_every_row_marked_is_counted(self, mocker: MockerFixture) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        _create_orphan()
        _create_orphan()

        result = mark_orphaned_running_tasks_failed(max_age_seconds=3600)

        assert result == OrphanReapResult(marked_failed=2, left_running=0)

    def test_a_row_the_database_refuses_does_not_stop_the_rest(
        self, mocker: MockerFixture
    ) -> None:
        # Patched rather than provoked: a real DatabaseError poisons the test's
        # wrapping transaction and every later query raises.
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        set_failed = mocker.patch.object(
            DBTaskResult, "set_failed", side_effect=[DatabaseError("nope"), None]
        )
        _create_orphan()
        _create_orphan()

        result = mark_orphaned_running_tasks_failed(max_age_seconds=3600)

        assert result == OrphanReapResult(marked_failed=1, left_running=1)
        assert set_failed.call_count == 2

    def test_each_orphaned_task_is_reported_to_sentry_separately(
        self, mocker: MockerFixture
    ) -> None:
        mock_sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        _create_orphan(task_path="freedom_ls.tests.first_task")
        _create_orphan(task_path="freedom_ls.tests.second_task")

        mark_orphaned_running_tasks_failed(max_age_seconds=3600)

        reported = [call.args[0] for call in mock_sentry.capture_message.call_args_list]
        assert len(reported) == 2
        assert any("freedom_ls.tests.first_task" in message for message in reported)
        assert any("freedom_ls.tests.second_task" in message for message in reported)


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
    def test_late_unpicked_task_reported_to_sentry_and_returned_as_a_finding(
        self, mocker: MockerFixture, database_task_backend: None
    ) -> None:
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            _create_task_result(run_after=get_date_max())
        mock_sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")

        outcome = run_housekeeping_sweeps()

        mock_sentry.capture_message.assert_called_once()
        assert len(outcome.findings) == 1
        assert "unpicked" in outcome.findings[0]
        # A stopped worker is not a fault in housekeeping, so it withholds nothing.
        assert outcome.sweep_failures == []


@pytest.mark.django_db
class TestOrphanedTaskReporting:
    def test_orphaned_task_is_reported_but_fails_nothing(
        self, mocker: MockerFixture, database_task_backend: None
    ) -> None:
        mock_sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        _create_orphan()

        outcome = run_housekeeping_sweeps()

        mock_sentry.capture_message.assert_called_once()
        assert outcome.sweep_failures == []
        assert outcome.findings == []
        assert len(outcome.notes) == 1
        assert "1 task result(s) orphaned" in outcome.notes[0]

    def test_reap_failure_is_a_sweep_failure(
        self, mocker: MockerFixture, database_task_backend: None
    ) -> None:
        mock_sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        mocker.patch(
            "freedom_ls.deployment.housekeeping.mark_orphaned_running_tasks_failed",
            side_effect=DatabaseError("db is gone"),
        )

        outcome = run_housekeeping_sweeps()

        assert len(outcome.sweep_failures) == 1
        assert "orphaned task sweep failed" in outcome.sweep_failures[0]
        mock_sentry.capture_exception.assert_called_once()

    def test_rows_left_running_are_a_sweep_failure(
        self, mocker: MockerFixture, database_task_backend: None
    ) -> None:
        mock_sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        mocker.patch(
            "freedom_ls.deployment.housekeeping.mark_orphaned_running_tasks_failed",
            return_value=OrphanReapResult(marked_failed=0, left_running=1),
        )

        outcome = run_housekeeping_sweeps()

        assert len(outcome.sweep_failures) == 1
        assert "still RUNNING" in outcome.sweep_failures[0]
        # The reap already captured per row; nothing captures it a second time here.
        mock_sentry.capture_exception.assert_not_called()

    def test_prune_failure_still_reaps_orphaned_tasks(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=CommandError("prune is broken"),
        )
        task = _create_orphan()

        run_housekeeping_sweeps()

        task.refresh_from_db()
        assert task.status == TaskResultStatus.FAILED


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

    def test_late_task_finding_raises_but_still_touches_heartbeat(
        self, mocker: MockerFixture, database_task_backend: None, tmp_path: Path
    ) -> None:
        """A stopped worker fails the run without calling housekeeping itself dead."""
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        heartbeat = tmp_path / "heartbeat"
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            _create_task_result(run_after=get_date_max())

        with pytest.raises(CommandError):
            call_command("fls_run_housekeeping", stdout=StringIO())

        assert heartbeat.exists()

    def test_orphaned_task_alone_neither_raises_nor_withholds_the_heartbeat(
        self, mocker: MockerFixture, database_task_backend: None, tmp_path: Path
    ) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        heartbeat = tmp_path / "heartbeat"
        task = _create_orphan()

        stdout = StringIO()
        call_command("fls_run_housekeeping", stdout=stdout)

        task.refresh_from_db()
        assert task.status == TaskResultStatus.FAILED
        assert heartbeat.exists()
        assert "orphaned in RUNNING" in stdout.getvalue()

    def test_failure_message_names_a_sweep_failure_apart_from_a_finding(
        self, mocker: MockerFixture, database_task_backend: None
    ) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")

        def fake_call_command(command_name: str, **kwargs: object) -> None:
            if command_name == "prune_db_task_results":
                raise CommandError("prune is broken")

        mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=fake_call_command,
        )
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            _create_task_result(run_after=get_date_max())

        with pytest.raises(CommandError) as excinfo:
            call_command("fls_run_housekeeping", stdout=StringIO())

        message = str(excinfo.value)
        assert "Sweep failures:" in message
        assert "prune_db_task_results" in message
        assert "Findings:" in message
        assert "unpicked" in message

    def test_a_sweep_failure_alongside_a_finding_still_withholds_the_heartbeat(
        self, mocker: MockerFixture, database_task_backend: None, tmp_path: Path
    ) -> None:
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        heartbeat = tmp_path / "heartbeat"

        def fake_call_command(command_name: str, **kwargs: object) -> None:
            if command_name == "prune_db_task_results":
                raise CommandError("prune is broken")

        mocker.patch(
            "freedom_ls.deployment.housekeeping.call_command",
            side_effect=fake_call_command,
        )
        with time_machine.travel(timezone.now() - timedelta(hours=2), tick=False):
            _create_task_result(run_after=get_date_max())

        with pytest.raises(CommandError):
            call_command("fls_run_housekeeping", stdout=StringIO())

        assert not heartbeat.exists()


@pytest.mark.django_db
class TestFindOrphanedRunningReports:
    def test_report_running_since_long_ago_is_orphaned(
        self, mock_site_context: None
    ) -> None:
        # Arrange
        report = _create_orphaned_report(started_hours_ago=2)

        # Act
        orphans = find_orphaned_running_reports(3600)

        # Assert
        assert list(orphans) == [report]

    def test_report_running_recently_is_not_orphaned(
        self, mock_site_context: None
    ) -> None:
        # Arrange
        _create_orphaned_report(started_hours_ago=0.1)

        # Act
        orphans = find_orphaned_running_reports(3600)

        # Assert
        assert list(orphans) == []

    def test_pending_report_is_not_orphaned(self, mock_site_context: None) -> None:
        # A PENDING row has no started_at, so nothing has claimed it yet.
        # Arrange
        GeneratedReportFactory(status=GeneratedReport.STATUS_PENDING)

        # Act
        orphans = find_orphaned_running_reports(3600)

        # Assert
        assert list(orphans) == []

    def test_failed_report_is_not_orphaned(self, mock_site_context: None) -> None:
        # Arrange
        GeneratedReportFactory(
            status=GeneratedReport.STATUS_FAILED,
            started_at=timezone.now() - timedelta(hours=2),
        )

        # Act
        orphans = find_orphaned_running_reports(3600)

        # Assert
        assert list(orphans) == []


@pytest.mark.django_db
class TestMarkOrphanedRunningReportsFailed:
    def test_orphaned_report_is_marked_failed(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        report = _create_orphaned_report()

        # Act
        mark_orphaned_running_reports_failed(3600)

        # Assert
        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED

    def test_orphaned_report_stamps_finished_at(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        report = _create_orphaned_report()

        # Act
        mark_orphaned_running_reports_failed(3600)

        # Assert
        report.refresh_from_db()
        assert report.finished_at is not None

    def test_orphaned_report_error_message_says_housekeeping_closed_it(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        report = _create_orphaned_report()

        # Act
        mark_orphaned_running_reports_failed(3600)

        # Assert
        report.refresh_from_db()
        assert "fls_run_housekeeping" in report.error_message

    def test_orphaned_report_frees_the_cohort_for_a_new_report(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # The point of the sweep: the partial unique index allows one pending or
        # running report per cohort, so a stranded row blocks the cohort forever.
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        report = _create_orphaned_report()

        # Act
        mark_orphaned_running_reports_failed(3600)

        # Assert
        replacement = GeneratedReportFactory(
            cohort=report.cohort, status=GeneratedReport.STATUS_PENDING
        )
        assert replacement.pk is not None

    def test_recently_started_report_is_left_running(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        report = _create_orphaned_report(started_hours_ago=0.1)

        # Act
        mark_orphaned_running_reports_failed(3600)

        # Assert
        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_RUNNING

    def test_every_report_marked_is_counted(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        _create_orphaned_report()
        _create_orphaned_report()

        # Act
        result = mark_orphaned_running_reports_failed(3600)

        # Assert
        assert result == OrphanReapResult(marked_failed=2, left_running=0)

    def test_a_report_the_database_refuses_does_not_stop_the_rest(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # Patched rather than provoked: a real DatabaseError poisons the test
        # transaction and every later query in it.
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        _create_orphaned_report()
        _create_orphaned_report()
        mocker.patch.object(
            GeneratedReport, "save", side_effect=[DatabaseError("nope"), None]
        )

        # Act
        result = mark_orphaned_running_reports_failed(3600)

        # Assert
        assert result == OrphanReapResult(marked_failed=1, left_running=1)

    def test_each_orphaned_report_is_reported_to_sentry_separately(
        self, mocker: MockerFixture, mock_site_context: None
    ) -> None:
        # Arrange
        sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        _create_orphaned_report()
        _create_orphaned_report()

        # Act
        mark_orphaned_running_reports_failed(3600)

        # Assert
        assert sentry.capture_message.call_count == 2


@pytest.mark.django_db
class TestOrphanedReportReporting:
    def test_orphaned_report_is_closed_and_reported_but_fails_nothing(
        self,
        mocker: MockerFixture,
        database_task_backend: None,
        mock_site_context: None,
    ) -> None:
        # The sweep worked, so it fails nothing. What it found reaches an operator
        # through Sentry, not by turning the housekeeping cron red every night.
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        _create_orphaned_report()

        # Act
        outcome = run_housekeeping_sweeps()

        # Assert
        assert outcome.sweep_failures == []
        assert outcome.findings == []
        assert any("cohort report(s) orphaned" in note for note in outcome.notes)

    def test_report_reap_failure_is_a_sweep_failure(
        self, mocker: MockerFixture, database_task_backend: None
    ) -> None:
        # Arrange
        sentry = mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        mocker.patch(
            "freedom_ls.deployment.housekeeping.mark_orphaned_running_reports_failed",
            side_effect=DatabaseError("the reports table is gone"),
        )

        # Act
        outcome = run_housekeeping_sweeps()

        # Assert
        assert any(
            "orphaned report sweep failed" in failure
            for failure in outcome.sweep_failures
        )
        sentry.capture_exception.assert_called_once()

    def test_reports_left_running_are_a_sweep_failure(
        self, mocker: MockerFixture, database_task_backend: None
    ) -> None:
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        mocker.patch(
            "freedom_ls.deployment.housekeeping.mark_orphaned_running_reports_failed",
            return_value=OrphanReapResult(marked_failed=0, left_running=1),
        )

        # Act
        outcome = run_housekeeping_sweeps()

        # Assert
        assert any("still RUNNING" in failure for failure in outcome.sweep_failures)

    def test_task_reap_failure_still_reaps_orphaned_reports(
        self,
        mocker: MockerFixture,
        database_task_backend: None,
        mock_site_context: None,
    ) -> None:
        # Sweep independence: one failing step must not skip the ones after it.
        # Arrange
        mocker.patch("freedom_ls.deployment.housekeeping.sentry_sdk")
        mocker.patch(
            "freedom_ls.deployment.housekeeping.mark_orphaned_running_tasks_failed",
            side_effect=DatabaseError("the task table is gone"),
        )
        report = _create_orphaned_report()

        # Act
        run_housekeeping_sweeps()

        # Assert
        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED
