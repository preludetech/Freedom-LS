"""The daily first-touch tally and the attribution-key digest it is keyed on."""

from __future__ import annotations

import hashlib
from datetime import date

from django.contrib.sites.models import Site
from django.db import IntegrityError, transaction
from django.db.models import F

from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import FirstTouchCount

KEY_SEPARATOR = "\x1f"
OVERFLOW_SENTINEL = "\x00overflow"


def attribution_key_hash(*values: str) -> str:
    return hashlib.sha256(KEY_SEPARATOR.join(values).encode("utf-8")).hexdigest()


def increment_first_touch(
    *,
    site: Site,
    day: date,
    key_hash: str,
    is_overflow: bool = False,
    **key_fields: str,
) -> None:
    """Increment the row for one attribution key, minting it on first sight.

    Once a site's daily key count reaches the cap, a key that hasn't been
    seen yet today folds into the overflow row instead of minting its own,
    so the table's daily row count stays bounded regardless of how many
    distinct campaigns get thrown at it.

    The overflow row exists only once the cap has been reached, so its
    presence is the cap signal. A novel key is tried against it before the
    count runs, which keeps a capped-out day — the path anyone can drive
    with random query strings — to two UPDATEs and no COUNT.
    """
    updated = FirstTouchCount.objects.filter(
        site=site, day=day, key_hash=key_hash
    ).update(count=F("count") + 1)
    if updated:
        return
    if not is_overflow:
        overflow_hash = attribution_key_hash(OVERFLOW_SENTINEL)
        folded = FirstTouchCount.objects.filter(
            site=site, day=day, key_hash=overflow_hash
        ).update(count=F("count") + 1)
        if folded:
            return
        if (
            FirstTouchCount.objects.filter(
                site=site, day=day, is_overflow=False
            ).count()
            >= config.REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP
        ):
            create_or_increment_first_touch(
                site=site, day=day, key_hash=overflow_hash, is_overflow=True
            )
            return
    create_or_increment_first_touch(
        site=site, day=day, key_hash=key_hash, is_overflow=is_overflow, **key_fields
    )


def create_or_increment_first_touch(
    *, site: Site, day: date, key_hash: str, is_overflow: bool, **key_fields: str
) -> None:
    """Create the row, or increment it if another request created it first.

    Two requests can both reach here for the same brand-new key: the
    `update()` above missed for both, so each tries to mint. Whichever loses
    the race hits the unique constraint on `(site, day, key_hash)`, and
    falls back to incrementing the row the winner just created. The nested
    `transaction.atomic()` scopes that failed `INSERT` to its own savepoint —
    without it, Postgres marks the whole outer transaction unusable and the
    fallback `update()` would raise `TransactionManagementError` instead of
    recovering.
    """
    try:
        with transaction.atomic():
            FirstTouchCount.objects.create(
                site=site,
                day=day,
                key_hash=key_hash,
                is_overflow=is_overflow,
                count=1,
                **key_fields,
            )
    except IntegrityError:
        FirstTouchCount.objects.filter(site=site, day=day, key_hash=key_hash).update(
            count=F("count") + 1
        )
