from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils.module_loading import import_string

from freedom_ls.comms.config import config
from freedom_ls.site_aware_models.models import SiteAwareManager, SiteAwareModel

if TYPE_CHECKING:
    from django_stubs_ext import StrPromise

    from freedom_ls.accounts.models import User
    from freedom_ls.base.notification_categories import NotificationCategory


def get_notification_category(key: str) -> NotificationCategory:
    for category in config.NOTIFICATION_CATEGORIES:
        if category.key == key:
            return category
    raise ValueError(f"Unknown notification category: {key!r}")


def message_placeholders(message: StrPromise) -> set[str]:
    return set(re.findall(r"%\((\w+)\)s", str(message)))


class NotificationQuerySet(models.QuerySet["Notification"]):
    def for_user(self, user: User) -> NotificationQuerySet:
        return self.filter(user=user)

    def unread(self) -> NotificationQuerySet:
        return self.filter(read_at__isnull=True)

    def unseen(self) -> NotificationQuerySet:
        return self.unread().filter(seen_at__isnull=True)


class NotificationManager(SiteAwareManager):
    """A SiteAwareManager backed by NotificationQuerySet, with categories a
    project has since dropped excluded from every surface and the badge.

    That exclusion lives here, not on each caller, so a project that drops a
    category doesn't have to remember to filter it out of the badge, the panel
    and the centre separately.

    This would ordinarily be spelled ``SiteAwareManager.from_queryset(
    NotificationQuerySet)``, but that dynamic base class isn't one this
    project's mypy setup can resolve, so _queryset_class and the three
    pass-through methods below spell out by hand what from_queryset() would
    have generated. get_queryset() is deliberately left without a return
    annotation, matching SiteAwareManager's own: Manager.get_queryset()'s
    declared return type is generic in the model's own manager, not
    NotificationQuerySet, so annotating an override here would conflict with it.
    """

    _queryset_class = NotificationQuerySet

    def get_queryset(self):
        keys = [category.key for category in config.NOTIFICATION_CATEGORIES]
        queryset = cast("NotificationQuerySet", super().get_queryset())
        return queryset.filter(category__in=keys)

    def for_user(self, user: User) -> NotificationQuerySet:
        return cast("NotificationQuerySet", self.get_queryset()).for_user(user)

    def unread(self) -> NotificationQuerySet:
        return cast("NotificationQuerySet", self.get_queryset()).unread()

    def unseen(self) -> NotificationQuerySet:
        return cast("NotificationQuerySet", self.get_queryset()).unseen()


class Notification(SiteAwareModel):
    """One stored message to one user on one site about something that happened
    to them."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    category = models.CharField(max_length=100)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # Open-set, like ObjectRoleAssignment.object_id (docs/app_conventions.md): a
    # downstream project can add categories whose targets aren't UUID-keyed.
    object_id = models.CharField(max_length=255)
    target = GenericForeignKey("content_type", "object_id")
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationManager()

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["user", "site", "-created_at"]),
            models.Index(
                fields=["user", "site"],
                name="comms_notification_unseen_idx",
                condition=Q(read_at__isnull=True, seen_at__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.category} notification for {self.user}"

    @property
    def message(self) -> str:
        return cast(
            str, str(get_notification_category(self.category).message) % self.data
        )

    @property
    def label(self) -> str:
        return str(get_notification_category(self.category).label)

    @property
    def icon(self) -> str:
        return get_notification_category(self.category).icon

    @property
    def url(self) -> str | None:
        builder = get_notification_category(self.category).url_builder
        if builder is None or self.target is None:
            return None
        return cast(str, import_string(builder)(self.target))
