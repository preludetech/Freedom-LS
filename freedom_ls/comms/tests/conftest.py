"""Shared fixtures for `comms` tests."""

from __future__ import annotations

import pytest
import pytest_django.fixtures


@pytest.fixture(autouse=True)
def _enable_notifications(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """The bell is off by default; comms tests exercise it switched on."""
    settings.NOTIFICATIONS_ENABLED = True
