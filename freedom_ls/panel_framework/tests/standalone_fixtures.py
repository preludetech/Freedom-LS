"""The site fixtures for a run with no host project around the framework."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from django.contrib.sites.models import Site

from .helpers import make_site


@pytest.fixture
def site(db: None) -> Site:
    # RequestFactory and the test client send this host.
    return make_site(name="TestSite", domain="testserver")


@pytest.fixture
def mock_site_context(site: Site) -> Iterator[Site]:
    """Make `site` the site of every request a test builds.

    django.contrib.sites caches the host lookup for the life of the
    process, so the cache is emptied on both sides of the test.
    """
    Site.objects.clear_cache()
    yield site
    Site.objects.clear_cache()
