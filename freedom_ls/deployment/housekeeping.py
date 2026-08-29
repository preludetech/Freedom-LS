"""Sweeps that keep the task queue and session table from growing without bound.

Runs once per invocation from `fls_run_housekeeping`; the downstream deploy
supplies the schedule (cron, a Kubernetes CronJob, or similar).
"""

from __future__ import annotations

from datetime import timedelta

import sentry_sdk
from django_tasks import TaskResultStatus
from django_tasks_db.models import DBTaskResult, get_date_max

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.db.models import Q, QuerySet
from django.utils import timezone

from freedom_ls.deployment.config import config


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


# The two ways a sweep can fail without being a bug in this command: the command
# it delegates to reports failure, or the database refuses the work. Anything else
# is a bug and propagates, where the management-command machinery turns it into a
# traceback and Sentry's own excepthook integration reports it.
SWEEP_FAILURES = (CommandError, DatabaseError)


def run_housekeeping_sweeps() -> list[str]:
    """Run both sweeps and the late-task check. Return a list of failure messages.

    Each step gets its own try/except so no failure stops a later step: a prune that
    dies must still leave expired sessions cleared, and both must still leave the
    late-task check run.
    """
    failures: list[str] = []

    try:
        call_command("prune_db_task_results", queue_name="*")
    except SWEEP_FAILURES as exc:
        sentry_sdk.capture_exception(exc)
        failures.append(f"prune_db_task_results failed: {exc}")

    try:
        call_command("clearsessions")
    except SWEEP_FAILURES as exc:
        sentry_sdk.capture_exception(exc)
        failures.append(f"clearsessions failed: {exc}")

    try:
        late_count = find_late_unpicked_tasks(
            config.HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS
        ).count()
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
        failures.append(f"late unpicked task check failed: {exc}")
    else:
        if late_count:
            sentry_sdk.capture_message(
                f"{late_count} READY task result(s) unpicked for more than "
                f"{config.HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS}s; "
                f"no worker is consuming."
            )
            failures.append(f"{late_count} task result(s) unpicked past the window.")

    return failures
