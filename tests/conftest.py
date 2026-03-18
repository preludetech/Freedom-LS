"""Shared pytest fixtures for top-level tests."""

import pytest


@pytest.fixture(autouse=True)
def _disable_force_site_name(settings):
    """Ensure FORCE_SITE_NAME is always None during tests."""
    settings.FORCE_SITE_NAME = None
