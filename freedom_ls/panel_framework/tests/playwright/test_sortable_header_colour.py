"""E2E test that a sortable column's header link looks like every other
header label rather than picking up the global link colour."""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page

from django.contrib.sites.models import Site

from ..conftest import _make_stub


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_sortable_header_link_has_the_same_colour_as_its_header_cell(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """A sortable header link used to render in the link colour while
    non-sortable header labels were muted."""
    _make_stub(name="row-01")

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    header = page.locator("#stubs-table thead th").filter(
        has=page.get_by_role("link", name="Name")
    )
    cell_colour = header.evaluate("el => getComputedStyle(el).color")
    link_colour = header.get_by_role("link", name="Name").evaluate(
        "el => getComputedStyle(el).color"
    )

    assert link_colour == cell_colour
