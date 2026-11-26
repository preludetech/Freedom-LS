"""The sweep that completes timed sittings nobody came back to, run by
`fls_run_housekeeping`.

It uses _base_manager, not the site-aware `objects`: housekeeping has no request
to derive a site from, and every site's sittings are in scope.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple

from django.db import DatabaseError, transaction
from django.db.models import DateTimeField, ExpressionWrapper, F, QuerySet, Value
from django.utils import timezone

from freedom_ls.form_engine.models import EXPIRY_GRACE, CompletionReason, FormProgress


class ExpiredSittingSweep(NamedTuple):
    completed: int
    failed: int


def _expired_sittings(now: datetime) -> QuerySet[FormProgress]:
    return (
        FormProgress._base_manager.filter(
            completed_time__isnull=True, form__time_limit_minutes__isnull=False
        )
        .annotate(
            expiry=ExpressionWrapper(
                F("start_time")
                + F("form__time_limit_minutes") * Value(timedelta(minutes=1)),
                output_field=DateTimeField(),
            )
        )
        # Past the grace window too: a page post may still be in flight inside it.
        .filter(expiry__lt=now - EXPIRY_GRACE)
    )


def complete_expired_sittings() -> ExpiredSittingSweep:
    """Complete every open sitting, on every site, whose time and grace window
    have both passed, with reason `time_expired`.

    Returns how many sittings were completed and how many failed. A failure is
    counted and the sweep carries on, so one malformed quiz cannot strand the
    rest.
    """
    completed = failed = 0
    now = timezone.now()
    # No lock here: each sitting is locked on its own below.
    pks = list(_expired_sittings(now).values_list("pk", flat=True))
    for pk in pks:
        try:
            with transaction.atomic():
                sitting = (
                    _expired_sittings(now)
                    .select_for_update(skip_locked=True, of=("self",))
                    .filter(pk=pk)
                    .first()
                )
                if sitting is None:
                    # Completed meanwhile, or a request holds it.
                    continue
                sitting.complete(reason=CompletionReason.TIME_EXPIRED)
                # complete() refreshes from the locked row, so a no-op leaves this
                # None.
                if sitting.completed_time is not None:
                    completed += 1
        except (DatabaseError, ValueError):  # ValueError: scoring a malformed quiz
            failed += 1
    return ExpiredSittingSweep(completed, failed)
