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


@pytest.fixture
def world(mock_site_context: Site, settings: SettingsWrapper) -> Iterator[World]:
    with custom_role_config(mock_site_context, settings):
        yield build_world(mock_site_context)
