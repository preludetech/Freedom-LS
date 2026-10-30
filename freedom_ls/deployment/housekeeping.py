"""Sweeps that keep the task queue and session table from growing without bound,
and that close rows a dead worker left open behind it.

Runs once per invocation from `fls_run_housekeeping`; the downstream deploy
supplies the schedule (cron, a Kubernetes CronJob, or similar).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import NamedTuple

import sentry_sdk
from django_tasks import TaskResultStatus
from django_tasks_db.models import DBTaskResult, get_date_max

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.db.models import Q, QuerySet
from django.utils import timezone

from freedom_ls.deployment.config import config
from freedom_ls.learner_management.config import config as learner_management_config
from freedom_ls.learner_management.models import ImportStatus, LearnerImport
from freedom_ls.panel_framework.bulk_runs import report_finished
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.reports.models import GeneratedReport


class OrphanedTaskError(RuntimeError):
    """Recorded on a task result housekeeping closed on the task's behalf.

    Never raised. DBTaskResult.set_failed needs an exception instance to record,
    and the class path it stores is what tells an operator the row was closed by
    this sweep rather than by the task's own code.
    """


class OrphanReapResult(NamedTuple):
    """How the orphan sweep went: rows closed, and rows the database would not close."""

    marked_failed: int
    left_running: int


class HousekeepingOutcome(NamedTuple):
    """What one run did, split by who has to act on it.

    sweep_failures are housekeeping's own work not getting done. findings are that
    work getting done and turning up something wrong outside this container. notes
    are what the run put right by itself. Only sweep_failures withhold the
    heartbeat; sweep_failures and findings both force a non-zero exit; notes force
    nothing.

    A populated NamedTuple is always truthy, so callers test a named field rather
    than the outcome itself.
    """

    sweep_failures: list[str]
    findings: list[str]
    notes: list[str]

    def failure_message(self) -> str:
        """The CommandError text, labelled so the two exit causes stay apart.

        Seeing "Sweep failures:" means this container's own probe goes red; seeing
        only "Findings:" means housekeeping is healthy and reporting on the worker.
        """
        parts: list[str] = []
        if self.sweep_failures:
            parts.append("Sweep failures: " + "; ".join(self.sweep_failures))
        if self.findings:
            parts.append("Findings: " + "; ".join(self.findings))
        return " ".join(parts)


def find_late_unpicked_tasks(max_age_seconds: int) -> QuerySet[DBTaskResult]:
    """READY task results that were due more than max_age_seconds ago.

    run_after is non-nullable and carries the sentinel get_date_max() (year 9999)
    for a task enqueued with no schedule, so lateness is measured from enqueued_at
    on that branch and from run_after on the other. A future run_after never
    satisfies run_after__lte=cutoff, so "not yet due is not late" needs no special
    case. Every queue, no scoping.
    """
    cutoff = timezone.now() - timedelta(seconds=max_age_seconds)
    return DBTaskResult.objects.filter(status=TaskResultStatus.READY).filter(
        Q(run_after=get_date_max(), enqueued_at__lte=cutoff)
        | Q(run_after__lt=get_date_max(), run_after__lte=cutoff)
    )


def find_orphaned_running_tasks(max_age_seconds: int) -> QuerySet[DBTaskResult]:
    """RUNNING task results claimed more than max_age_seconds ago.

    claim() is the only writer of started_at and sets RUNNING in the same save, so
    started_at is how long a worker has held the row; there is no last_attempted_at
    column to consult. A NULL started_at never satisfies the comparison, which is
    the right answer for a row no worker ever claimed. Every queue, no scoping.
    """
    cutoff = timezone.now() - timedelta(seconds=max_age_seconds)
    return DBTaskResult.objects.running().filter(started_at__lte=cutoff)


def mark_orphaned_running_tasks_failed(max_age_seconds: int) -> OrphanReapResult:
    """Close every orphaned RUNNING row as FAILED. Bookkeeping, not recovery.

    The task is never run again and never requeued. The row records that the task
    started, not how far it got, so a task killed between sending an email and
    recording that it sent one would send it twice. Closing the row says the true
    thing and makes the row prunable, and the Sentry issue beside it puts a person
    in front of the decision the automation cannot make.
    """
    # Materialised before the loop starts changing the status the query filters on.
    orphans = list(find_orphaned_running_tasks(max_age_seconds))
    marked_failed = 0
    left_running = 0

    for task_result in orphans:
        workers = ", ".join(str(worker_id) for worker_id in task_result.worker_ids)
        try:
            task_result.set_failed(
                OrphanedTaskError(
                    f"Claimed at {task_result.started_at} by worker(s) "
                    f"{workers or 'unknown'} and still running {max_age_seconds}s "
                    f"later, so the worker holding it died without finishing it. "
                    f"fls_run_housekeeping marked this row failed to say so. The "
                    f"task was not run again and was not requeued; whether the work "
                    f"still needs doing is an operator's call."
                )
            )
        except DatabaseError as exc:
            sentry_sdk.capture_exception(exc)
            left_running += 1
        else:
            marked_failed += 1
            # The task path alone is the message, so Sentry groups a task that dies
            # its worker every night into one recurring issue. Everything that
            # varies per row rides on the scope instead.
            with sentry_sdk.new_scope() as scope:
                scope.set_extra("task_result_id", str(task_result.id))
                scope.set_extra("started_at", str(task_result.started_at))
                scope.set_extra("worker_ids", task_result.worker_ids)
                sentry_sdk.capture_message(
                    f"Task {task_result.task_path} was orphaned in RUNNING and has "
                    f"been marked failed. It was not retried."
                )

    return OrphanReapResult(marked_failed=marked_failed, left_running=left_running)


def find_orphaned_running_reports(max_age_seconds: int) -> QuerySet[GeneratedReport]:
    """Cohort reports that have been RUNNING longer than the given window.

    started_at is written once, by generate_cohort_report, in the same save that
    sets RUNNING, so it is how long the render has been in flight. A row still
    PENDING has no started_at and never satisfies the comparison, which is right:
    nothing has claimed it yet.

    _base_manager, not the site-aware `objects`: housekeeping runs from a
    management command with no request to derive a site from, and every site's rows
    are in scope.
    """
    cutoff = timezone.now() - timedelta(seconds=max_age_seconds)
    return GeneratedReport._base_manager.filter(
        status=GeneratedReport.STATUS_RUNNING, started_at__lte=cutoff
    )


def mark_orphaned_running_reports_failed(max_age_seconds: int) -> OrphanReapResult:
    """Close every orphaned RUNNING report as FAILED. Bookkeeping, not recovery.

    The render is never retried. What makes this worth sweeping is the partial
    unique index on the model: while the row sits in RUNNING it *is* the one
    in-flight report that cohort is allowed, so leaving it there blocks that cohort
    from ever asking for another. Closing it says the render did not finish and
    hands the cohort back.

    Nothing was written to storage on this path, so there is no file to clean up.
    """
    # Materialised before the loop starts changing the status the query filters on.
    orphans = list(find_orphaned_running_reports(max_age_seconds))
    marked_failed = 0
    left_running = 0

    for report in orphans:
        report.status = GeneratedReport.STATUS_FAILED
        report.error_message = (
            f"Started at {report.started_at} and still rendering "
            f"{max_age_seconds}s later, so the worker rendering it died without "
            f"finishing. fls_run_housekeeping marked this report failed to say so. "
            f"The report was not re-rendered; ask for it again to retry."
        )
        report.finished_at = timezone.now()
        try:
            report.save(update_fields=["status", "error_message", "finished_at"])
        except DatabaseError as exc:
            sentry_sdk.capture_exception(exc)
            left_running += 1
        else:
            marked_failed += 1
            # A constant message, so every stranded report groups into one
            # recurring Sentry issue. What varies per row rides on the scope.
            with sentry_sdk.new_scope() as scope:
                scope.set_extra("report_id", str(report.id))
                scope.set_extra("cohort_id", str(report.cohort_id))
                scope.set_extra("site_id", str(report.site_id))
                scope.set_extra("started_at", str(report.started_at))
                sentry_sdk.capture_message(
                    "A cohort report was orphaned in RUNNING and has been marked "
                    "failed. It was not re-rendered."
                )

    return OrphanReapResult(marked_failed=marked_failed, left_running=left_running)


# Learner imports and bulk action runs share the lifecycle fields the sweeps use
# (status, created_at, started_at, finished_at, error_message), so each sweep is
# written once and takes the model class.
type BulkRecordModel = type[BulkActionRun] | type[LearnerImport]

BULK_RECORD_MODELS: tuple[BulkRecordModel, ...] = (BulkActionRun, LearnerImport)

STALE_PREVIEW_MAX_AGE = timedelta(hours=24)


def delete_stale_previews() -> int:
    """Delete learner imports left in PREVIEWED for 24 hours, and their rows.

    A preview is only a stage before the reader confirms; one nobody confirmed
    holds nothing worth keeping. Runs have no preview stage, so only imports are
    swept.

    _base_manager, not the site-aware `objects`: housekeeping has no request to
    derive a site from, and every site's rows are in scope.
    """
    cutoff = timezone.now() - STALE_PREVIEW_MAX_AGE
    _, deleted_per_model = LearnerImport._base_manager.filter(
        status=ImportStatus.PREVIEWED, created_at__lte=cutoff
    ).delete()
    return deleted_per_model.get(LearnerImport._meta.label, 0)


def _close_as_failed(
    model: BulkRecordModel, records: QuerySet, error_message: str
) -> int:
    """Close every record in `records` as FAILED, at the current time, and
    tell a bulk action run's action, which a bare update would skip and
    which is how the requester hears about a run they are no longer
    watching. Returns how many rows were closed."""
    closed = list(records.values_list("pk", "site_id"))
    if not closed:
        return 0
    records.filter(pk__in=[pk for pk, _ in closed]).update(
        status=RunStatus.FAILED, error_message=error_message, finished_at=timezone.now()
    )
    if model is BulkActionRun:
        for pk, site_id in closed:
            report_finished(str(pk), site_id)
    return len(closed)


def mark_unpicked_runs_failed(model: BulkRecordModel, max_age_seconds: int) -> int:
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
        f"The background task was never picked up within {max_age_seconds}s "
        f"of being queued, so no worker is consuming. fls_run_housekeeping "
        f"marked this record failed to say so. Start the action again.",
    )


def mark_orphaned_runs_failed(model: BulkRecordModel, max_age_seconds: int) -> int:
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
        f"Still running {max_age_seconds}s after it started, so the worker "
        f"running it died without finishing. fls_run_housekeeping marked this "
        f"record failed to say so. The work was not run again; check what was "
        f"applied before starting it again.",
    )


def delete_finished_records(model: BulkRecordModel, days: int) -> int:
    """Delete records that finished more than `days` days ago.

    Records closed by the sweeps above carry a finished_at like any other
    terminal record, so they are deleted here in their turn. A record that has
    not finished has a NULL finished_at and is never matched.
    Returns how many rows were deleted.
    """
    cutoff = timezone.now() - timedelta(days=days)
    _, deleted_per_model = model._base_manager.filter(finished_at__lte=cutoff).delete()
    return deleted_per_model.get(model._meta.label, 0)


# The two ways a sweep can fail without being a bug in this command: the command
# it delegates to reports failure, or the database refuses the work. Anything else
# is a bug and propagates, where the management-command machinery turns it into a
# traceback and Sentry's own excepthook integration reports it.
SWEEP_FAILURES = (CommandError, DatabaseError)


def run_housekeeping_sweeps() -> HousekeepingOutcome:
    """Run both sweeps, the late-task check and the orphan reap.

    Each step gets its own try/except so no failure stops a later step: a prune that
    dies must still leave expired sessions cleared, and both must still leave the
    late-task check run.
    """
    sweep_failures: list[str] = []
    findings: list[str] = []
    notes: list[str] = []

    try:
        call_command("prune_db_task_results", queue_name="*")
    except SWEEP_FAILURES as exc:
        sentry_sdk.capture_exception(exc)
        sweep_failures.append(f"prune_db_task_results failed: {exc}")

    try:
        call_command("clearsessions")
    except SWEEP_FAILURES as exc:
        sentry_sdk.capture_exception(exc)
        sweep_failures.append(f"clearsessions failed: {exc}")

    try:
        late_count = find_late_unpicked_tasks(
            config.HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS
        ).count()
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
        sweep_failures.append(f"late unpicked task check failed: {exc}")
    else:
        if late_count:
            sentry_sdk.capture_message(
                f"{late_count} READY task result(s) unpicked for more than "
                f"{config.HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS}s; "
                f"no worker is consuming."
            )
            findings.append(f"{late_count} task result(s) unpicked past the window.")

    # Last of the four, because either order is safe and this one keeps the diff
    # additive. The prune deletes finished rows older than its fourteen-day default
    # and a row closed here has finished_at of now, so the same run's prune cannot
    # delete the evidence. A prune given --min-age-days=0 could.
    try:
        reaped = mark_orphaned_running_tasks_failed(
            config.HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS
        )
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
        sweep_failures.append(f"orphaned task sweep failed: {exc}")
    else:
        if reaped.marked_failed:
            # The sweep worked, so this fails nothing. What it found is an
            # application failure and it reaches the operator through Sentry.
            notes.append(
                f"Closed {reaped.marked_failed} task result(s) orphaned in RUNNING."
            )
        if reaped.left_running:
            sweep_failures.append(
                f"{reaped.left_running} orphaned task result(s) could not be closed "
                f"and are still RUNNING."
            )

    # Last, on the same reasoning as the sweep above. Closing the task row does not
    # close the report row: they are separate tables, and the report is the one a
    # cohort's next request is blocked behind.
    try:
        reaped_reports = mark_orphaned_running_reports_failed(
            config.HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS
        )
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
        sweep_failures.append(f"orphaned report sweep failed: {exc}")
    else:
        if reaped_reports.marked_failed:
            notes.append(
                f"Closed {reaped_reports.marked_failed} cohort report(s) orphaned "
                f"in RUNNING."
            )
        if reaped_reports.left_running:
            sweep_failures.append(
                f"{reaped_reports.left_running} orphaned cohort report(s) could not "
                f"be closed and are still RUNNING."
            )

    try:
        previews_deleted = delete_stale_previews()
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
        sweep_failures.append(f"stale import preview sweep failed: {exc}")
    else:
        if previews_deleted:
            notes.append(f"Deleted {previews_deleted} unconfirmed learner import(s).")

    # One try per sweep and model, so a failure on one table leaves the rest run.
    bulk_sweeps: tuple[tuple[str, str, Callable[[BulkRecordModel], int]], ...] = (
        (
            "unpicked bulk record sweep",
            "Closed {count} {name}(s) never picked up by a worker.",
            lambda model: mark_unpicked_runs_failed(
                model, config.HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS
            ),
        ),
        (
            "orphaned bulk record sweep",
            "Closed {count} {name}(s) orphaned in RUNNING.",
            lambda model: mark_orphaned_runs_failed(
                model, config.HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS
            ),
        ),
        (
            "finished bulk record sweep",
            "Deleted {count} finished {name}(s) past retention.",
            lambda model: delete_finished_records(
                model, learner_management_config.BULK_RECORD_RETENTION_DAYS
            ),
        ),
    )
    for failure_label, note_template, sweep in bulk_sweeps:
        for model in BULK_RECORD_MODELS:
            try:
                count = sweep(model)
            except DatabaseError as exc:
                sentry_sdk.capture_exception(exc)
                sweep_failures.append(
                    f"{failure_label} failed for {model._meta.label}: {exc}"
                )
            else:
                if count:
                    notes.append(
                        note_template.format(count=count, name=model._meta.verbose_name)
                    )

    return HousekeepingOutcome(
        sweep_failures=sweep_failures, findings=findings, notes=notes
    )
