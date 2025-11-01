"""Shared pytest fixtures for all tests."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
import tempfile
from pathlib import Path

from content_engine.models import Form

User = get_user_model()


@pytest.fixture
def site():
    """Create a test site."""
    site, _ = Site.objects.get_or_create(
        name="TestSite", defaults={"domain": "testsite"}
    )
    return site


@pytest.fixture
def user(site):
    """Create a test user."""
    user = User(
        email="test@example.com",
        site_id=site,
        is_active=True,
    )
    user.set_password("testpass")
    user.save()
    return user


@pytest.fixture
def form(site):
    """Create a test form."""
    return Form.objects.create(
        site_id=site, title="Test Form", strategy="CATEGORY_VALUE_SUM"
    )


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
