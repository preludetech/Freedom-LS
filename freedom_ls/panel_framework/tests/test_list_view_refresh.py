"""The list view's create action refreshes the list's table region."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from .conftest import _make_stub
from .view_helpers import fetch

pytestmark = pytest.mark.django_db

LIST_REGION_ID = "panel-test-panel-framework-stubs"


def test_the_refresh_wiring_targets_the_list_panels_region(
    mock_site_context: Site,
) -> None:
    _make_stub(name="row-2")

    html = fetch("stubs").content.decode()

    assert html.count('x-data="listRefresh"') == 1
    assert 'data-refresh-events="itemCreated"' in html
    assert f'data-refresh-target="{LIST_REGION_ID}"' in html
    assert f'id="{LIST_REGION_ID}"' in html


def test_a_region_refresh_skips_the_create_action(mock_site_context: Site) -> None:
    _make_stub(name="row-1")

    html = fetch("stubs", htmx=True, hx_target=LIST_REGION_ID).content.decode()

    assert "row-1" in html
    assert "Create Item" not in html
