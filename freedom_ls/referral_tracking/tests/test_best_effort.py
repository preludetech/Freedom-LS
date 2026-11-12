"""Tests for the best-effort write guard."""

from __future__ import annotations

import pytest

from django.db import DatabaseError

from freedom_ls.referral_tracking.best_effort import best_effort_write
from freedom_ls.referral_tracking.factories import AttributionTouchFactory
from freedom_ls.referral_tracking.models import AttributionTouch


@pytest.fixture
def sentry(mocker):
    return mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")


def test_a_database_error_inside_is_reported_to_sentry(db, sentry) -> None:
    with best_effort_write():
        raise DatabaseError("boom")

    sentry.capture_exception.assert_called_once()


def test_a_database_error_inside_is_not_raised(db, sentry) -> None:
    with best_effort_write():
        raise DatabaseError("boom")


@pytest.mark.django_db
def test_the_callers_transaction_stays_usable_after_a_failed_write(
    mock_site_context, sentry
) -> None:
    touch = AttributionTouchFactory()

    with best_effort_write():
        AttributionTouchFactory(
            user=touch.user,
            occurred_at=touch.occurred_at,
            utm_source=touch.utm_source,
        )

    assert AttributionTouch._base_manager.count() == 1
