"""The run-record sweeps: they close stale queued and running records on every
site and delete finished ones, reporting each row they close."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
import time_machine

from django.contrib.sites.models import Site
from django.db.models import Model

from freedom_ls.panel_framework.bulk_actions import RecordedBulkAction
from freedom_ls.panel_framework.housekeeping import (
    ORPHANED_MESSAGE,
    UNPICKED_MESSAGE,
    delete_finished_records,
    mark_orphaned_runs_failed,
    mark_unpicked_runs_failed,
    sweep_run_records,
)
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

from .helpers import make_staff_user

pytestmark = pytest.mark.django_db

FIXED_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _make_run(
    *,
    status: str,
    created_ago: timedelta = timedelta(0),
    started_ago: timedelta | None = None,
    finished_ago: timedelta | None = None,
    site: Site | None = None,
    action_path: str = "nowhere.Deactivate",
) -> BulkActionRun:
    """A run in `status`, with its timestamps set relative to FIXED_NOW.

    created_at is auto_now_add, so it is set by creating the row while the clock
    is `created_ago` in the past.
    """
    requester = make_staff_user()
    run = BulkActionRun(
        requested_by=requester,
        status=status,
        started_at=None if started_ago is None else FIXED_NOW - started_ago,
        finished_at=None if finished_ago is None else FIXED_NOW - finished_ago,
        action_path=action_path,
        table_key="stubs",
        action_name="deactivate",
    )
    if site is not None:
        run.site = site
    with time_machine.travel(FIXED_NOW - created_ago, tick=False):
        run.save()
    return run


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[type[Model], str, int]] = []

    def __call__(self, model: type[Model], pk: str, site_id: int) -> None:
        self.calls.append((model, pk, site_id))


class TestMarkUnpickedRunsFailed:
    def test_queued_record_older_than_the_window_is_failed(
        self, mock_site_context
    ) -> None:
        record = _make_run(status=RunStatus.QUEUED, created_ago=timedelta(seconds=3601))

        with time_machine.travel(FIXED_NOW, tick=False):
            closed = mark_unpicked_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert (closed, record.status, record.finished_at) == (
            1,
            RunStatus.FAILED,
            FIXED_NOW,
        )

    def test_error_message_tells_the_reader_it_did_not_start(
        self, mock_site_context
    ) -> None:
        record = _make_run(status=RunStatus.QUEUED, created_ago=timedelta(hours=2))

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_unpicked_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.error_message == UNPICKED_MESSAGE

    def test_a_record_exactly_at_the_threshold_is_closed(
        self, mock_site_context
    ) -> None:
        record = _make_run(status=RunStatus.QUEUED, created_ago=timedelta(seconds=3600))

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_unpicked_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.status == RunStatus.FAILED

    def test_queued_record_inside_the_window_is_left_queued(
        self, mock_site_context
    ) -> None:
        record = _make_run(status=RunStatus.QUEUED, created_ago=timedelta(seconds=3599))

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_unpicked_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.status == RunStatus.QUEUED

    def test_running_record_is_not_touched(self, mock_site_context) -> None:
        record = _make_run(
            status=RunStatus.RUNNING,
            created_ago=timedelta(hours=5),
            started_ago=timedelta(minutes=1),
        )

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_unpicked_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.status == RunStatus.RUNNING

    def test_a_second_sweep_closes_nothing(self, mock_site_context) -> None:
        _make_run(status=RunStatus.QUEUED, created_ago=timedelta(hours=2))

        with time_machine.travel(FIXED_NOW, tick=False):
            first = mark_unpicked_runs_failed(BulkActionRun, 3600)
            second = mark_unpicked_runs_failed(BulkActionRun, 3600)

        assert (first, second) == (1, 0)

    def test_report_closed_is_called_once_per_closed_row(
        self, mock_site_context
    ) -> None:
        records = [
            _make_run(status=RunStatus.QUEUED, created_ago=timedelta(hours=2))
            for _ in range(2)
        ]
        recorder = _Recorder()

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_unpicked_runs_failed(BulkActionRun, 3600, report_closed=recorder)

        assert sorted(recorder.calls, key=lambda call: call[1]) == sorted(
            [(BulkActionRun, str(r.pk), r.site_id) for r in records],
            key=lambda call: call[1],
        )


class TestMarkOrphanedRunsFailed:
    def test_running_record_started_before_the_window_is_failed(
        self, mock_site_context
    ) -> None:
        record = _make_run(
            status=RunStatus.RUNNING, started_ago=timedelta(seconds=3601)
        )

        with time_machine.travel(FIXED_NOW, tick=False):
            closed = mark_orphaned_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert (closed, record.status, record.finished_at) == (
            1,
            RunStatus.FAILED,
            FIXED_NOW,
        )

    def test_error_message_tells_the_reader_it_stopped(self, mock_site_context) -> None:
        record = _make_run(status=RunStatus.RUNNING, started_ago=timedelta(hours=2))

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_orphaned_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.error_message == ORPHANED_MESSAGE

    def test_a_record_exactly_at_the_threshold_is_closed(
        self, mock_site_context
    ) -> None:
        record = _make_run(
            status=RunStatus.RUNNING, started_ago=timedelta(seconds=3600)
        )

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_orphaned_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.status == RunStatus.FAILED

    def test_running_record_started_inside_the_window_is_left_running(
        self, mock_site_context
    ) -> None:
        record = _make_run(
            status=RunStatus.RUNNING, started_ago=timedelta(seconds=3599)
        )

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_orphaned_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.status == RunStatus.RUNNING

    def test_queued_record_is_not_touched(self, mock_site_context) -> None:
        record = _make_run(status=RunStatus.QUEUED, created_ago=timedelta(hours=5))

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_orphaned_runs_failed(BulkActionRun, 3600)

        record.refresh_from_db()
        assert record.status == RunStatus.QUEUED

    def test_a_second_sweep_closes_nothing(self, mock_site_context) -> None:
        _make_run(status=RunStatus.RUNNING, started_ago=timedelta(hours=2))

        with time_machine.travel(FIXED_NOW, tick=False):
            first = mark_orphaned_runs_failed(BulkActionRun, 3600)
            second = mark_orphaned_runs_failed(BulkActionRun, 3600)

        assert (first, second) == (1, 0)

    def test_report_closed_is_called_once_per_closed_row(
        self, mock_site_context
    ) -> None:
        record = _make_run(status=RunStatus.RUNNING, started_ago=timedelta(hours=2))
        recorder = _Recorder()

        with time_machine.travel(FIXED_NOW, tick=False):
            mark_orphaned_runs_failed(BulkActionRun, 3600, report_closed=recorder)

        assert recorder.calls == [(BulkActionRun, str(record.pk), record.site_id)]


class TestDeleteFinishedRecords:
    def test_record_finished_before_the_retention_window_is_deleted(
        self, mock_site_context
    ) -> None:
        _make_run(status=RunStatus.DONE, finished_ago=timedelta(days=30, seconds=1))

        with time_machine.travel(FIXED_NOW, tick=False):
            deleted = delete_finished_records(BulkActionRun, 30)

        assert (deleted, BulkActionRun._base_manager.count()) == (1, 0)

    def test_record_finished_exactly_at_the_retention_boundary_is_deleted(
        self, mock_site_context
    ) -> None:
        _make_run(status=RunStatus.DONE, finished_ago=timedelta(days=30))

        with time_machine.travel(FIXED_NOW, tick=False):
            delete_finished_records(BulkActionRun, 30)

        assert BulkActionRun._base_manager.count() == 0

    def test_record_finished_inside_the_retention_window_is_kept(
        self, mock_site_context
    ) -> None:
        _make_run(status=RunStatus.DONE, finished_ago=timedelta(days=29, hours=23))

        with time_machine.travel(FIXED_NOW, tick=False):
            delete_finished_records(BulkActionRun, 30)

        assert BulkActionRun._base_manager.count() == 1

    def test_unfinished_record_is_kept_however_old(self, mock_site_context) -> None:
        _make_run(status=RunStatus.QUEUED, created_ago=timedelta(days=90))

        with time_machine.travel(FIXED_NOW, tick=False):
            delete_finished_records(BulkActionRun, 30)

        assert BulkActionRun._base_manager.count() == 1

    def test_record_failed_by_a_sweep_is_deleted_once_retention_passes(
        self, mock_site_context
    ) -> None:
        _make_run(status=RunStatus.QUEUED, created_ago=timedelta(hours=2))
        with time_machine.travel(FIXED_NOW, tick=False):
            mark_unpicked_runs_failed(BulkActionRun, 3600)

        with time_machine.travel(FIXED_NOW + timedelta(days=29), tick=False):
            delete_finished_records(BulkActionRun, 30)
        kept = BulkActionRun._base_manager.count()
        with time_machine.travel(FIXED_NOW + timedelta(days=31), tick=False):
            delete_finished_records(BulkActionRun, 30)

        assert (kept, BulkActionRun._base_manager.count()) == (1, 0)


class TestSweepRunRecords:
    def test_returns_the_unpicked_orphaned_and_deleted_counts(
        self, mock_site_context
    ) -> None:
        _make_run(status=RunStatus.QUEUED, created_ago=timedelta(hours=2))
        _make_run(status=RunStatus.RUNNING, started_ago=timedelta(hours=2))
        _make_run(status=RunStatus.RUNNING, started_ago=timedelta(hours=3))
        _make_run(status=RunStatus.DONE, finished_ago=timedelta(days=40))

        with time_machine.travel(FIXED_NOW, tick=False):
            counts = sweep_run_records(
                BulkActionRun,
                unpicked_max_age=3600,
                orphaned_max_age=3600,
                retention_days=30,
            )

        assert counts == (1, 2, 1)


class TestSweepsSpanEverySite:
    def test_stale_rows_on_two_sites_are_closed_and_each_reported_with_its_own_site(
        self, mock_site_context
    ) -> None:
        other_site = SiteFactory()
        with site_context(other_site):
            on_other = _make_run(
                status=RunStatus.QUEUED,
                created_ago=timedelta(hours=2),
                site=other_site,
            )
        on_current = _make_run(status=RunStatus.QUEUED, created_ago=timedelta(hours=2))
        recorder = _Recorder()

        with time_machine.travel(FIXED_NOW, tick=False):
            closed = mark_unpicked_runs_failed(
                BulkActionRun, 3600, report_closed=recorder
            )

        assert closed == 2
        assert {(pk, site_id) for _, pk, site_id in recorder.calls} == {
            (str(on_other.pk), other_site.pk),
            (str(on_current.pk), on_current.site_id),
        }


class _ReportingAction(RecordedBulkAction):
    """Records the runs it is told have finished."""

    finished: ClassVar[list[str]] = []

    def on_finished(self, run: BulkActionRun) -> None:
        type(self).finished.append(str(run.pk))


def _queued_for_two_hours(action_path: str) -> BulkActionRun:
    return _make_run(
        status=RunStatus.QUEUED,
        created_ago=timedelta(hours=2),
        action_path=action_path,
    )


def _running_for_two_hours(action_path: str) -> BulkActionRun:
    return _make_run(
        status=RunStatus.RUNNING,
        started_ago=timedelta(hours=2),
        action_path=action_path,
    )


@pytest.mark.parametrize(
    ("sweep", "make_run"),
    [
        (mark_unpicked_runs_failed, _queued_for_two_hours),
        (mark_orphaned_runs_failed, _running_for_two_hours),
    ],
    ids=["unpicked", "orphaned"],
)
def test_a_run_closed_by_a_sweep_is_reported_to_its_action(
    mock_site_context,
    monkeypatch: pytest.MonkeyPatch,
    sweep: Callable[[type[Model], int], int],
    make_run: Callable[[str], BulkActionRun],
) -> None:
    """The sweeps close runs with a bare update, so the action's on_finished
    would never run and the requester would never hear the run had stopped."""
    monkeypatch.setattr(_ReportingAction, "finished", [])
    record = make_run(f"{__name__}.{_ReportingAction.__name__}")

    with time_machine.travel(FIXED_NOW, tick=False):
        closed = sweep(BulkActionRun, 3600)

    record.refresh_from_db()
    assert (closed, record.status) == (1, RunStatus.FAILED)
    assert _ReportingAction.finished == [str(record.pk)]
