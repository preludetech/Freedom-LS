from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from freedom_ls.comms.models import (
    Notification,
    get_notification_category,
    message_placeholders,
)

if TYPE_CHECKING:
    from django.db.models import Model

    from freedom_ls.accounts.models import User


def raise_notification(
    *,
    user: User,
    category: str,
    target: Model,
    site_id: int,
    data: dict[str, str],
) -> None:
    """Raise a notification for a user about something that happened to them.

    Validates the category and data against the registry synchronously, in the
    caller, so a programming error (unknown category, missing placeholder) is
    never silently swallowed. The row itself is written from
    transaction.on_commit(..., robust=True), so a caller's own transaction never
    sees a notification for work that was rolled back, and a failure writing the
    row can't affect the caller's own response.
    """
    notification_category = get_notification_category(category)
    missing = message_placeholders(notification_category.message) - data.keys()
    if missing:
        raise ValueError(
            f"Notification data is missing {sorted(missing)} for {category!r}"
        )

    def write() -> None:
        Notification.objects.create(
            user=user, category=category, target=target, site_id=site_id, data=data
        )

    transaction.on_commit(write, robust=True)
