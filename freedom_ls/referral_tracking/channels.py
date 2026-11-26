"""The marketing channel a first touch came through, worked out from its stored fields.

Pure: no request and no database query. Callers classify at read time, so a rule
change reclassifies history.
"""

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Protocol

from django.db import models


class Channel(models.TextChoices):
    # Declaration order is the display order: `.choices` feeds filter dropdowns.
    DIRECT = "direct", "Direct"
    ORGANIC_SEARCH = "organic_search", "Organic search"
    PAID_SEARCH = "paid_search", "Paid search"
    ORGANIC_SOCIAL = "organic_social", "Organic social"
    PAID_SOCIAL = "paid_social", "Paid social"
    EMAIL = "email", "Email"
    REFERRAL = "referral", "Referral"
    OTHER = "other", "Other"
    UNKNOWN = "unknown", "Unknown"


class ChannelBasis(models.TextChoices):
    UTM = "utm", "UTM tags"
    GCLID = "gclid", "Google click ID"
    REFERER = "referer", "Referring site"
    REFERRAL_CODE = "referral_code", "Referral code"
    FBCLID_ONLY = "fbclid_only", "Meta click ID only"
    NONE = "none", "No signal"


class FirstTouchFields(Protocol):
    """Any record with the first-touch field names, such as `SignupAttribution`
    or a project's own lead model."""

    advert_code: str
    referral_code: str
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_content: str
    utm_term: str
    gclid: str
    gbraid: str
    wbraid: str
    fbclid: str
    landing_path: str
    referer: str
    raw_query: str


@dataclass(frozen=True)
class FirstTouch:
    advert_code: str
    referral_code: str
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_content: str
    utm_term: str
    gclid: str
    gbraid: str
    wbraid: str
    fbclid: str
    landing_path: str
    referer: str
    raw_query: str
    first_seen: datetime

    @classmethod
    def from_record(
        cls, record: FirstTouchFields, first_seen: datetime
    ) -> "FirstTouch":
        names = [f.name for f in fields(cls) if f.name != "first_seen"]
        return cls(
            **{name: getattr(record, name) for name in names}, first_seen=first_seen
        )


@dataclass(frozen=True)
class ChannelResult:
    channel: Channel
    source_platform: str
    basis: ChannelBasis


def classify(first_touch: FirstTouch | None) -> ChannelResult:
    """The first matching rule wins."""
    if first_touch is None:
        return ChannelResult(Channel.UNKNOWN, "", ChannelBasis.NONE)
    return ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)
