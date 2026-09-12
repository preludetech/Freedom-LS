"""Delete referral code hits older than a cutoff, across every site.

Nothing trims the hit log on its own, so an operator runs this on whatever
schedule suits their retention policy. What one client can add to the log is
capped (see `REFERRAL_TRACKING_HIT_LOG_LIMIT`), but ordinary traffic still
grows it indefinitely.
"""

from __future__ import annotations

from datetime import timedelta

import djclick as click

from django.utils import timezone

from freedom_ls.referral_tracking.models import ReferralCodeHit

PRUNE_BATCH_SIZE = 1000


@click.command()
@click.option("--older-than-days", type=click.IntRange(min=1), required=True)
def command(older_than_days: int) -> None:
    """Delete referral code hits older than the cutoff, on every site."""
    cutoff = timezone.now() - timedelta(days=older_than_days)
    deleted = 0
    while True:
        batch = list(
            ReferralCodeHit._base_manager.filter(hit_at__lt=cutoff)
            .order_by("hit_at")
            .values_list("pk", flat=True)[:PRUNE_BATCH_SIZE]
        )
        if not batch:
            break
        deleted_count, _ = ReferralCodeHit._base_manager.filter(pk__in=batch).delete()
        deleted += deleted_count
    click.echo(
        f"Deleted {deleted} referral code hit(s) older than {older_than_days} day(s)."
    )
