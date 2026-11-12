"""Tests for referral_tracking models — `SignupAttribution`, `FirstTouchCount`,
`ReferralCode` and `ReferralCodeHit`."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.db import IntegrityError
from django.db.models import ProtectedError, RestrictedError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.counters import attribution_key_hash
from freedom_ls.referral_tracking.factories import (
    AttributionTouchFactory,
    ConversionFactory,
    FirstTouchCountFactory,
    ReferralCodeFactory,
    ReferralCodeHitFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import (
    ATTRIBUTION_KEY_FIELDS,
    AttributionTouch,
    Conversion,
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


@pytest.mark.django_db
def test_referral_code_hit_str_names_the_code_not_its_id(mock_site_context) -> None:
    hit = ReferralCodeHitFactory(referral_code=ReferralCodeFactory(code="mrbeast"))

    assert str(hit).startswith("mrbeast via")


@pytest.mark.django_db
def test_updating_an_existing_attribution_touch_raises(mock_site_context) -> None:
    touch = AttributionTouchFactory()

    touch.referral_code = "other"

    with pytest.raises(ValueError, match="append-only"):
        touch.save()


@pytest.mark.django_db
def test_a_second_touch_with_the_same_site_user_time_and_key_raises(
    mock_site_context,
) -> None:
    touch = AttributionTouchFactory()

    with pytest.raises(IntegrityError):
        AttributionTouchFactory(
            user=touch.user,
            occurred_at=touch.occurred_at,
            utm_source=touch.utm_source,
        )


@pytest.mark.django_db
def test_updating_an_existing_conversion_raises(mock_site_context) -> None:
    conversion = ConversionFactory()

    conversion.target_label = "Other"

    with pytest.raises(ValueError, match="append-only"):
        conversion.save()


@pytest.mark.django_db
def test_deleting_the_user_removes_the_conversion_and_its_touches(
    mock_site_context,
) -> None:
    user = UserFactory()
    touch = AttributionTouchFactory(user=user, referral_code="A")
    ConversionFactory(user=user, first_touch=touch, last_touch=touch)

    user.delete()

    assert not Conversion._base_manager.exists()
    assert not AttributionTouch._base_manager.exists()


@pytest.mark.django_db
def test_deleting_a_touch_a_conversion_rests_on_raises(mock_site_context) -> None:
    touch = AttributionTouchFactory(referral_code="A")
    ConversionFactory(user=touch.user, first_touch=touch, last_touch=touch)

    with pytest.raises(RestrictedError):
        touch.delete()


@pytest.mark.django_db
def test_a_second_conversion_on_the_same_target_raises(mock_site_context) -> None:
    conversion = ConversionFactory()

    with pytest.raises(IntegrityError):
        ConversionFactory(
            user=conversion.user, kind=conversion.kind, target=conversion.target
        )
