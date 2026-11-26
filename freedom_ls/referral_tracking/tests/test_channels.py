from dataclasses import fields
from datetime import UTC, datetime

import pytest

from freedom_ls.referral_tracking.channels import (
    EMAIL_HOSTS,
    SEARCH_HOSTS,
    SOCIAL_HOSTS,
    VIDEO_HOSTS,
    Channel,
    ChannelBasis,
    ChannelResult,
    FirstTouch,
    FirstTouchFields,
    classify,
    has_signal,
    is_direct_pair,
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


@pytest.mark.parametrize("source", ["direct", "(direct)"])
@pytest.mark.parametrize("medium", ["none", "(none)", "(not set)"])
def test_is_direct_pair_true_for_direct_source_and_empty_medium(
    source: str, medium: str
) -> None:
    assert is_direct_pair(source, medium) is True


@pytest.mark.parametrize(
    ("source", "medium"),
    [(" DIRECT ", "None"), ("(Direct)", " (NOT SET) ")],
)
def test_is_direct_pair_ignores_case_and_surrounding_spaces(
    source: str, medium: str
) -> None:
    assert is_direct_pair(source, medium) is True


@pytest.mark.parametrize(
    ("source", "medium"),
    [("direct", "email"), ("google", "none"), ("", "none"), ("direct", "")],
)
def test_is_direct_pair_false_for_anything_else(source: str, medium: str) -> None:
    assert is_direct_pair(source, medium) is False


def test_classify_direct_marker_pair_is_direct() -> None:
    result = classify(_touch(utm_source="(direct)", utm_medium="(none)"))

    assert result == ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)


def test_classify_direct_marker_from_a_signup_attribution_is_direct() -> None:
    record = SignupAttribution(utm_source="direct", utm_medium="none")

    result = classify(FirstTouch.from_record(record, _FIRST_SEEN))

    assert result == ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)


def _utm(channel: Channel, platform: str = "") -> ChannelResult:
    return ChannelResult(channel, platform, ChannelBasis.UTM)


@pytest.mark.parametrize(
    ("utm_source", "utm_medium", "expected"),
    [
        ("google", "cpc", _utm(Channel.PAID_SEARCH, "Google")),
        ("bing", "ppc", _utm(Channel.PAID_SEARCH, "Bing")),
        ("google", "paid_search", _utm(Channel.PAID_SEARCH, "Google")),
        ("facebook", "paid", _utm(Channel.PAID_SOCIAL, "Facebook")),
        ("fb", "cpc", _utm(Channel.PAID_SOCIAL, "Facebook")),
        ("ig", "cpc", _utm(Channel.PAID_SOCIAL, "Instagram")),
        ("tt", "paid_social", _utm(Channel.PAID_SOCIAL, "TikTok")),
        ("x", "cpc", _utm(Channel.PAID_SOCIAL, "X")),
        ("an", "cpc", _utm(Channel.PAID_SOCIAL, "Meta")),
        ("msg", "cpc", _utm(Channel.PAID_SOCIAL, "Meta")),
        ("youtube", "cpv", _utm(Channel.PAID_SOCIAL, "YouTube")),
        ("linkedin", "retargeting", _utm(Channel.PAID_SOCIAL, "LinkedIn")),
        ("newsletter", "display", _utm(Channel.OTHER)),
        ("someadnet", "cpm", _utm(Channel.OTHER)),
        ("someadnet", "cpc", _utm(Channel.OTHER)),
        ("google", "organic", _utm(Channel.ORGANIC_SEARCH, "Google")),
        ("google", "", _utm(Channel.ORGANIC_SEARCH, "Google")),
        ("", "organic", _utm(Channel.ORGANIC_SEARCH)),
        ("facebook", "social", _utm(Channel.ORGANIC_SOCIAL, "Facebook")),
        ("linkedin", "", _utm(Channel.ORGANIC_SOCIAL, "LinkedIn")),
        ("", "social-media", _utm(Channel.ORGANIC_SOCIAL)),
        ("", "video", _utm(Channel.ORGANIC_SOCIAL)),
        ("newsletter", "promo-video", _utm(Channel.ORGANIC_SOCIAL)),
        ("vimeo", "", _utm(Channel.ORGANIC_SOCIAL, "Vimeo")),
        ("newsletter", "email", _utm(Channel.EMAIL, "Email")),
        ("e-mail", "", _utm(Channel.EMAIL, "Email")),
        ("partner", "referral", _utm(Channel.REFERRAL)),
        ("partner", "affiliate", _utm(Channel.REFERRAL)),
        ("partner", "banana", _utm(Channel.OTHER)),
        (" Google ", "CPC", _utm(Channel.PAID_SEARCH, "Google")),
        ("facebook.com", "social", _utm(Channel.ORGANIC_SOCIAL)),
        ("xbox", "cpc", _utm(Channel.OTHER)),
        ("facebook", "cpc", _utm(Channel.PAID_SOCIAL, "Facebook")),
    ],
)
def test_classify_utm_pair(
    utm_source: str, utm_medium: str, expected: ChannelResult
) -> None:
    result = classify(_touch(utm_source=utm_source, utm_medium=utm_medium))

    assert result == expected


