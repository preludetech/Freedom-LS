"""E2E Playwright tests for the #quick-view drawer/sheet layout and print rule.

Covers the docked drawer's bounding box from 1280px up (pinned to the
inline-end edge, full height, about 30rem wide) and the room the page content
makes for it, the side drawer laid over the page between 768px and 1280px, the mobile
sheet's bounding box (full width, anchored to the viewport bottom), and that
the dialog does not render under print media. Interaction behaviour lives in
test_quick_view_htmx.py and test_quick_view_mobile_htmx.py.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub

_DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
_TABLET_VIEWPORT = {"width": 1024, "height": 800}
_MOBILE_VIEWPORT = {"width": 375, "height": 750}


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_docked_drawer_is_pinned_full_height_to_the_inline_end_edge(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    make_stub(name="Alpha")
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Quick view: Alpha").click()
    expect(page.locator("#quick-view")).to_be_visible()
    # The slide-in transform transitions over 200ms, so wait for it to settle
    # before measuring the box, or the read races the animation.
    expect(page.locator("#quick-view")).to_have_css("transform", "none")

    box = page.locator("#quick-view").bounding_box()
    assert box is not None
    assert box["x"] + box["width"] == pytest.approx(_DESKTOP_VIEWPORT["width"], abs=1)
    assert box["width"] == pytest.approx(480, abs=2)
    assert box["y"] == pytest.approx(0, abs=1)
    assert box["height"] == pytest.approx(_DESKTOP_VIEWPORT["height"], abs=1)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_page_content_makes_room_for_the_docked_drawer(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    make_stub(name="Alpha")
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Quick view: Alpha").click()
    expect(page.locator("#quick-view")).to_have_css("transform", "none")

    drawer_box = page.locator("#quick-view").bounding_box()
    table_box = page.locator("#main-content table").bounding_box()
    create_box = page.get_by_role("button", name="Create Item").bounding_box()
    assert drawer_box is not None
    assert table_box is not None
    assert create_box is not None
    assert table_box["x"] + table_box["width"] <= drawer_box["x"]
    assert create_box["x"] + create_box["width"] <= drawer_box["x"]


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_below_1280_the_drawer_lies_over_the_page_below_the_header(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """Too narrow to dock beside the page, but wide enough to stay a side
    drawer rather than the phone's bottom sheet. It starts below the site
    header so the header stays usable, like the docked drawer."""
    make_stub(name="Alpha")
    page.set_viewport_size(_TABLET_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Quick view: Alpha").click()
    expect(page.locator("#quick-view")).to_have_css("transform", "none")

    expect(page.locator("dialog:modal")).to_have_count(0)
    # --sidebar-top is the site header's height, set by sidePanel.
    header_bottom = page.evaluate(
        "parseFloat(getComputedStyle(document.querySelector('#quick-view'))"
        ".getPropertyValue('--sidebar-top')) || 0"
    )
    box = page.locator("#quick-view").bounding_box()
    assert box is not None
    assert box["x"] + box["width"] == pytest.approx(_TABLET_VIEWPORT["width"], abs=1)
    assert box["width"] == pytest.approx(480, abs=2)
    assert box["y"] == pytest.approx(header_bottom, abs=1)
    assert box["y"] + box["height"] == pytest.approx(_TABLET_VIEWPORT["height"], abs=1)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_mobile_sheet_spans_the_full_width_anchored_to_the_bottom(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    make_stub(name="Alpha")
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Quick view: Alpha").click()
    # The slide-up transform transitions over 200ms, so wait for it to settle
    # before measuring the box, or the read races the animation.
    expect(page.locator("#quick-view")).to_have_css("transform", "none")

    expect(page.locator("dialog:modal")).to_have_count(0)
    box = page.locator("#quick-view").bounding_box()
    assert box is not None
    assert box["x"] == pytest.approx(0, abs=1)
    assert box["width"] == pytest.approx(_MOBILE_VIEWPORT["width"], abs=1)
    assert box["y"] + box["height"] == pytest.approx(_MOBILE_VIEWPORT["height"], abs=1)
    # Half the screen at most, so the page above stays in view.
    assert box["height"] <= _MOBILE_VIEWPORT["height"] / 2 + 1


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_drawer_is_not_displayed_under_print_media(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    make_stub(name="Alpha")
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Quick view: Alpha").click()
    expect(page.locator("#quick-view")).to_be_visible()

    page.emulate_media(media="print")

    display = page.locator("#quick-view").evaluate("el => getComputedStyle(el).display")
    assert display == "none"
