"""Tests for the `prune_attribution_touches` management command."""

from __future__ import annotations

from datetime import timedelta

import click
import pytest

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.utils import timezone

from freedom_ls.referral_tracking.factories import (
    AttributionTouchFactory,
    ConversionFactory,
)
from freedom_ls.referral_tracking.models import AttributionTouch

pytestmark = pytest.mark.django_db

OLD_ENOUGH = timedelta(days=45)
NOT_OLD_ENOUGH = timedelta(days=1)


def _touch(site: Site, age: timedelta) -> AttributionTouch:
    touch: AttributionTouch = AttributionTouchFactory.create(
        site=site, occurred_at=timezone.now() - age
    )
    return touch


def _remaining() -> set[object]:
    return set(AttributionTouch._base_manager.values_list("pk", flat=True))


def test_old_unreferenced_touches_are_deleted_and_recent_ones_kept(
    mock_site_context, site
) -> None:
    _touch(site, OLD_ENOUGH)
    recent = _touch(site, NOT_OLD_ENOUGH)

    call_command("prune_attribution_touches", "--older-than-days", "30")

    assert _remaining() == {recent.pk}


def test_touches_a_conversion_references_are_kept(mock_site_context, site) -> None:
    as_first = _touch(site, OLD_ENOUGH)
    as_last = _touch(site, OLD_ENOUGH)
    unreferenced = _touch(site, OLD_ENOUGH)
    ConversionFactory(site=site, first_touch=as_first)
    ConversionFactory(
        site=site, last_touch=as_last, user=AttributionTouchFactory(site=site).user
    )

    call_command("prune_attribution_touches", "--older-than-days", "30")

    remaining = _remaining()
    assert as_first.pk in remaining
    assert as_last.pk in remaining
    assert unreferenced.pk not in remaining


def test_touches_on_every_site_are_pruned(mock_site_context, site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    _touch(site, OLD_ENOUGH)
    _touch(other_site, OLD_ENOUGH)

    call_command("prune_attribution_touches", "--older-than-days", "30")

    assert not AttributionTouch._base_manager.exists()


def test_older_than_days_zero_is_refused(mock_site_context, site) -> None:
    touch = _touch(site, OLD_ENOUGH)

    with pytest.raises(click.exceptions.BadParameter):
        call_command("prune_attribution_touches", "--older-than-days", "0")

    assert _remaining() == {touch.pk}


def test_the_command_reports_how_many_it_deleted(
    mock_site_context, site, capsys
) -> None:
    for _ in range(3):
        _touch(site, OLD_ENOUGH)

    call_command("prune_attribution_touches", "--older-than-days", "30")

    assert (
        "Deleted 3 attribution touch(es) older than 30 day(s)."
        in capsys.readouterr().out
    )
