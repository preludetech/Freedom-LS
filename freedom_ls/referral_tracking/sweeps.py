"""Retention sweeps for referral tracking, run by `fls_run_housekeeping`."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import AttributionTouch

PRUNE_BATCH_SIZE = 1000


def prune_attribution_touches() -> int:
    """Delete unreferenced attribution touches past retention, on every site.

    A touch that a conversion records as its first or last touch is kept however
    old it is: the conversion's foreign keys are `RESTRICT`, which is the
    guarantee, and the filter here only keeps the sweep from tripping over it.
    System check E003 keeps the retention at or above the attribution window, so
    a touch that can still count toward a future conversion is never deleted.

    _base_manager, not the site-aware `objects`: housekeeping has no request to
    derive a site from, and every site's rows are in scope.

    Returns how many touches were deleted.
    """
    cutoff = timezone.now() - timedelta(
        days=config.REFERRAL_TRACKING_TOUCH_RETENTION_DAYS
    )
    deleted = 0
    while True:
        batch = list(
            AttributionTouch._base_manager.filter(
                occurred_at__lt=cutoff,
                conversions_as_first__isnull=True,
                conversions_as_last__isnull=True,
            )
            .order_by("occurred_at")
            .values_list("pk", flat=True)[:PRUNE_BATCH_SIZE]
        )
        if not batch:
            return deleted
        deleted_count, _ = AttributionTouch._base_manager.filter(pk__in=batch).delete()
        deleted += deleted_count
