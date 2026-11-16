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
    ReferralCodeFactory,
    ReferralCodeHitFactory,
)
from freedom_ls.referral_tracking.models import AttributionTouch, ReferralCodeHit
from freedom_ls.referral_tracking.sweeps import (
    prune_attribution_touches,
    prune_referral_code_hits,
)

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
    settings.REFERRAL_TRACKING_HIT_RETENTION_DAYS = RETENTION_DAYS


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


def _aged_hit(code: object, site: Site, age: timedelta) -> ReferralCodeHit:
    """A hit with `hit_at` moved back by `age`. `auto_now_add` ignores a passed
    value on create, so the only way to backdate one is an `.update()` after."""
    hit: ReferralCodeHit = ReferralCodeHitFactory(referral_code=code, site=site)
    ReferralCodeHit._base_manager.filter(pk=hit.pk).update(hit_at=timezone.now() - age)
    return hit


def test_hits_past_retention_are_deleted_on_every_site(mock_site_context, site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    code_here = ReferralCodeFactory(site=site, hit_count=3)
    code_there = ReferralCodeFactory(site=other_site, hit_count=5)
    _aged_hit(code_here, site, OLD_ENOUGH)
    _aged_hit(code_there, other_site, OLD_ENOUGH)
    new_here = _aged_hit(code_here, site, NOT_OLD_ENOUGH)
    new_there = _aged_hit(code_there, other_site, NOT_OLD_ENOUGH)

    prune_referral_code_hits()

    remaining = set(ReferralCodeHit._base_manager.values_list("pk", flat=True))
    assert remaining == {new_here.pk, new_there.pk}
    code_here.refresh_from_db()
    code_there.refresh_from_db()
    assert code_here.hit_count == 3
    assert code_there.hit_count == 5


def test_the_hit_sweep_returns_how_many_it_deleted(mock_site_context, site) -> None:
    code = ReferralCodeFactory(site=site)
    for _ in range(3):
        _aged_hit(code, site, OLD_ENOUGH)

    assert prune_referral_code_hits() == 3


@override_settings(REFERRAL_TRACKING_HIT_RETENTION_DAYS=30)
def test_the_hit_cutoff_follows_the_retention_setting(mock_site_context, site) -> None:
    code = ReferralCodeFactory(site=site)
    _aged_hit(code, site, timedelta(days=31))
    kept = _aged_hit(code, site, timedelta(days=29))

    prune_referral_code_hits()

    assert set(ReferralCodeHit._base_manager.values_list("pk", flat=True)) == {kept.pk}


def test_hit_at_is_indexed_on_its_own() -> None:
    """The prune filters on `hit_at` alone, which the (site, hit_at) index
    cannot serve: without this one every batch is a sequential scan."""
    indexed = [tuple(index.fields) for index in ReferralCodeHit._meta.indexes]

    assert ("hit_at",) in indexed


def test_the_prune_deletes_across_a_batch_boundary(
    mock_site_context, site, mocker
) -> None:
    mocker.patch("freedom_ls.referral_tracking.sweeps.PRUNE_BATCH_SIZE", 2)
    code = ReferralCodeFactory(site=site)
    for _ in range(3):
        _aged_hit(code, site, OLD_ENOUGH)

    assert prune_referral_code_hits() == 3
    assert not ReferralCodeHit._base_manager.exists()
