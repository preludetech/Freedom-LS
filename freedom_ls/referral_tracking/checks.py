"""System checks for the referral_tracking app.

E001 — REFERRAL_TRACKING_INACTIVE_DESTINATION is not a site path.
W001 — REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS is shorter than the cookie's life.
E002 — REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS is too large for `Conversion.window_days`.
E003 — REFERRAL_TRACKING_TOUCH_RETENTION_DAYS is shorter than the attribution window.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error, Warning, register
from django.core.exceptions import ValidationError
from django.db import connection


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
    from freedom_ls.referral_tracking.models import Conversion

    window = config.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS
    cookie_days = config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS
    field = Conversion._meta.get_field("window_days")
    _, largest = connection.ops.integer_field_range(field.get_internal_type())
    if largest is not None and window > largest:
        # Every conversion insert would fail, and the best-effort write
        # around it would swallow the error.
        return [
            Error(
                f"REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS ({window}) is larger "
                f"than Conversion.window_days can store ({largest}).",
                hint=f"Set it to {largest} days or fewer.",
                id="freedom_ls_referral_tracking.E002",
            )
        ]
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


@register()
def check_touch_retention(**kwargs: object) -> list[CheckMessage]:
    from freedom_ls.referral_tracking.config import config

    retention = config.REFERRAL_TRACKING_TOUCH_RETENTION_DAYS
    window = config.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS
    if retention < window:
        # Housekeeping would delete touches a conversion that has not happened
        # yet could still credit, and that conversion would record no codes.
        return [
            Error(
                f"REFERRAL_TRACKING_TOUCH_RETENTION_DAYS ({retention}) is shorter "
                f"than REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS ({window}).",
                hint=f"Set it to {window} days or more.",
                id="freedom_ls_referral_tracking.E003",
            )
        ]
    return []
