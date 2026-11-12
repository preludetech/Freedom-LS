"""Tests for resolving the touches in play at a conversion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from django.test import override_settings

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.factories import AttributionTouchFactory
from freedom_ls.referral_tracking.resolution import touches_in_play
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _days_ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_the_earliest_and_latest_coded_touches_in_the_window_are_returned(
    mock_site_context, site
) -> None:
    user = UserFactory()
    first = AttributionTouchFactory(
        user=user, referral_code="A", occurred_at=_days_ago(60)
    )
    AttributionTouchFactory(user=user, referral_code="B", occurred_at=_days_ago(30))
    last = AttributionTouchFactory(
        user=user, referral_code="C", occurred_at=_days_ago(1)
    )

    assert touches_in_play(user=user, site=site, when=NOW) == (first, last)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_a_touch_after_the_instant_is_ignored(mock_site_context, site) -> None:
    user = UserFactory()
    before = AttributionTouchFactory(
        user=user, referral_code="A", occurred_at=_days_ago(2)
    )
    AttributionTouchFactory(
        user=user, referral_code="B", occurred_at=NOW + timedelta(days=1)
    )

    assert touches_in_play(user=user, site=site, when=NOW) == (before, before)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_a_touch_older_than_the_window_is_not_the_first(
    mock_site_context, site
) -> None:
    user = UserFactory()
    AttributionTouchFactory(user=user, referral_code="OLD", occurred_at=_days_ago(91))
    inside = AttributionTouchFactory(
        user=user, referral_code="A", occurred_at=_days_ago(10)
    )

    first, _ = touches_in_play(user=user, site=site, when=NOW)

    assert first == inside


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_a_touch_older_than_the_window_is_not_the_last(mock_site_context, site) -> None:
    user = UserFactory()
    AttributionTouchFactory(user=user, referral_code="OLD", occurred_at=_days_ago(91))

    assert touches_in_play(user=user, site=site, when=NOW) == (None, None)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_a_utm_only_touch_between_coded_ones_is_ignored(
    mock_site_context, site
) -> None:
    user = UserFactory()
    first = AttributionTouchFactory(
        user=user, referral_code="A", occurred_at=_days_ago(30)
    )
    AttributionTouchFactory(
        user=user, referral_code="", utm_source="news", occurred_at=_days_ago(20)
    )
    last = AttributionTouchFactory(
        user=user, referral_code="B", occurred_at=_days_ago(10)
    )

    assert touches_in_play(user=user, site=site, when=NOW) == (first, last)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_another_users_touches_are_ignored(mock_site_context, site) -> None:
    user = UserFactory()
    AttributionTouchFactory(
        user=UserFactory(), referral_code="A", occurred_at=_days_ago(2)
    )

    assert touches_in_play(user=user, site=site, when=NOW) == (None, None)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_another_sites_touches_are_ignored(mock_site_context, site) -> None:
    user = UserFactory()
    with site_context(SiteFactory()):
        AttributionTouchFactory(user=user, referral_code="A", occurred_at=_days_ago(2))

    assert touches_in_play(user=user, site=site, when=NOW) == (None, None)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
def test_a_user_with_no_coded_touch_gets_none_for_both(mock_site_context, site) -> None:
    user = UserFactory()

    assert touches_in_play(user=user, site=site, when=NOW) == (None, None)


@pytest.mark.django_db
@time_machine.travel(NOW, tick=False)
@override_settings(REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS=30)
def test_a_shorter_window_excludes_a_touch_the_default_would_include(
    mock_site_context, site
) -> None:
    user = UserFactory()
    AttributionTouchFactory(user=user, referral_code="A", occurred_at=_days_ago(45))

    assert touches_in_play(user=user, site=site, when=NOW) == (None, None)
