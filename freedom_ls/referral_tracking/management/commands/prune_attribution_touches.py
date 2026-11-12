"""Delete attribution touches older than a cutoff, across every site.

Nothing trims the touch log on its own, so an operator runs this on whatever
schedule suits their retention policy. A touch that a conversion records as its
first or last touch is kept however old it is: the conversion's foreign keys are
`RESTRICT`, which is the guarantee, and the filter here only keeps the command
from tripping over it.
"""

from __future__ import annotations

from datetime import timedelta

import djclick as click

from django.utils import timezone

from freedom_ls.referral_tracking.models import AttributionTouch

PRUNE_BATCH_SIZE = 1000


@click.command()
@click.option("--older-than-days", type=click.IntRange(min=1), required=True)
def command(older_than_days: int) -> None:
    """Delete unreferenced attribution touches older than the cutoff, on every site."""
    cutoff = timezone.now() - timedelta(days=older_than_days)
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
            break
        deleted_count, _ = AttributionTouch._base_manager.filter(pk__in=batch).delete()
        deleted += deleted_count
    click.echo(
        f"Deleted {deleted} attribution touch(es) older than {older_than_days} day(s)."
    )
