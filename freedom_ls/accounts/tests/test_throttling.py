"""Tests for the per-address request cap."""

from __future__ import annotations

import pytest

from django.core.cache import cache
from django.core.exceptions import PermissionDenied

from freedom_ls.accounts.throttling import is_ip_throttled

CLIENT_IP = "203.0.113.7"


def _throttled(rf, limit: int = 2, window_seconds: int = 3600, **extra: str) -> bool:
    request = rf.get("/", **extra)
    return is_ip_throttled(
        request,
        namespace="accounts.tests",
        scope="scope",
        limit=limit,
        window_seconds=window_seconds,
    )


def test_is_ip_throttled_fires_past_the_limit(rf, settings) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None

    results = [_throttled(rf, limit=2) for _ in range(3)]

    assert results == [False, False, True]


@pytest.mark.parametrize(("limit", "window_seconds"), [(0, 3600), (2, 0)])
def test_is_ip_throttled_zero_limit_disables(
    rf, settings, limit: int, window_seconds: int
) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None

    results = [
        _throttled(rf, limit=limit, window_seconds=window_seconds) for _ in range(5)
    ]

    assert results == [False] * 5


def test_is_ip_throttled_key_holds_no_raw_ip(rf, settings) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None

    _throttled(rf, REMOTE_ADDR=CLIENT_IP)

    assert cache._cache
    assert not [key for key in cache._cache if CLIENT_IP in key]


def test_is_ip_throttled_broken_cache_fails_open(rf, settings, mocker) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None
    mocker.patch(
        "freedom_ls.accounts.throttling.cache.add",
        side_effect=ConnectionError("no cache"),
    )
    mocker.patch("freedom_ls.accounts.throttling.sentry_sdk")

    assert _throttled(rf, limit=1) is False


def test_is_ip_throttled_broken_cache_reports(rf, settings, mocker) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None
    mocker.patch(
        "freedom_ls.accounts.throttling.cache.add",
        side_effect=ConnectionError("no cache"),
    )
    sentry = mocker.patch("freedom_ls.accounts.throttling.sentry_sdk")

    _throttled(rf, limit=1)

    sentry.capture_exception.assert_called_once()


def test_is_ip_throttled_missing_proxy_header_propagates(rf, settings) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"

    with pytest.raises(PermissionDenied):
        _throttled(rf)


def test_is_ip_throttled_empty_address_is_forbidden(rf, settings) -> None:
    settings.TRUSTED_PROXY_IP_HEADER = None

    with pytest.raises(PermissionDenied):
        _throttled(rf, REMOTE_ADDR="")
