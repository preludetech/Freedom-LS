"""Shared pytest fixtures for all tests."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
import tempfile
from pathlib import Path
from django.test import RequestFactory
from django.urls import reverse
from freedom_ls.content_engine.models import Form, Activity
from urllib.parse import urlparse
from playwright.sync_api import Page
from allauth.account.models import EmailAddress


User = get_user_model()


def reverse_url(
    live_server, viewname, urlconf=None, args=None, kwargs=None, current_app=None
):
    end = reverse(viewname, urlconf, args, kwargs, current_app)
    return f"{live_server.url}{end}"


@pytest.fixture
def activity(mock_site_context):
    """Create a test activity."""
    return Activity.objects.create(
        title="Test Activity",
        slug="test-activity",
    )


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
def user(site):
    """Create a test user."""
    user = User(
        email="test@example.com",
        site=site,
        is_active=True,
    )
    user.set_password("testpass")
    user.save()
    return user


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
    from freedom_ls.site_aware_models.models import _thread_locals
    from django.contrib.sites.models import SITE_CACHE

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
def form(site):
    """Create a test form."""
    return Form.objects.create(
        site=site, title="Test Form", strategy="CATEGORY_VALUE_SUM"
    )


@pytest.fixture
def live_server_site(live_server, site):
    # Update site domain to match the live_server
    parsed_url = urlparse(live_server.url)
    site.domain = parsed_url.netloc
    site.save()
    return site


@pytest.fixture
def logged_in_page(page: Page, live_server, user, db, live_server_site):
    """Create a logged in page with a verified email address."""

    # Set the user's email as verified (required for allauth)
    # Use get_or_create to avoid duplicate email addresses
    EmailAddress.objects.get_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )

    # Navigate to login page
    login_url = reverse_url(live_server, "account_login")
    page.goto(login_url)

    # Fill in login form
    page.fill('input[name="login"]', user.email)
    page.fill('input[name="password"]', "testpass")

    # Submit the form
    page.click('button[type="submit"]')

    # Wait for navigation to complete
    page.wait_for_load_state("networkidle")

    yield page
