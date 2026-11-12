"""System checks for the referral_tracking app.

E001 — REFERRAL_TRACKING_INACTIVE_DESTINATION is not a site path.
W001 — REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS is shorter than the cookie's life.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error, Warning, register
from django.core.exceptions import ValidationError


@register()
def check_inactive_destination(**kwargs: object) -> list[CheckMessage]:
    from freedom_ls.referral_tracking.codes import validate_site_path
    from freedom_ls.referral_tracking.config import config

    try:
        validate_site_path(config.REFERRAL_TRACKING_INACTIVE_DESTINATION)
    except ValidationError as exc:
        return [
            Error(
                f"REFERRAL_TRACKING_INACTIVE_DESTINATION is not a site path: {exc.messages[0]}",
                hint="Set it to a path on this site, such as '/'.",
                id="freedom_ls_referral_tracking.E001",
            )
        ]
    return []


@register()
def check_attribution_window(**kwargs: object) -> list[CheckMessage]:
    from freedom_ls.referral_tracking.config import config

    window = config.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS
    cookie_days = config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS
    if window < cookie_days:
        return [
            Warning(
                f"REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS ({window}) is shorter "
                f"than REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS ({cookie_days}).",
                hint=(
                    "A touch flushed from the cookie near the end of its life can "
                    "already be outside the window. Raise the window to at least "
                    "the cookie's life."
                ),
                id="freedom_ls_referral_tracking.W001",
            )
        ]
    return []
