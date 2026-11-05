"""Collection guard and shared fixtures for the course_interest tests."""

from collections.abc import Iterator

import pytest

from django.core.cache import cache

from freedom_ls.tests.app_guards import ignore_tests_unless_installed

collect_ignore_glob = ignore_tests_unless_installed("freedom_ls.course_interest")


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Empty the cache around every test in this app.

    The API throttle counts in the cache, and the default LocMemCache lives
    for the whole test process, so counts would otherwise carry from one test
    into the next.
    """
    cache.clear()
    yield
    cache.clear()
