"""Retention sweeps for referral tracking, run by `fls_run_housekeeping`.

Each sweep uses _base_manager, not the site-aware `objects`: housekeeping has no
request to derive a site from, and every site's rows are in scope.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db.models import QuerySet
from django.utils import timezone

from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import AttributionTouch, ReferralCodeHit

PRUNE_BATCH_SIZE = 1000


def _delete_in_batches(queryset: QuerySet, order_field: str) -> int:
    """Delete every row in `queryset`, oldest first, PRUNE_BATCH_SIZE at a time,
    so one run never holds a lock over the whole table. Returns how many rows
    were deleted."""
    deleted = 0
    while True:
        batch = list(
            queryset.order_by(order_field).values_list("pk", flat=True)[
                :PRUNE_BATCH_SIZE
            ]
        )
        if not batch:
            return deleted
        deleted_count, _ = queryset.model._base_manager.filter(pk__in=batch).delete()
        deleted += deleted_count


def _cutoff(days: int) -> datetime:
    return timezone.now() - timedelta(days=days)


def prune_attribution_touches() -> int:
    """Delete unreferenced attribution touches past retention, on every site.

    A touch that a conversion records as its first or last touch is kept however
    old it is: the conversion's foreign keys are `RESTRICT`, which is the
    guarantee, and the filter here only keeps the sweep from tripping over it.
    System check E003 keeps the retention at or above the attribution window, so
    a touch that can still count toward a future conversion is never deleted.

    Returns how many touches were deleted.
    """
    return _delete_in_batches(
        AttributionTouch._base_manager.filter(
            occurred_at__lt=_cutoff(config.REFERRAL_TRACKING_TOUCH_RETENTION_DAYS),
            conversions_as_first__isnull=True,
            conversions_as_last__isnull=True,
        ),
        "occurred_at",
    )


def prune_referral_code_hits() -> int:
    """Delete referral code hits past retention, on every site.

    What one client can add to the hit log is capped (see
    `REFERRAL_TRACKING_HIT_LOG_LIMIT`), but ordinary traffic still grows it
    indefinitely. A code's `hit_count` is kept as it is.

    Returns how many hits were deleted.
    """
    return _delete_in_batches(
        ReferralCodeHit._base_manager.filter(
            hit_at__lt=_cutoff(config.REFERRAL_TRACKING_HIT_RETENTION_DAYS)
        ),
        "hit_at",
    )
