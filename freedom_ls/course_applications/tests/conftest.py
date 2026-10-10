"""Shared helpers for the course_applications tests."""

from collections.abc import Iterator

import pytest

from django.core.cache import cache

from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.course_applications"):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Empty the cache around every test in this app.

    The per-address caps count in the cache, and the default LocMemCache lives
    for the whole test process, so counts would otherwise carry from one test
    into the next.
    """
    cache.clear()
    yield
    cache.clear()
