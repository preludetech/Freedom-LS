"""Fixtures shared by the referral_tracking tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Empty the cache around every test in this app.

    The hit-log throttle counts in the cache, and the default LocMemCache lives
    for the whole test process, so counts would otherwise carry from one test
    into the next.
    """
    cache.clear()
    yield
    cache.clear()
