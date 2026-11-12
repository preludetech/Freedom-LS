"""Finding the touches in play for a conversion."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.contrib.sites.models import Site

from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import AttributionTouch
from freedom_ls.site_aware_models.models import SiteAwareModelBase


def touches_in_play(
    *, user: SiteAwareModelBase, site: Site, when: datetime
) -> tuple[AttributionTouch | None, AttributionTouch | None]:
    """Return the user's earliest and latest coded touches within the window ending at `when`.

    Only touches carrying a referral code count: a UTM-only touch never
    displaces a code. `site` is named explicitly and read through
    `_base_manager`, so a shell script or background job can call this with
    no request and no ambient site context.
    """
    window = timedelta(days=config.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS)
    coded = AttributionTouch._base_manager.filter(
        site=site,
        user_id=user.pk,
        occurred_at__gte=when - window,
        occurred_at__lte=when,
    ).exclude(referral_code="")
    return (
        coded.order_by("occurred_at", "recorded_at").first(),
        coded.order_by("-occurred_at", "-recorded_at").first(),
    )
