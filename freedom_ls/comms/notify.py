from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from django.tasks import default_task_backend
from django.utils import timezone

from freedom_ls.base.notification_categories import FLS_NOTIFICATION_CATEGORIES
from freedom_ls.comms.config import config
from freedom_ls.comms.models import (
    Notification,
    get_notification_category,
    message_placeholders,
)
from freedom_ls.comms.tasks import deliver_notification

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet

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

    An FLS category the project has left out of NOTIFICATION_CATEGORIES is an
    opt-out, not an error: the call returns without writing anything.
    """
    configured_keys = {c.key for c in config.NOTIFICATION_CATEGORIES}
    fls_keys = {c.key for c in FLS_NOTIFICATION_CATEGORIES}
    if category not in configured_keys and category in fls_keys:
        return

    notification_category = get_notification_category(category)
    missing = message_placeholders(notification_category.message) - data.keys()
    if missing:
        raise ValueError(
            f"Notification data is missing {sorted(missing)} for {category!r}"
        )

    def create_and_enqueue(rollup_key: str | None) -> None:
        notification = Notification.objects.create(
            user=user,
            category=category,
            target=target,
            site_id=site_id,
            data=data,
            rollup_key=rollup_key,
        )
        for backend_path in config.NOTIFICATION_DELIVERY_BACKENDS:
            default_task_backend.enqueue(
                deliver_notification,
                args=[backend_path, str(notification.pk), site_id],
                kwargs={},
            )

    def update_unread_rollup(rollup_key: str) -> bool:
        # An update re-surfaces the row and re-lights the badge; it enqueues no delivery.
        return bool(
            Notification.objects.filter(
                user=user, site_id=site_id, rollup_key=rollup_key, read_at__isnull=True
            ).update(data=data, created_at=timezone.now(), seen_at=None)
        )

    def write() -> None:
        if not notification_category.rollup:
            create_and_enqueue(rollup_key=None)
            return
        rollup_key = f"{ContentType.objects.get_for_model(target).pk}:{target.pk}"
        if update_unread_rollup(rollup_key):
            return
        try:
            with transaction.atomic():
                create_and_enqueue(rollup_key=rollup_key)
        except IntegrityError:
            # A concurrent raise created the unread row first; this event folds into it.
            update_unread_rollup(rollup_key)

    transaction.on_commit(write, robust=True)


def stamp_read(queryset: QuerySet[Notification]) -> None:
    """The one place read implies seen: a row marked read and then unread must
    not come back onto the badge."""
    now = timezone.now()
    queryset.update(read_at=now, seen_at=Coalesce("seen_at", Value(now)))


def mark_notifications_read(
    *, user: User, target: Model, site_id: int, condition: Q | None = None
) -> None:
    """Mark the user's unread notifications about ``target`` read.

    ``condition`` narrows which rows are marked; it is applied in the same
    UPDATE, so a row that stops matching before the write is left alone.
    """
    stamp_read(
        Notification._base_manager.filter(
            condition or Q(),
            user=user,
            site_id=site_id,
            content_type=ContentType.objects.get_for_model(target),
            object_id=str(target.pk),
            read_at__isnull=True,
        )
    )
