"""System checks for the referral_tracking app.

E001 — REFERRAL_TRACKING_INACTIVE_DESTINATION is not a site path.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error, register
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
