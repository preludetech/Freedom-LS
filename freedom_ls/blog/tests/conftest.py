import importlib
from collections.abc import Callable, Iterator

import pytest

from django.test import override_settings
from django.urls import clear_url_caches

from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.blog"):
    collect_ignore_glob = ["test_*.py"]


def _reload_urlconf() -> None:
    importlib.reload(importlib.import_module("config.urls"))
    clear_url_caches()


@pytest.fixture
def blog_url_prefix() -> Iterator[Callable[[str], None]]:
    """Return a callable that serves the blog under another prefix.

    The URLconf is reloaded on entry and again on teardown, so the changed
    prefix never reaches another test.
    """
    overrides: list[override_settings] = []

    def _set_prefix(prefix: str) -> None:
        override = override_settings(BLOG_URL_PREFIX=prefix)
        override.enable()
        overrides.append(override)
        _reload_urlconf()

    try:
        yield _set_prefix
    finally:
        for override in reversed(overrides):
            override.disable()
        _reload_urlconf()
