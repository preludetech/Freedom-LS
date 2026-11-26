from dataclasses import fields
from datetime import UTC, datetime

from freedom_ls.referral_tracking.channels import (
    Channel,
    ChannelBasis,
    ChannelResult,
    FirstTouch,
    FirstTouchFields,
    classify,
)
from freedom_ls.referral_tracking.models import SignupAttribution

_FIRST_SEEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

_FIELD_NAMES = [
    "advert_code",
    "referral_code",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "gclid",
    "gbraid",
    "wbraid",
    "fbclid",
    "landing_path",
    "referer",
    "raw_query",
]


def _touch(**overrides: str) -> FirstTouch:
    values = dict.fromkeys(_FIELD_NAMES, "")
    values.update(overrides)
    return FirstTouch(**values, first_seen=_FIRST_SEEN)


def test_channel_choices_are_in_display_order() -> None:
    assert Channel.choices == [
        ("direct", "Direct"),
        ("organic_search", "Organic search"),
        ("paid_search", "Paid search"),
        ("organic_social", "Organic social"),
        ("paid_social", "Paid social"),
        ("email", "Email"),
        ("referral", "Referral"),
        ("other", "Other"),
        ("unknown", "Unknown"),
    ]


def test_channel_basis_choices_are_in_display_order() -> None:
    assert ChannelBasis.choices == [
        ("utm", "UTM tags"),
        ("gclid", "Google click ID"),
        ("referer", "Referring site"),
        ("referral_code", "Referral code"),
        ("fbclid_only", "Meta click ID only"),
        ("none", "No signal"),
    ]


def test_first_touch_fields_are_the_fourteen_names_and_first_seen() -> None:
    assert [f.name for f in fields(FirstTouch)] == [*_FIELD_NAMES, "first_seen"]


def test_first_touch_fields_protocol_matches_first_touch_fields() -> None:
    assert [*FirstTouchFields.__annotations__, "first_seen"] == [
        f.name for f in fields(FirstTouch)
    ]


def test_from_record_copies_every_field_of_a_signup_attribution() -> None:
    values = {name: f"value-{name}" for name in _FIELD_NAMES}
    record = SignupAttribution(**values)

    assert FirstTouch.from_record(record, _FIRST_SEEN) == FirstTouch(
        **values, first_seen=_FIRST_SEEN
    )


def test_classify_none_is_unknown() -> None:
    assert classify(None) == ChannelResult(Channel.UNKNOWN, "", ChannelBasis.NONE)


def test_classify_empty_touch_is_direct() -> None:
    assert classify(_touch()) == ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)