def _referer(channel: Channel, platform: str = "") -> ChannelResult:
    return ChannelResult(channel, platform, ChannelBasis.REFERER)


_PAID_GOOGLE = ChannelResult(Channel.PAID_SEARCH, "Google", ChannelBasis.GCLID)


@pytest.mark.parametrize("identifier", ["gclid", "gbraid", "wbraid"])
def test_classify_google_click_identifier_is_paid_search(identifier: str) -> None:
    result = classify(_touch(**{identifier: "abc"}))

    assert result == _PAID_GOOGLE


def test_classify_utm_beats_a_click_identifier() -> None:
    result = classify(_touch(utm_source="newsletter", utm_medium="email", gclid="abc"))

    assert result == _utm(Channel.EMAIL, "Email")


def test_classify_click_identifier_beats_a_referer() -> None:
    result = classify(_touch(gclid="abc", referer="https://www.facebook.com/"))

    assert result == _PAID_GOOGLE


def test_classify_direct_pair_falls_through_to_a_click_identifier() -> None:
    result = classify(_touch(utm_source="direct", utm_medium="none", gclid="abc"))

    assert result == _PAID_GOOGLE


def test_classify_direct_pair_falls_through_to_the_referer() -> None:
    result = classify(
        _touch(
            utm_source="direct", utm_medium="none", referer="https://www.facebook.com/"
        )
    )

    assert result == _referer(Channel.ORGANIC_SOCIAL, "Facebook")


@pytest.mark.parametrize(
    ("referer", "expected"),
    [
        (
            "https://l.facebook.com/l.php?u=x",
            _referer(Channel.ORGANIC_SOCIAL, "Facebook"),
        ),
        ("https://lm.facebook.com/", _referer(Channel.ORGANIC_SOCIAL, "Facebook")),
        ("https://m.facebook.com/", _referer(Channel.ORGANIC_SOCIAL, "Facebook")),
        ("https://l.instagram.com/", _referer(Channel.ORGANIC_SOCIAL, "Instagram")),
        ("https://search.yahoo.com/", _referer(Channel.ORGANIC_SEARCH, "Yahoo")),
        ("https://www.google.co.za/", _referer(Channel.ORGANIC_SEARCH, "Google")),
        ("https://www.google.com.au/", _referer(Channel.ORGANIC_SEARCH, "Google")),
        ("https://www.google.de/", _referer(Channel.ORGANIC_SEARCH, "Google")),
        ("https://accounts.google.com/", _referer(Channel.REFERRAL)),
        ("https://docs.google.com/", _referer(Channel.REFERRAL)),
        ("https://box.com/", _referer(Channel.REFERRAL)),
        ("https://ghost.co/", _referer(Channel.REFERRAL)),
        ("https://outlook.office.com/", _referer(Channel.EMAIL, "Outlook")),
        ("https://outlook.office365.com/", _referer(Channel.EMAIL, "Outlook")),
        ("https://mail.proton.me/", _referer(Channel.EMAIL, "Proton Mail")),
        ("https://www.icloud.com/mail/", _referer(Channel.EMAIL, "iCloud Mail")),
        ("https://mail.yahoo.com/", _referer(Channel.EMAIL, "Yahoo Mail")),
        ("android-app://com.google.android.gm/", _referer(Channel.EMAIL, "Gmail")),
        (
            "android-app://com.linkedin.android/",
            _referer(Channel.ORGANIC_SOCIAL, "LinkedIn"),
        ),
        ("android-app://com.example.app/", _referer(Channel.REFERRAL)),
        ("not a url", ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)),
        ("http://", ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)),
    ],
)
def test_classify_referer(referer: str, expected: ChannelResult) -> None:
    result = classify(_touch(referer=referer))

    assert result == expected


