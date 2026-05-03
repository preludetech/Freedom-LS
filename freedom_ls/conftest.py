"""Shared pytest fixtures for all tests."""

import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pytest

from django.contrib.sites.models import Site
from django.test import RequestFactory
from django.urls import reverse

# Re-export Playwright fixtures (logged_in_page, reset_local_storage) so
# tests can consume them without importing the fixtures module directly.
from freedom_ls.tests.playwright_fixtures import *  # noqa: F403


@pytest.fixture(autouse=True)
def _disable_force_site_name(settings):
    """Ensure FORCE_SITE_NAME is always None during tests."""
    settings.FORCE_SITE_NAME = None


def reverse_url(
    live_server, viewname, urlconf=None, args=None, kwargs=None, current_app=None
):
    end = reverse(viewname, urlconf, args, kwargs, current_app)
    return f"{live_server.url}{end}"


@pytest.fixture
def site(request):
    """Create a test site. Can be parametrized with a name."""
    # Check if parametrized with a name
    if hasattr(request, "param"):
        name = request.param
        domain = name.lower()
    else:
        name = "TestSite"
        domain = "testsite"

    site, _ = Site.objects.get_or_create(name=name, defaults={"domain": domain})
    return site


@pytest.fixture
def make_temp_file():
    """Create a temporary YAML file and clean it up after test."""
    temp_file = None

    def _create_file(suffix, content):
        nonlocal temp_file
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(content)
            temp_file = Path(f.name)
        return temp_file

    yield _create_file

    # Cleanup
    if temp_file and temp_file.exists():
        temp_file.unlink()


@pytest.fixture
def mock_site_context(site, mocker):
    """Mock the thread local request and get_current_site for SiteAwareModel and templates."""
    from django.contrib.sites.models import SITE_CACHE

    from freedom_ls.site_aware_models.models import _thread_locals

    # Check if request attribute already exists
    had_request = hasattr(_thread_locals, "request")
    old_request = getattr(_thread_locals, "request", None) if had_request else None

    mock_request = mocker.Mock()
    # Set _cached_site to the actual site object to prevent Mock issues in ORM queries
    mock_request._cached_site = site
    _thread_locals.request = mock_request

    mocker.patch(
        "freedom_ls.site_aware_models.models.get_current_site", return_value=site
    )
    # Also patch for template context processors
    mocker.patch("django.contrib.sites.shortcuts.get_current_site", return_value=site)

    # Clear and populate SITE_CACHE to ensure RequestFactory requests work
    SITE_CACHE.clear()
    SITE_CACHE["testserver"] = site

    yield site

    # Cleanup: restore original state and clear cache
    SITE_CACHE.clear()
    if had_request:
        _thread_locals.request = old_request
    elif hasattr(_thread_locals, "request"):
        delattr(_thread_locals, "request")


@pytest.fixture
def site_aware_request(mock_site_context):
    return RequestFactory()


@pytest.fixture
def live_server_site(live_server, site):
    # Update site domain to match the live_server
    parsed_url = urlparse(live_server.url)
    site.domain = parsed_url.netloc
    site.save()
    return site


# ``logged_in_page`` is now defined in
# ``freedom_ls.tests.playwright_fixtures`` and re-exported via the
# wildcard import at the top of this module.
