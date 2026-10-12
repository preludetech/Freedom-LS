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
    from freedom_ls.base.notification_categories import (
        NotificationCategory,
        NotificationColour,
    )


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
    # On a rollup row this is when the row last changed, not when it was first written.
    created_at = models.DateTimeField(auto_now_add=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    # "<content type pk>:<target pk>" on a rollup category's row, null otherwise. Null,
    # not blank, because the unique constraint must skip rows that are not rollups.
    rollup_key = models.CharField(  # noqa: DJ001
        max_length=64, null=True, blank=True
    )

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
        constraints = [
            models.UniqueConstraint(
                fields=["user", "site", "rollup_key"],
                condition=Q(read_at__isnull=True, rollup_key__isnull=False),
                name="comms_notification_one_unread_rollup",
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
    def colour(self) -> NotificationColour | None:
        return get_notification_category(self.category).colour

    @property
    def url(self) -> str | None:
        builder = get_notification_category(self.category).url_builder
        if builder is None or self.target is None:
            return None
        return cast(str, import_string(builder)(self.target))


class Conversation(SiteAwareModel):
    """The one direct-message exchange between a pair of users on a site."""

    # "<low user pk>:<high user pk>", written only by get_or_create_conversation.
    pair_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "pair_key"], name="comms_conversation_pair_per_site"
            )
        ]

    def __str__(self) -> str:
        return f"Conversation {self.pair_key}"


class ConversationParticipant(SiteAwareModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_participants",
    )
    # The created_at of the newest message this participant was shown, never "now",
    # so a message that lands between render and mark stays unread.
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="comms_participant_once_per_conversation",
            )
        ]
        indexes = [
            models.Index(fields=["user", "site"], name="comms_part_user_site_idx")
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.conversation}"


class Message(SiteAwareModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    # Null once the sender's account is deleted; the text stays for the other
    # participant.
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Chosen by the composer per send, so a retried or double-clicked send is
    # recognised and stored once.
    client_key = models.UUIDField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "sender", "client_key"],
                condition=Q(client_key__isnull=False),
                name="comms_message_client_key_once",
            )
        ]
        indexes = [
            models.Index(
                fields=["conversation", "created_at", "id"],
                name="comms_message_cursor_idx",
            )
        ]

    def __str__(self) -> str:
        return f"Message in {self.conversation}"
