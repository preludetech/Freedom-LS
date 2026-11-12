from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from freedom_ls.referral_tracking.codes import validate_site_path
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
    "referral_code": 64,
}

ATTRIBUTION_KEY_FIELDS = (
    "advert_code",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "referral_code",
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
    referral_code = models.CharField(blank=True, max_length=CAPS["referral_code"])
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
    referral_code = models.CharField(blank=True, max_length=CAPS["referral_code"])
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


class Door(models.TextChoices):
    GO = "go", "/go/"
    D = "d", "/d/"


class TouchSource(models.TextChoices):
    LIVE = "live", "Live"
    SIGNUP_FLUSH = "signup_flush", "Signup flush"
    LOGIN_FLUSH = "login_flush", "Login flush"


class AttributionTouch(SiteAwareModel):
    """Append-only record of one tracked landing by a known account.

    Keyed on `user`, not `Learner`: attribution belongs to the account, and a
    signup happens before any `Learner` row exists. A live touch is written the
    moment a signed-in user lands; a flushed one is written later from the
    cookie, so `occurred_at` is when the landing happened and `recorded_at`
    is when the row was written. `recorded_via` tells a reader how far to trust
    the ordering. Holds no IP, user agent, referer, raw query or click
    identifier.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attribution_touches",
    )
    advert_code = models.CharField(blank=True, max_length=CAPS["advert_code"])
    referral_code = models.CharField(blank=True, max_length=CAPS["referral_code"])
    utm_source = models.CharField(blank=True, max_length=CAPS["utm_source"])
    utm_medium = models.CharField(blank=True, max_length=CAPS["utm_medium"])
    utm_campaign = models.CharField(blank=True, max_length=CAPS["utm_campaign"])
    utm_content = models.CharField(blank=True, max_length=CAPS["utm_content"])
    utm_term = models.CharField(blank=True, max_length=CAPS["utm_term"])
    # Set on a live touch and a flushed first touch; blank on a flushed list entry.
    landing_path = models.CharField(blank=True, max_length=CAPS["landing_path"])
    occurred_at = models.DateTimeField(db_index=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_via = models.CharField(max_length=16, choices=TouchSource)
    key_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "occurred_at", "key_hash"],
                name="unique_attribution_touch",
            ),
        ]
        indexes = [
            models.Index(fields=["site", "user", "occurred_at"]),
            models.Index(fields=["site", "referral_code"]),
            # A cursor for a changed-since conversions feed.
            models.Index(fields=["site", "recorded_at"]),
        ]
        # recorded_at breaks ties so two touches at one instant sort the same way every time.
        ordering = ["-occurred_at", "-recorded_at"]
        verbose_name_plural = "attribution touches"

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
                "AttributionTouch records are append-only and cannot be updated"
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.user_id} via {self.utm_source}/{self.referral_code} "
            f"at {self.occurred_at:%Y-%m-%d}"
        )


class ConversionKind(models.TextChoices):
    ACCOUNT_SIGNUP = "account_signup", "Account signup"
    COURSE_APPLICATION = "course_application", "Course application"
    COURSE_INTEREST = "course_interest", "Course interest"
    COURSE_REGISTRATION = "course_registration", "Course registration"


class Conversion(SiteAwareModel):
    """Append-only record of one conversion and the referral codes in play when it happened.

    Keyed on `user`, not `Learner`: a conversion belongs to the account, and an
    `account_signup` one exists before any `Learner` row. The target is a
    generic foreign key with a text `object_id`, because this app cannot
    import the target models or assume their primary key type. The codes and
    `target_label` are frozen copies, so the row still reads correctly after the
    target or a touch is gone.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_conversions",
    )
    kind = models.CharField(max_length=32, choices=ConversionKind)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.CharField(max_length=255, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    target_label = models.CharField(blank=True, max_length=255)
    occurred_at = models.DateTimeField(db_index=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    window_days = models.PositiveSmallIntegerField()
    # RESTRICT, not PROTECT: deleting a user cascades to both the touches and
    # the conversions, and PROTECT would raise there and block account erasure.
    # A touch a conversion rests on still cannot be deleted on its own.
    first_touch = models.ForeignKey(
        AttributionTouch,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="conversions_as_first",
    )
    last_touch = models.ForeignKey(
        AttributionTouch,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="conversions_as_last",
    )
    first_referral_code = models.CharField(blank=True, max_length=CAPS["referral_code"])
    last_referral_code = models.CharField(blank=True, max_length=CAPS["referral_code"])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "kind", "content_type", "object_id"],
                name="unique_conversion_per_target",
            ),
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["site", "kind", "occurred_at"]),
            # A cursor for a changed-since conversions feed.
            models.Index(fields=["site", "recorded_at"]),
        ]
        ordering = ["-occurred_at"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        # `SiteAwareModel` uses a UUID PK with `default=uuid.uuid4`, so
        # `self.pk` is set as soon as the instance is constructed — before
        # the row exists in the DB. We therefore need `_state.adding` to
        # distinguish "first-time insert" from "update an existing row".
        # Note: this guard only covers ``.save()``. ``QuerySet.update()`` and
        # ``bulk_update()`` bypass it silently — the admin is registered as
        # fully read-only as the second layer of defence.
        if self.pk is not None and self._state.adding is False:
            raise ValueError("Conversion records are append-only and cannot be updated")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.kind} by {self.user_id} at {self.occurred_at:%Y-%m-%d}"


