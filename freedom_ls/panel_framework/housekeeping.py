"""Sweeps that close the run records a dead worker left open, and delete the
ones that finished long ago.

A run record is any model whose rows satisfy `RunRecord`: a `BulkActionRun`, or a
host's own record of a background run. These sweeps close run records only. A
host's task-result and report sweeps (in FLS, `mark_orphaned_running_tasks_failed`
and `mark_orphaned_running_reports_failed`) are a separate job the host owns.

The sweeps run from a scheduled job with no request and so no current site, and
they must close stale rows on every site. They therefore read through
`model._base_manager`, not the site-aware `objects`, and report each closed row
with its own `site_id`.

The module reads no setting: the caller passes every threshold, and a host that
wants an operator alert passes `report_closed`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from django.db.models import Model, QuerySet
from django.utils import timezone

from freedom_ls.panel_framework.bulk_runs import report_finished
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus

__all__ = [
    "ORPHANED_MESSAGE",
    "UNPICKED_MESSAGE",
    "ReportClosed",
    "delete_finished_records",
    "mark_orphaned_runs_failed",
    "mark_unpicked_runs_failed",
    "sweep_run_records",
]

#: Called once for each record a sweep closed, with its model, primary key and site.
type ReportClosed = Callable[[type[Model], str, int], None]

#: What the requester reads on a record a sweep closed. The record's page
#: shows error_message word for word, so it carries no operator detail.
UNPICKED_MESSAGE = "The background task did not start. Start the action again."
ORPHANED_MESSAGE = (
    "The background task stopped before it finished. Check what was applied "
    "before starting it again."
)


def _close_as_failed(
    model: type[Model],
    records: QuerySet,
    error_message: str,
    report_closed: ReportClosed | None,
) -> int:
    """Close every record in `records` as FAILED, at the current time, and
    tell a bulk action run's action, which a bare update would skip and
    which is how the requester hears about a run they are no longer
    watching. `report_closed` hears of every row closed. Returns how many rows
    were closed."""
    closed = list(records.values_list("pk", "site_id"))
    if not closed:
        return 0
    records.filter(pk__in=[pk for pk, _ in closed]).update(
        status=RunStatus.FAILED, error_message=error_message, finished_at=timezone.now()
    )
    for pk, site_id in closed:
        if model is BulkActionRun:
            # A bare update skips the action's own hook, which is how the
            # requester hears about a run they are no longer watching.
            report_finished(str(pk), site_id)
        if report_closed is not None:
            report_closed(model, str(pk), site_id)
    return len(closed)


def mark_unpicked_runs_failed(
    model: type[Model],
    max_age_seconds: int,
    *,
    report_closed: ReportClosed | None = None,
) -> int:
    """Close every QUEUED record older than max_age_seconds as FAILED.

    A record still QUEUED this long after it was created means no worker ever took
    its task. The task is not requeued; the reader starts the action again.
    Returns how many rows were closed.
    """
    return _close_as_failed(
        model,
        model._base_manager.filter(
            status=RunStatus.QUEUED,
            created_at__lte=timezone.now() - timedelta(seconds=max_age_seconds),
        ),
        UNPICKED_MESSAGE,
        report_closed,
    )


def mark_orphaned_runs_failed(
    model: type[Model],
    max_age_seconds: int,
    *,
    report_closed: ReportClosed | None = None,
) -> int:
    """Close every RUNNING record started over max_age_seconds ago as FAILED.

    started_at is how long the worker has held the record. A NULL started_at never
    satisfies the comparison, which is right for a record no worker has begun.
    The work is not run again: part of it may already have been applied.
    Returns how many rows were closed.
    """
    return _close_as_failed(
        model,
        model._base_manager.filter(
            status=RunStatus.RUNNING,
            started_at__lte=timezone.now() - timedelta(seconds=max_age_seconds),
        ),
        ORPHANED_MESSAGE,
        report_closed,
    )


def delete_finished_records(model: type[Model], retention_days: int) -> int:
    """Delete records that finished more than `retention_days` days ago.

    Records closed by the sweeps above carry a finished_at like any other
    terminal record, so they are deleted here in their turn. A record that has
    not finished has a NULL finished_at and is never matched.
    Returns how many rows were deleted.
    """
    cutoff = timezone.now() - timedelta(days=retention_days)
    _, deleted_per_model = model._base_manager.filter(finished_at__lte=cutoff).delete()
    return deleted_per_model.get(model._meta.label, 0)


def sweep_run_records(
    model: type[Model],
    *,
    unpicked_max_age: int,
    orphaned_max_age: int,
    retention_days: int,
    report_closed: ReportClosed | None = None,
) -> tuple[int, int, int]:
    """All three sweeps for one model: (unpicked, orphaned, deleted)."""
    return (
        mark_unpicked_runs_failed(model, unpicked_max_age, report_closed=report_closed),
        mark_orphaned_runs_failed(model, orphaned_max_age, report_closed=report_closed),
        delete_finished_records(model, retention_days),
    )
