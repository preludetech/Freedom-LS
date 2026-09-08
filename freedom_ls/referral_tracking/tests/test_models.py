"""Tests for referral_tracking models — `SignupAttribution` and `FirstTouchCount`."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import SignupAttribution


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
