"""Shared fixtures for the form_engine tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_file_scanner_cache():
    """Reset the cached file scanner before and after each test.

    get_file_scanner() is @functools.cache'd for the process lifetime, so a test
    overriding FILE_SCAN_BACKEND would otherwise leave a stale instance behind
    for whichever test runs next.
    """
    from freedom_ls.form_engine.scanning import get_file_scanner

    get_file_scanner.cache_clear()
    yield
    get_file_scanner.cache_clear()