class ReferralCode(SiteAwareModel):
    """A per-site code a builder hands to a partner, printed on a board or dropped in an email.

    `/go/{code}` and `/d/{CODE}` both redirect a visitor to `destination` and
    log the access; an inactive code redirects to `inactive_destination`
    instead. A code's text is never reused: the admin refuses deletion and
    the text is read-only once saved, so a retired code stays reserved
    rather than being handed to someone new.
    """

    code = models.CharField(
        max_length=CAPS["referral_code"],
        help_text=(
            "Leave blank to generate an 8-character print code. The code "
            "cannot be changed once the referral code is saved."
        ),
    )
    label = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    destination = models.CharField(max_length=512, validators=[validate_site_path])
    inactive_destination = models.CharField(
        max_length=512, blank=True, validators=[validate_site_path]
    )
    is_active = models.BooleanField(default=True)
    hit_count = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Counts hits not flagged as a machine fetch: an upper bound on "
            "human use, not a scan count. Link previews, mail scanners and "
            "crawlers that imitate a browser still inflate it. This number "
            "and the hit log do not reconcile — the log holds every hit, "
            "machine fetches included, and pruning empties it, while this "
            "count skips machine fetches and never goes down. Repeated hits "
            "from one address are capped per hour, so heavy use from a single "
            "connection is undercounted."
        ),
    )
    last_hit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("code"), "site", name="unique_referral_code_per_site"
            ),
        ]
        ordering = ["-created_at"]

    def full_clean(self, *args: Any, **kwargs: Any) -> None:
        self._set_site_from_request()
        if not self.code and self.site_id:
            from freedom_ls.referral_tracking.codes import generate_code

            self.code = generate_code(self.site)
        super().full_clean(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        # Only while the text is being set. A saved code can never be edited,
        # so re-checking one on update can only reject something no form can
        # fix — and the change form excludes `code`, which turns an error
        # keyed to it into a ValueError out of `add_error` rather than a
        # rendered field error.
        if self.site_id and self._state.adding:
            from freedom_ls.referral_tracking.codes import validate_code_text

            try:
                validate_code_text(self.code, self.site)
            except ValidationError as exc:
                raise ValidationError({"code": exc.messages}) from exc

    def __str__(self) -> str:
        return self.code


class ReferralCodeHit(SiteAwareModel):
    """One logged access of a ReferralCode. Holds no personal data."""

    referral_code = models.ForeignKey(
        ReferralCode, on_delete=models.PROTECT, related_name="hits"
    )
    door = models.CharField(max_length=2, choices=Door)
    is_machine_fetch = models.BooleanField()
    hit_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["site", "hit_at"]),
            # The prune filters on hit_at alone, across every site.
            models.Index(fields=["hit_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.referral_code.code} via {self.door} at {self.hit_at:%Y-%m-%d}"
