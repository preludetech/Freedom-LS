"""Tests for referral_tracking models — `SignupAttribution`, `FirstTouchCount`,
`ReferralCode` and `ReferralCodeHit`."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.db import IntegrityError
from django.db.models import ProtectedError

from freedom_ls.referral_tracking.counters import attribution_key_hash
from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    ReferralCodeFactory,
    ReferralCodeHitFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import (
    ATTRIBUTION_KEY_FIELDS,
    ReferralCode,
    SignupAttribution,
)


@pytest.mark.django_db
def test_updating_an_existing_signup_attribution_raises(mock_site_context) -> None:
    attribution = SignupAttributionFactory()

    attribution.utm_campaign = "spring-sale"

    with pytest.raises(ValueError, match="append-only"):
        attribution.save()


@pytest.mark.django_db
def test_deleting_the_user_deletes_the_signup_attribution(mock_site_context) -> None:
    attribution = SignupAttributionFactory()
    user = attribution.user

    user.delete()

    assert not SignupAttribution.objects.filter(pk=attribution.pk).exists()


@pytest.mark.django_db
def test_duplicate_first_touch_count_key_for_same_site_and_day_raises(
    mock_site_context,
) -> None:
    FirstTouchCountFactory(day="2026-01-01", key_hash="samehash")

    with pytest.raises(IntegrityError):
        FirstTouchCountFactory(day="2026-01-01", key_hash="samehash")


@pytest.mark.django_db
def test_first_touch_count_factory_hashes_the_seven_key_values(
    mock_site_context,
) -> None:
    row = FirstTouchCountFactory(referral_code="mrbeast")

    expected = attribution_key_hash(
        *(getattr(row, name) for name in ATTRIBUTION_KEY_FIELDS)
    )
    assert row.key_hash == expected


@pytest.mark.django_db
def test_case_only_duplicate_referral_code_on_one_site_raises(
    mock_site_context,
) -> None:
    ReferralCodeFactory(code="mrbeast")

    with pytest.raises(IntegrityError):
        ReferralCodeFactory(code="MrBeast")


@pytest.mark.django_db
def test_the_same_referral_code_on_two_sites_saves(mock_site_context, site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")

    ReferralCodeFactory(site=site, code="mrbeast")
    ReferralCodeFactory(site=other_site, code="mrbeast")

    assert ReferralCode._base_manager.filter(code__iexact="mrbeast").count() == 2


@pytest.mark.django_db
def test_deleting_a_referral_code_with_hits_raises(mock_site_context) -> None:
    hit = ReferralCodeHitFactory()

    with pytest.raises(ProtectedError):
        hit.referral_code.delete()
