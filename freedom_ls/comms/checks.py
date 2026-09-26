"""Django system checks for the comms app.

E001 — Two registered notification categories share a key.
E002 — a NOTIFICATION_DELIVERY_BACKENDS path that doesn't import (added in a later
       slice, alongside the delivery seam itself).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, register

from freedom_ls.comms.config import config


@register()
def check_notification_category_keys_are_unique(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    keys = [category.key for category in config.NOTIFICATION_CATEGORIES]
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if not duplicates:
        return []

    return [
        Error(
            f"NOTIFICATION_CATEGORIES has duplicate keys: {duplicates}.",
            hint="Each notification category's key must be unique.",
            id="freedom_ls_comms.E001",
        )
    ]
