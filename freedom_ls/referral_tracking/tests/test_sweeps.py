"""Tests for the referral_tracking retention sweeps."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib.sites.models import Site
from django.test import override_settings
from django.utils import timezone

from freedom_ls.referral_tracking.factories import (
    AttributionTouchFactory,
    ConversionFactory,
)
from freedom_ls.referral_tracking.models import AttributionTouch
from freedom_ls.referral_tracking.sweeps import prune_attribution_touches

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("_pinned_retention"),
]

RETENTION_DAYS = 365
OLD_ENOUGH = timedelta(days=RETENTION_DAYS + 1)
NOT_OLD_ENOUGH = timedelta(days=RETENTION_DAYS - 1)


@pytest.fixture
def _pinned_retention(settings) -> None:
    settings.REFERRAL_TRACKING_TOUCH_RETENTION_DAYS = RETENTION_DAYS


def _touch(site: Site, age: timedelta) -> AttributionTouch:
    touch: AttributionTouch = AttributionTouchFactory.create(
        site=site, occurred_at=timezone.now() - age
    )
    return touch


def _remaining() -> set[object]:
    return set(AttributionTouch._base_manager.values_list("pk", flat=True))


def test_touches_past_retention_are_deleted_and_younger_ones_kept(
    mock_site_context, site
) -> None:
    _touch(site, OLD_ENOUGH)
    recent = _touch(site, NOT_OLD_ENOUGH)

    prune_attribution_touches()

    assert _remaining() == {recent.pk}


def test_touches_a_conversion_references_are_kept(mock_site_context, site) -> None:
    as_first = _touch(site, OLD_ENOUGH)
    as_last = _touch(site, OLD_ENOUGH)
    unreferenced = _touch(site, OLD_ENOUGH)
    ConversionFactory(site=site, first_touch=as_first)
    ConversionFactory(
        site=site, last_touch=as_last, user=AttributionTouchFactory(site=site).user
    )

    prune_attribution_touches()

    remaining = _remaining()
    assert as_first.pk in remaining
    assert as_last.pk in remaining
    assert unreferenced.pk not in remaining


def test_touches_on_every_site_are_pruned(mock_site_context, site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    _touch(site, OLD_ENOUGH)
    _touch(other_site, OLD_ENOUGH)

    prune_attribution_touches()

    assert not AttributionTouch._base_manager.exists()


def test_the_sweep_returns_how_many_it_deleted(mock_site_context, site) -> None:
    for _ in range(3):
        _touch(site, OLD_ENOUGH)

    assert prune_attribution_touches() == 3


@override_settings(REFERRAL_TRACKING_TOUCH_RETENTION_DAYS=120)
def test_the_cutoff_follows_the_retention_setting(mock_site_context, site) -> None:
    _touch(site, timedelta(days=121))
    kept = _touch(site, timedelta(days=119))

    prune_attribution_touches()

    assert _remaining() == {kept.pk}
