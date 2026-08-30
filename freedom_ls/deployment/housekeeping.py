"""Sweeps that keep the task queue and session table from growing without bound.

Runs once per invocation from `fls_run_housekeeping`; the downstream deploy
supplies the schedule (cron, a Kubernetes CronJob, or similar).
"""

from __future__ import annotations

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

    return HousekeepingOutcome(
        sweep_failures=sweep_failures, findings=findings, notes=notes
    )
