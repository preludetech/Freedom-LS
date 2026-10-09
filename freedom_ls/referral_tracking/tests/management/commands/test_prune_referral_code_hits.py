"""Tests for the `prune_referral_code_hits` management command."""

from __future__ import annotations

from datetime import timedelta

import click
import pytest

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.utils import timezone

from freedom_ls.referral_tracking.factories import (
    ReferralCodeFactory,
    ReferralCodeHitFactory,
)
from freedom_ls.referral_tracking.models import ReferralCodeHit

pytestmark = pytest.mark.django_db

OLD_ENOUGH = timedelta(days=45)
NOT_OLD_ENOUGH = timedelta(days=1)


def _age(hit: ReferralCodeHit, delta: timedelta) -> None:
    """Move a hit's `hit_at` back in time. `auto_now_add` ignores a passed value
    on create, so the only way to backdate one is an `.update()` after the fact.
    """
    ReferralCodeHit._base_manager.filter(pk=hit.pk).update(
        hit_at=timezone.now() - delta
    )


def test_hits_older_than_the_cutoff_are_deleted_on_every_site(
    mock_site_context, site
) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    code_here = ReferralCodeFactory(site=site, hit_count=3)
    code_there = ReferralCodeFactory(site=other_site, hit_count=5)

    old_here = ReferralCodeHitFactory(referral_code=code_here, site=site)
    new_here = ReferralCodeHitFactory(referral_code=code_here, site=site)
    old_there = ReferralCodeHitFactory(referral_code=code_there, site=other_site)
    new_there = ReferralCodeHitFactory(referral_code=code_there, site=other_site)
    _age(old_here, OLD_ENOUGH)
    _age(old_there, OLD_ENOUGH)
    _age(new_here, NOT_OLD_ENOUGH)
    _age(new_there, NOT_OLD_ENOUGH)

    call_command("prune_referral_code_hits", "--older-than-days", "30")

    remaining = set(ReferralCodeHit._base_manager.values_list("pk", flat=True))
    assert remaining == {new_here.pk, new_there.pk}
    code_here.refresh_from_db()
    code_there.refresh_from_db()
    assert code_here.hit_count == 3
    assert code_there.hit_count == 5


def test_the_command_reports_how_many_it_deleted(
    mock_site_context, site, capsys
) -> None:
    code = ReferralCodeFactory(site=site)
    first = ReferralCodeHitFactory(referral_code=code, site=site)
    second = ReferralCodeHitFactory(referral_code=code, site=site)
    third = ReferralCodeHitFactory(referral_code=code, site=site)
    _age(first, OLD_ENOUGH)
    _age(second, OLD_ENOUGH)
    _age(third, OLD_ENOUGH)

    call_command("prune_referral_code_hits", "--older-than-days", "30")

    assert (
        "Deleted 3 referral code hit(s) older than 30 day(s)."
        in capsys.readouterr().out
    )


def test_older_than_days_zero_is_refused(mock_site_context, site) -> None:
    code = ReferralCodeFactory(site=site)
    hit = ReferralCodeHitFactory(referral_code=code, site=site)
    _age(hit, OLD_ENOUGH)

    with pytest.raises(click.exceptions.BadParameter):
        call_command("prune_referral_code_hits", "--older-than-days", "0")

    assert ReferralCodeHit._base_manager.filter(pk=hit.pk).exists()


def test_hit_at_is_indexed_on_its_own() -> None:
    """The prune filters on `hit_at` alone, which the (site, hit_at) index
    cannot serve — without this one every batch is a sequential scan."""
    indexed = [tuple(index.fields) for index in ReferralCodeHit._meta.indexes]

    assert ("hit_at",) in indexed


def test_the_prune_deletes_across_a_batch_boundary(
    mock_site_context, site, mocker
) -> None:
    mocker.patch(
        "freedom_ls.referral_tracking.management.commands."
        "prune_referral_code_hits.PRUNE_BATCH_SIZE",
        2,
    )
    code = ReferralCodeFactory(site=site)
    for _ in range(3):
        _age(ReferralCodeHitFactory(referral_code=code, site=site), OLD_ENOUGH)

    call_command("prune_referral_code_hits", "--older-than-days", "30")

    assert not ReferralCodeHit._base_manager.exists()
