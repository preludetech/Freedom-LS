"""Tests for referral code text and the site paths a code can redirect to."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError

from freedom_ls.referral_tracking.codes import (
    GENERATED_CODE_ALPHABET,
    GENERATED_CODE_LENGTH,
    RESERVED_REFERRAL_CODES,
    absolute_code_url,
    build_redirect_url,
    generate_code,
    inactive_destination_for,
    lookup_referral_code,
    validate_code_text,
    validate_site_path,
)
from freedom_ls.referral_tracking.factories import ReferralCodeFactory
from freedom_ls.referral_tracking.models import Door, ReferralCode

pytestmark = pytest.mark.django_db


# --- Code text -------------------------------------------------------------


@pytest.mark.parametrize("word", sorted(RESERVED_REFERRAL_CODES))
@pytest.mark.parametrize("casing", [str.lower, str.upper, str.title])
def test_reserved_word_is_rejected_in_any_case(site, word, casing) -> None:
    with pytest.raises(ValidationError):
        validate_code_text(casing(word), site)


def test_the_sites_slugified_name_is_reserved(site) -> None:
    site.name = "My Site"
    site.save()

    with pytest.raises(ValidationError):
        validate_code_text("my-site", site)


def test_the_sites_name_without_hyphens_is_reserved(site) -> None:
    site.name = "My Site"
    site.save()

    with pytest.raises(ValidationError):
        validate_code_text("mysite", site)


def test_a_blank_site_name_reserves_nothing(site) -> None:
    site.name = ""
    site.save()

    validate_code_text("anything", site)


@pytest.mark.parametrize(
    "code", ["has_underscore", "has space", "", "a" * 65, "emoji😀"]
)
def test_code_outside_the_pattern_is_rejected(site, code) -> None:
    with pytest.raises(ValidationError):
        validate_code_text(code, site)


def test_a_code_within_the_pattern_is_accepted(site) -> None:
    validate_code_text("valid-Code123", site)


def test_generate_code_returns_eight_characters_from_the_alphabet(site) -> None:
    code = generate_code(site)

    assert len(code) == GENERATED_CODE_LENGTH
    assert all(character in GENERATED_CODE_ALPHABET for character in code)


def test_generate_code_retries_past_a_collision(site, mocker) -> None:
    ReferralCodeFactory(site=site, code="AAAAAAAA")
    mocker.patch(
        "freedom_ls.referral_tracking.codes.secrets.choice",
        side_effect=[*"AAAAAAAA", *"BBBBBBBB"],
    )

    code = generate_code(site)

    assert code == "BBBBBBBB"


def test_generate_code_retries_past_a_reserved_candidate(site, mocker) -> None:
    mocker.patch(
        "freedom_ls.referral_tracking.codes.secrets.choice",
        side_effect=[*"ACCOUNTS", *"BBBBBBBB"],
    )

    code = generate_code(site)

    assert code == "BBBBBBBB"


def test_lookup_referral_code_is_case_insensitive(site) -> None:
    ReferralCodeFactory(site=site, code="MrBeast")

    found = lookup_referral_code(site, "mrbeast")

    assert found is not None
    assert found.code == "MrBeast"


def test_lookup_referral_code_finds_nothing_on_another_site(site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    ReferralCodeFactory(site=other_site, code="mrbeast")

    assert lookup_referral_code(site, "mrbeast") is None


# --- Paths -------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "//evil.com",
        "/\\evil.com",
        "https://x",
        "x",
        "/a b",
        "/a\x01b",
        "/go/other",
    ],
)
def test_rejected_site_paths(value) -> None:
    with pytest.raises(ValidationError):
        validate_site_path(value)


@pytest.mark.parametrize("value", ["/", "/courses/x", "/courses/x?a=1#top"])
def test_accepted_site_paths(value) -> None:
    validate_site_path(value)


# --- build_redirect_url -------------------------------------------------------------


def _code(**kwargs: object) -> ReferralCode:
    defaults = {"code": "mrbeast", "destination": "/courses/", "is_active": True}
    defaults.update(kwargs)
    return ReferralCode(**defaults)


def test_destination_query_pairs_survive_with_no_visitor_query() -> None:
    code = _code(destination="/courses/?a=1&b=2")

    url = build_redirect_url(code, "")

    assert urlsplit(url).query == "a=1&b=2&ref=mrbeast"


def test_the_visitors_query_survives() -> None:
    code = _code(destination="/courses/")

    url = build_redirect_url(code, "x=9")

    assert urlsplit(url).query == "x=9&ref=mrbeast"


def test_the_visitor_wins_on_a_shared_key() -> None:
    code = _code(destination="/courses/?a=1")

    url = build_redirect_url(code, "a=2")

    assert urlsplit(url).query == "a=2&ref=mrbeast"


def test_ref_from_the_destination_is_replaced_by_the_stored_code() -> None:
    code = _code(destination="/courses/?ref=typed")

    url = build_redirect_url(code, "")

    assert urlsplit(url).query == "ref=mrbeast"


def test_ref_from_the_visitor_is_replaced_by_the_stored_code() -> None:
    code = _code(destination="/courses/")

    url = build_redirect_url(code, "ref=typed")

    assert urlsplit(url).query == "ref=mrbeast"


def test_a_stored_mixed_case_code_reached_in_lowercase_appends_its_own_case() -> None:
    code = _code(code="MrBeast", destination="/courses/")

    url = build_redirect_url(code, "")

    assert urlsplit(url).query == "ref=MrBeast"


def test_the_fragment_stays_last() -> None:
    code = _code(destination="/courses/?a=1#top")

    url = build_redirect_url(code, "")

    assert urlsplit(url).fragment == "top"
    assert url.endswith("#top")


def test_an_inactive_code_uses_its_own_inactive_destination() -> None:
    code = _code(is_active=False, inactive_destination="/retired/")

    url = build_redirect_url(code, "")

    assert urlsplit(url).path == "/retired/"


def test_an_inactive_code_with_no_inactive_destination_uses_the_setting(
    settings,
) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = "/gone/"
    code = _code(is_active=False, inactive_destination="")

    url = build_redirect_url(code, "")

    assert urlsplit(url).path == "/gone/"


def test_inactive_destination_for_reports_when_it_is_the_default(settings) -> None:
    settings.REFERRAL_TRACKING_INACTIVE_DESTINATION = "/gone/"
    code = _code(is_active=False, inactive_destination="")

    assert inactive_destination_for(code) == "/gone/"


def test_base_overrides_the_default_source() -> None:
    code = _code(destination="/courses/")

    url = build_redirect_url(code, "", base="/other/")

    assert urlsplit(url).path == "/other/"


# --- absolute_code_url -------------------------------------------------------------


def test_absolute_code_url_uses_the_codes_site_domain(site) -> None:
    site.domain = "referral-codes.example.com"
    site.save()
    referral_code = ReferralCodeFactory(site=site, code="mrbeast")

    url = absolute_code_url(referral_code, Door.GO)

    assert url == "https://referral-codes.example.com/go/mrbeast"


def test_absolute_code_url_for_d_uppercases_the_whole_string(site) -> None:
    site.domain = "referral-codes.example.com"
    site.save()
    referral_code = ReferralCodeFactory(site=site, code="mrbeast")

    url = absolute_code_url(referral_code, Door.D)

    assert url == url.upper()
    assert url == "HTTPS://REFERRAL-CODES.EXAMPLE.COM/D/MRBEAST"
