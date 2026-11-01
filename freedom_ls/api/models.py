from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from django.contrib.postgres.fields import ArrayField
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel

from .scopes import ApiScope

KEY_TEXT_PREFIX = "flsk_"
LAST_USED_RESOLUTION = timedelta(minutes=5)


class ApiKeyStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"


def hash_key(key_text: str) -> str:
    return hashlib.sha256(key_text.encode()).hexdigest()


class ApiKey(SiteAwareModel, TimestampedModel):
    name = models.CharField(max_length=200)
    key_prefix = models.CharField(max_length=16, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    scopes = ArrayField(models.CharField(max_length=40, choices=ApiScope.choices))
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)

    # Held in memory on the instance that was just issued, for the one
    # response that shows it. Never a column.
    issued_key: str | None = None

    class Meta:
        verbose_name = "API key"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix})"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if not self.scopes:
            errors["scopes"] = "Choose at least one API scope."
        elif len(set(self.scopes)) != len(self.scopes):
            errors["scopes"] = "Each API scope can be chosen once."
        # Only a key being issued is held to a future expiry: an issued key's
        # expiry may pass while its name is still being edited.
        if (
            self._state.adding
            and self.expires_at is not None
            and self.expires_at <= timezone.now()
        ):
            errors["expires_at"] = "The expiry must be in the future."
        if errors:
            raise ValidationError(errors)

    @classmethod
    def issue(cls, instance: ApiKey, *, site: Site) -> str:
        """Fill an unsaved key, save it and return the one full key text.

        The site is passed in rather than read from the current request: a
        key is issued from the admin on behalf of the host site, and from
        factories and scripts where there is no request at all.

        The secret carries 256 bits of entropy, so a plain SHA-256 is enough
        and a password hasher would only add cost to every request. The prefix
        is 64 random bits under a unique constraint; a collision is accepted
        as an IntegrityError rather than retried.
        """
        instance.key_prefix = secrets.token_hex(8)
        secret = secrets.token_urlsafe(32)
        key_text = f"{KEY_TEXT_PREFIX}{instance.key_prefix}.{secret}"
        instance.key_hash = hash_key(key_text)
        instance.site = site
        instance.save()
        return key_text

    def status(self, now: datetime) -> ApiKeyStatus:
        if self.revoked_at is not None:
            return ApiKeyStatus.REVOKED
        if self.expires_at is not None and self.expires_at <= now:
            return ApiKeyStatus.EXPIRED
        return ApiKeyStatus.ACTIVE

    def is_active(self, now: datetime) -> bool:
        return self.status(now) == ApiKeyStatus.ACTIVE

    def revoke(self, now: datetime) -> None:
        if self.revoked_at is not None:
            return
        self.revoked_at = now
        self.save(update_fields=["revoked_at", "updated_at"])