def _nested_entries(table: dict[str, str]) -> list[tuple[str, str]]:
    return [
        (entry, other)
        for entry in table
        for other in table
        if entry != other and entry.endswith("." + other)
    ]


@pytest.mark.parametrize(
    "table", [SEARCH_HOSTS, SOCIAL_HOSTS, VIDEO_HOSTS, EMAIL_HOSTS]
)
def test_host_table_has_no_entry_nested_under_another(table: dict[str, str]) -> None:
    # A nested entry would never be reached, so its platform would be ignored.
    assert _nested_entries(table) == []


def test_classify_referral_code_alone_is_referral() -> None:
    result = classify(_touch(referral_code="friend"))

    assert result == ChannelResult(Channel.REFERRAL, "", ChannelBasis.REFERRAL_CODE)


def test_classify_fbclid_alone_is_organic_social_via_meta() -> None:
    result = classify(_touch(fbclid="abc"))

    assert result == ChannelResult(
        Channel.ORGANIC_SOCIAL, "Meta", ChannelBasis.FBCLID_ONLY
    )


def test_classify_referer_beats_a_referral_code() -> None:
    result = classify(
        _touch(referral_code="friend", referer="https://www.facebook.com/")
    )

    assert result == _referer(Channel.ORGANIC_SOCIAL, "Facebook")


def test_classify_referral_code_beats_fbclid() -> None:
    result = classify(_touch(referral_code="friend", fbclid="abc"))

    assert result == ChannelResult(Channel.REFERRAL, "", ChannelBasis.REFERRAL_CODE)


def test_classify_google_click_identifier_beats_a_referral_code() -> None:
    result = classify(_touch(gclid="abc", referral_code="friend"))

    assert result == _PAID_GOOGLE


def test_classify_direct_pair_falls_through_to_a_referral_code() -> None:
    result = classify(
        _touch(utm_source="direct", utm_medium="none", referral_code="friend")
    )

    assert result == ChannelResult(Channel.REFERRAL, "", ChannelBasis.REFERRAL_CODE)


def test_classify_direct_pair_falls_through_to_fbclid() -> None:
    result = classify(_touch(utm_source="direct", utm_medium="none", fbclid="abc"))

    assert result == ChannelResult(
        Channel.ORGANIC_SOCIAL, "Meta", ChannelBasis.FBCLID_ONLY
    )


def test_classify_advert_code_alone_is_direct() -> None:
    result = classify(_touch(advert_code="ad-1"))

    assert result == ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, False),
        ({"utm_source": "direct", "utm_medium": "none"}, False),
        ({"utm_source": "   "}, False),
        ({"referer": "not a url"}, False),
        ({"advert_code": "ad-1"}, True),
        ({"utm_medium": "email"}, True),
        ({"referral_code": "friend"}, True),
        ({"gclid": "abc"}, True),
        ({"gbraid": "abc"}, True),
        ({"wbraid": "abc"}, True),
        ({"fbclid": "abc"}, True),
        ({"referer": "https://example.com/"}, True),
    ],
)
def test_has_signal(overrides: dict[str, str], expected: bool) -> None:
    assert has_signal(_touch(**overrides)) is expected
