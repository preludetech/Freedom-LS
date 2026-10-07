"""E2E tests for how a sortable column's header link is styled."""

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


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_sort_icon_keeps_its_size_when_the_header_label_is_squeezed(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """When a narrow column made the header label wrap, the flex link
    squeezed the sort icon down to a dot."""
    _make_stub(name="row-01")

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    link = page.locator("#stubs-table thead").get_by_role("link", name="Name")
    link.evaluate("el => { el.style.width = '2rem'; }")
    icon_width = link.locator("svg").evaluate("el => el.getBoundingClientRect().width")

    assert icon_width == 16
