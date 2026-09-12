"""Tests for machine-fetch detection and logging one referral code access."""

from __future__ import annotations

import pytest

from django.db import DatabaseError, connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from freedom_ls.referral_tracking.codes import lookup_referral_code
from freedom_ls.referral_tracking.factories import ReferralCodeFactory
from freedom_ls.referral_tracking.hits import (
    NAMED_FETCHERS,
    is_machine_fetch,
    record_hit,
)
from freedom_ls.referral_tracking.models import Door, ReferralCodeHit

rf = RequestFactory()

REAL_BROWSER_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like "
    "Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
    "like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; CUBOT X30) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/86.0.4240.198 Mobile Safari/537.36",
)


@pytest.mark.parametrize("fetcher", NAMED_FETCHERS)
def test_a_named_fetcher_is_flagged(fetcher) -> None:
    request = rf.get("/", HTTP_USER_AGENT=f"Mozilla/5.0 ({fetcher}/1.0)")

    assert is_machine_fetch(request) is True


def test_an_empty_user_agent_is_flagged() -> None:
    request = rf.get("/", HTTP_USER_AGENT="")

    assert is_machine_fetch(request) is True


def test_a_missing_user_agent_is_flagged() -> None:
    request = rf.get("/")

    assert is_machine_fetch(request) is True


@pytest.mark.parametrize("token", ["crawler", "spider", "preview", "headless"])
def test_a_generic_token_is_flagged(token) -> None:
    request = rf.get("/", HTTP_USER_AGENT=f"Some {token} tool/1.0")

    assert is_machine_fetch(request) is True


def test_bot_is_flagged_on_a_word_boundary() -> None:
    request = rf.get("/", HTTP_USER_AGENT="Mozilla/5.0 custom bot/1.0")

    assert is_machine_fetch(request) is True


def test_a_device_name_containing_bot_as_a_substring_is_not_flagged() -> None:
    request = rf.get(
        "/",
        HTTP_USER_AGENT=(
            "Mozilla/5.0 (Linux; Android 10; CUBOT X30) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/86.0.4240.198 Mobile Safari/537.36"
        ),
    )

    assert is_machine_fetch(request) is False


@pytest.mark.parametrize("user_agent", REAL_BROWSER_USER_AGENTS)
def test_a_real_browser_user_agent_is_not_flagged(user_agent) -> None:
    request = rf.get("/", HTTP_USER_AGENT=user_agent)

    assert is_machine_fetch(request) is False


@pytest.mark.parametrize("header", ["Sec-Purpose", "Purpose", "X-Moz"])
def test_a_prefetch_header_is_flagged(header) -> None:
    meta_key = f"HTTP_{header.upper().replace('-', '_')}"
    request = rf.get(
        "/", HTTP_USER_AGENT=REAL_BROWSER_USER_AGENTS[0], **{meta_key: "prefetch"}
    )

    assert is_machine_fetch(request) is True


@pytest.mark.django_db
def test_a_flagged_hit_writes_a_row_and_leaves_the_counters_unchanged(
    mock_site_context,
) -> None:
    referral_code = ReferralCodeFactory()
    request = rf.get("/", HTTP_USER_AGENT="Slackbot 1.0")

    record_hit(referral_code, Door.GO, request)

    referral_code.refresh_from_db()
    hit = ReferralCodeHit.objects.get()
    assert hit.is_machine_fetch is True
    assert hit.door == Door.GO
    assert referral_code.hit_count == 0
    assert referral_code.last_hit_at is None


@pytest.mark.django_db
def test_an_unflagged_hit_writes_a_row_and_moves_both_counters(
    mock_site_context,
) -> None:
    referral_code = ReferralCodeFactory()
    request = rf.get("/", HTTP_USER_AGENT=REAL_BROWSER_USER_AGENTS[0])

    record_hit(referral_code, Door.D, request)

    referral_code.refresh_from_db()
    hit = ReferralCodeHit.objects.get()
    assert hit.is_machine_fetch is False
    assert hit.door == Door.D
    assert referral_code.hit_count == 1
    assert referral_code.last_hit_at is not None


@pytest.mark.django_db
def test_a_database_error_is_reported_and_swallowed(mock_site_context, mocker) -> None:
    referral_code = ReferralCodeFactory()
    request = rf.get("/", HTTP_USER_AGENT=REAL_BROWSER_USER_AGENTS[0])
    mocker.patch.object(
        ReferralCodeHit._base_manager, "create", side_effect=DatabaseError("boom")
    )
    sentry = mocker.patch("freedom_ls.referral_tracking.hits.sentry_sdk")

    record_hit(referral_code, Door.GO, request)

    sentry.capture_exception.assert_called_once()
    assert not ReferralCodeHit.objects.exists()


@pytest.mark.django_db
def test_recording_a_hit_does_not_re_fetch_the_site(mock_site_context) -> None:
    """The hit row takes the code's site id rather than dereferencing the FK.

    `lookup_referral_code` builds its queryset without `select_related`, so
    reading `referral_code.site` costs a query on every single redirect.
    """
    ReferralCodeFactory(code="mrbeast")
    # Through the lookup the view uses, not the factory instance: only a
    # freshly fetched row has an empty relation cache to fall into.
    referral_code = lookup_referral_code(mock_site_context, "mrbeast")
    request = rf.get("/", HTTP_USER_AGENT=REAL_BROWSER_USER_AGENTS[0])

    with CaptureQueriesContext(connection) as queries:
        record_hit(referral_code, Door.GO, request)

    assert not [q for q in queries.captured_queries if "django_site" in q["sql"]]
