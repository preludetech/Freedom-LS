"""Immutable xAPI event storage.

Two models live here: ``Event`` (the append-only event log) and
``ActorErasure`` (the append-only audit trail of erasure operations).

Both are append-only at four layers of defence:

1. Python :py:meth:`Event.save` override refuses to mutate an existing row and
   refuses to create a new row unless the ``_tracker_authorised`` flag is set.
2. Python :py:meth:`Event.delete` override raises.
3. Python manager / queryset override: ``Event.objects.update()`` and
   ``Event.objects.filter(...).delete()`` raise.
4. A :class:`django.db.models.signals.pre_save` signal mirrors rules 1 and 2 — a
   defence-in-depth guard against someone calling ``super().save()`` directly.

In addition, migration 0002 revokes ``UPDATE`` and ``DELETE`` at the DB level
from the application role, so even a bug or a malicious call path cannot
mutate already-persisted rows. The narrowly-scoped erasure flow uses a
separate DB role (``fls_erasure_role``) and a raw parameterised ``UPDATE``
through that connection.
"""

from __future__ import annotations

import contextlib

from django.conf import settings
from django.contrib.postgres.indexes import BrinIndex, GinIndex
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from freedom_ls.site_aware_models.models import SiteAwareManager, SiteAwareModel

from .exceptions import EventImmutableError


class _AppendOnlyQuerySet(models.QuerySet):
    """Queryset that refuses ``update()`` / ``delete()`` at the ORM level."""

    def update(self, *args, **kwargs):
        raise EventImmutableError("Bulk update on append-only tables is forbidden.")

    def delete(self, *args, **kwargs):
        raise EventImmutableError("Bulk delete on append-only tables is forbidden.")


class _AppendOnlyManager(SiteAwareManager):
    """Manager that returns an :class:`_AppendOnlyQuerySet`."""

    def get_queryset(self) -> models.QuerySet:
        request = getattr(_thread_locals_module_ref(), "request", None)
        qs: models.QuerySet = _AppendOnlyQuerySet(self.model, using=self._db)
        if request:
            from freedom_ls.site_aware_models.models import get_cached_site

            site = get_cached_site(request)
            qs = qs.filter(site=site)
        return qs


def _thread_locals_module_ref():
    """Return the module-level ``_thread_locals`` object.

    Indirection exists so the manager can lazily import from
    ``site_aware_models`` without triggering Django's app-loading ordering
    issues at module-import time.
    """
    from freedom_ls.site_aware_models.models import _thread_locals

    return _thread_locals


class Event(SiteAwareModel):
    """One xAPI-shaped event.

    All foreign keys except ``site`` (inherited) are nullable / SET_NULL so
    that deletion of any referenced record leaves the event intact. Snapshots
    stored alongside the FKs are the authoritative audit record.
    """

    # Non-persisted one-shot sentinel consumed by :py:meth:`Event.save` to
    # guarantee events are only created via experience_api.tracking.track().
    _tracker_authorised: bool = False

    site_domain = models.CharField(max_length=253)

    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    actor_email = models.EmailField(max_length=254, blank=True, default="")
    actor_display_name = models.CharField(max_length=512, blank=True, default="")
    # xAPI Inverse-Functional Identifier: "<site_homepage>|<user.id>".
    # Never email.
    actor_ifi = models.CharField(max_length=512, blank=True, default="")

    verb = models.CharField(max_length=512)
    verb_display = models.CharField(max_length=64)

    object_type = models.CharField(max_length=128)
    object_id = models.UUIDField(null=True, blank=True)
    object_definition = models.JSONField()

    result = models.JSONField(null=True, blank=True)
    context = models.JSONField(default=dict)

    # Full xAPI statement (denormalised composition of the typed columns).
    statement = models.JSONField()

    timestamp = models.DateTimeField()
    stored = models.DateTimeField(auto_now_add=True)

    session_id_hash = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    user_agent = models.CharField(max_length=1024, null=True, blank=True)  # noqa: DJ001
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    platform = models.CharField(max_length=32, default="backend")

    objects: _AppendOnlyManager = _AppendOnlyManager()

    class Meta:
        indexes = [
            models.Index(
                fields=["site", "verb", "-timestamp"],
                name="expapi_event_site_verb_ts",
            ),
            models.Index(
                fields=["site", "actor_user", "-timestamp"],
                name="expapi_event_site_actor_ts",
            ),
            models.Index(
                fields=["site", "object_type", "object_id", "-timestamp"],
                name="expapi_event_site_obj_ts",
            ),
            BrinIndex(
                fields=["timestamp"],
                name="expapi_event_ts_brin",
            ),
            GinIndex(
                fields=["context"],
                opclasses=["jsonb_path_ops"],
                name="expapi_event_ctx_gin",
            ),
            GinIndex(
                fields=["result"],
                opclasses=["jsonb_path_ops"],
                name="expapi_event_result_gin",
            ),
        ]

    # -- Immutability enforcement -----------------------------------------

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise EventImmutableError("Event rows are immutable once written.")
        if not getattr(self, "_tracker_authorised", False):
            raise EventImmutableError(
                "Events must be created via experience_api.tracking.track()."
            )
        # The _tracker_authorised flag is a one-shot token. Consume it only
        # after super().save() succeeds so that pre_save still sees it.
        super().save(*args, **kwargs)
        with contextlib.suppress(AttributeError):
            delattr(self, "_tracker_authorised")

    def delete(self, *args, **kwargs):
        raise EventImmutableError("Events cannot be deleted via the ORM.")


class ActorErasure(SiteAwareModel):
    """Append-only audit trail of erasure operations.

    One row per invocation of ``erase_actor``. The erasure role itself is not
    granted ``UPDATE`` or ``DELETE`` on this table — it is strictly
    insert-only for every caller (see migration 0002).
    """

    target_user_id = models.BigIntegerField()
    erased_token = models.CharField(max_length=64)
    event_count = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    invoking_os_user = models.CharField(max_length=256)
    invoking_hostname = models.CharField(max_length=256)
    invoking_admin_user_id = models.BigIntegerField(null=True, blank=True)

    objects: _AppendOnlyManager = _AppendOnlyManager()

    class Meta:
        indexes = [
            models.Index(fields=["target_user_id"], name="expapi_erase_user_idx"),
            models.Index(fields=["-timestamp"], name="expapi_erase_ts_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise EventImmutableError("ActorErasure rows are immutable once written.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise EventImmutableError("ActorErasure rows cannot be deleted.")


# ---------------------------------------------------------------------------
# pre_save signal — defence in depth. Triggers before ``super().save()`` runs
# and enforces the same invariants as the ``Event.save`` override. The
# ``_tracker_authorised`` flag is still on the instance at this point because
# the override only deletes it after ``super().save`` completes.


@receiver(pre_save, sender=Event)
def _enforce_event_immutability(sender, instance: Event, **kwargs) -> None:
    if not instance._state.adding:
        raise EventImmutableError("Event rows are immutable once written.")
    if not getattr(instance, "_tracker_authorised", False):
        raise EventImmutableError(
            "Events must be created via experience_api.tracking.track()."
        )


@receiver(pre_save, sender=ActorErasure)
def _enforce_actor_erasure_immutability(
    sender, instance: ActorErasure, **kwargs
) -> None:
    if not instance._state.adding:
        raise EventImmutableError("ActorErasure rows are immutable once written.")
