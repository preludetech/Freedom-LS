from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_django.fixtures import SettingsWrapper

from django.contrib.sites.models import Site

from freedom_ls.learner_management.tests.scenario_world import (
    World,
    build_world,
    custom_role_config,
)
from freedom_ls.site_aware_models.models import _thread_locals


@pytest.fixture
def world(mock_site_context: Site, settings: SettingsWrapper) -> Iterator[World]:
    with custom_role_config(mock_site_context, settings):
        yield build_world(mock_site_context)


@pytest.fixture
def without_request() -> Iterator[None]:
    """Run the test with no request in scope. List `world` first in the test's
    signature so the factories still see a site while the world is built."""
    request = getattr(_thread_locals, "request", None)
    if hasattr(_thread_locals, "request"):
        del _thread_locals.request
    yield
    if request is not None:
        _thread_locals.request = request
