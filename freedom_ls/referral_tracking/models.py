from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel

CAPS: dict[str, int] = {
    "advert_code": 64,
    "utm_source": 64,
    "utm_medium": 64,
    "utm_campaign": 255,
    "utm_content": 128,
    "utm_term": 128,
    "gclid": 128,
    "gbraid": 128,
    "wbraid": 128,
    "fbclid": 256,
    "landing_path": 255,
    "referer": 255,
    "raw_query": 512,
    "ga_cookie": 64,
    "fbp_cookie": 64,
    "fbc_cookie": 320,
    "user_agent": 512,
}

ATTRIBUTION_KEY_FIELDS = (
    "advert_code",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
)


class SignupAttribution(SiteAwareModel):
    """Append-only record of where one signed-up user's first landing came from.

    Each row is created exactly once, on the signup POST. The model rejects
    updates to existing rows; the admin registers this model as fully read-only.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signup_attribution",
    )

    # Frozen at first landing, carried in the attribution cookie.
    advert_code = models.CharField(blank=True, max_length=CAPS["advert_code"])
    utm_source = models.CharField(blank=True, max_length=CAPS["utm_source"])
    utm_medium = models.CharField(blank=True, max_length=CAPS["utm_medium"])
    utm_campaign = models.CharField(blank=True, max_length=CAPS["utm_campaign"])
    utm_content = models.CharField(blank=True, max_length=CAPS["utm_content"])
    utm_term = models.CharField(blank=True, max_length=CAPS["utm_term"])
    gclid = models.CharField(blank=True, max_length=CAPS["gclid"])
    gbraid = models.CharField(blank=True, max_length=CAPS["gbraid"])
    wbraid = models.CharField(blank=True, max_length=CAPS["wbraid"])
    fbclid = models.CharField(blank=True, max_length=CAPS["fbclid"])
    landing_path = models.CharField(blank=True, max_length=CAPS["landing_path"])
    referer = models.CharField(blank=True, max_length=CAPS["referer"])
    raw_query = models.CharField(blank=True, max_length=CAPS["raw_query"])
    first_seen = models.DateTimeField()

    # Taken from the signup request itself.
    ga_cookie = models.CharField(blank=True, max_length=CAPS["ga_cookie"])
    fbp_cookie = models.CharField(blank=True, max_length=CAPS["fbp_cookie"])
    fbc_cookie = models.CharField(blank=True, max_length=CAPS["fbc_cookie"])
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(blank=True, max_length=CAPS["user_agent"])
    signed_up_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["site", "signed_up_at"]),
            models.Index(fields=["site", "utm_source"]),
            models.Index(fields=["site", "utm_campaign"]),
        ]
        ordering = ["-signed_up_at"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        # `SiteAwareModel` uses a UUID PK with `default=uuid.uuid4`, so
        # `self.pk` is set as soon as the instance is constructed — before
        # the row exists in the DB. We therefore need `_state.adding` to
        # distinguish "first-time insert" from "update an existing row".
        # Note: this guard only covers ``.save()``. ``QuerySet.update()`` and
        # ``bulk_update()`` bypass it silently — the admin is registered as
        # fully read-only as the second layer of defence.
        if self.pk is not None and self._state.adding is False:
            raise ValueError(
                "SignupAttribution records are append-only and cannot be updated"
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.user_id} via {self.utm_source}/{self.utm_medium} "
            f"at {self.signed_up_at:%Y-%m-%d}"
        )


class FirstTouchCount(SiteAwareModel):
    """Daily tally of first touches per attribution key.

    Holds no personal data: the row counts landings sharing one attribution
    key on one day, never a visitor.
    """

    day = models.DateField()
    advert_code = models.CharField(blank=True, max_length=CAPS["advert_code"])
    utm_source = models.CharField(blank=True, max_length=CAPS["utm_source"])
    utm_medium = models.CharField(blank=True, max_length=CAPS["utm_medium"])
    utm_campaign = models.CharField(blank=True, max_length=CAPS["utm_campaign"])
    utm_content = models.CharField(blank=True, max_length=CAPS["utm_content"])
    utm_term = models.CharField(blank=True, max_length=CAPS["utm_term"])
    is_overflow = models.BooleanField(default=False)
    key_hash = models.CharField(max_length=64)
    count = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Counts cookie mints, not visitors: bots and link unfurlers "
            "inflate it. Use it to compare campaigns against each other, "
            "not as an absolute count."
        ),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "day", "key_hash"], name="unique_first_touch_count"
            ),
        ]
        indexes = [
            models.Index(fields=["site", "utm_source"]),
            models.Index(fields=["site", "utm_campaign"]),
        ]

    def __str__(self) -> str:
        return f"{self.day}: {self.count} × {self.utm_source}/{self.utm_campaign}"  # noqa: RUF001 -- the multiplication sign, not an x
