"""Writing attribution touches for signed-in users.

Every entry point is best-effort: a database failure is reported and the
caller carries on, because these writes ride on requests that must succeed.
"""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.sites.models import Site
from django.http import HttpRequest

from freedom_ls.referral_tracking.best_effort import best_effort_write
from freedom_ls.referral_tracking.capture import first_touch_from_request
from freedom_ls.referral_tracking.counters import (
    attribution_key_hash_of,
    attribution_key_values,
)
from freedom_ls.referral_tracking.models import (
    ATTRIBUTION_KEY_FIELDS,
    AttributionTouch,
    TouchSource,
)


def record_live_touch(
    *,
    request: HttpRequest,
    user: AbstractBaseUser,
    site: Site,
    occurred_at: datetime,
) -> AttributionTouch | None:
    """Write the touch for a signed-in user's tracked landing.

    Writes nothing when the landing carries no attribution-key value (a click id
    alone is not an attribution key) or when the user's latest touch on this
    site has the same key, so a refresh or a back-and-forth between two
    pages does not pile up identical rows. A third landing on a key the user
    has used before does write: the history records the order they arrived in.

    `site` is the request's resolved site, named explicitly and written through
    `_base_manager` so the row lands on that site whatever the ambient site
    context is.
    """
    landing = first_touch_from_request(request)
    if not any(attribution_key_values(landing)):
        return None
    key_hash = attribution_key_hash_of(landing)
    touch = None
    with best_effort_write():
        latest = (
            AttributionTouch._base_manager.filter(site=site, user_id=user.pk)
            .order_by("-occurred_at", "-recorded_at")
            .values_list("key_hash", flat=True)
            .first()
        )
        if latest == key_hash:
            return None
        touch = AttributionTouch._base_manager.create(
            site=site,
            user_id=user.pk,
            recorded_via=TouchSource.LIVE,
            occurred_at=occurred_at,
            key_hash=key_hash,
            landing_path=landing["landing_path"],
            **{name: landing[name] for name in ATTRIBUTION_KEY_FIELDS},
        )
    return touch
