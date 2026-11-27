"""The sweep that completes timed sittings nobody came back to, run by
`fls_run_housekeeping`.

It uses _base_manager, not the site-aware `objects`: housekeeping has no request
to derive a site from, and every site's sittings are in scope.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple

import sentry_sdk

from django.db.models import DateTimeField, ExpressionWrapper, F, QuerySet, Value
from django.utils import timezone

from freedom_ls.form_engine.models import EXPIRY_GRACE, FormProgress


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
    reported, counted and the sweep carries on, so one malformed quiz cannot
    strand the rest.
    """
    completed = failed = 0
    now = timezone.now()
    sittings = _expired_sittings(now).select_related("form")
    for sitting in sittings:
        try:
            # No lock or transaction of the sweep's own. complete() locks the
            # sitting, checks again that it is open and expired, and releases the
            # lock before its receivers write the course progress record. A
            # request locks that record first and the sitting second, so holding
            # the sitting across the receivers would deadlock against it.
            if sitting.complete_if_expired(timezone.now()):
                completed += 1
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            failed += 1
    return ExpiredSittingSweep(completed, failed)
