"""Browser flow for the component reference page.

The isolated test URLconf carries no allauth login page, so the flow cannot
drive a UI login. A `Client` signs in server-side and its session cookie is
added to this test's browser context only; nothing is shared between tests.
"""

from __future__ import annotations

import io
import re

import pytest
import pytest_django.live_server_helper
from PIL import Image
from playwright.sync_api import Page, expect

from django.conf import settings
from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from ..helpers import make_staff_user

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE_MAX_WIDTH = 640
_RGB_PATTERN = re.compile(r"rgb\((\d+), (\d+), (\d+)\)")

_RESOLVE_PRIMARY_COLOUR = """() => {
    const probe = document.createElement('div');
    probe.style.backgroundColor = 'var(--color-primary)';
    document.body.appendChild(probe);
    const colour = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return colour;
}"""


def _sign_in_as_staff(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer
) -> None:
    staff_client = Client()
    staff_client.force_login(make_staff_user())
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": staff_client.cookies[settings.SESSION_COOKIE_NAME].value,
                "url": live_server.url,
            }
        ]
    )


def test_component_reference_flow(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: Site,
) -> None:
    _sign_in_as_staff(page, live_server)

    page.goto(f"{live_server.url}/test-panel/components/")

    # A rejected cookie would land on the admin login instead.
    expect(page).to_have_url(re.compile(r"/test-panel/components/$"))
    # `> h2` excludes the card examples' own titles, which are nested in cards.
    expect(page.locator("section > h2")).to_have_count(12)

    # The progress bar's fill is the primary colour, not the browser default.
    # Chromium drops a whole CSS rule when one selector in a list uses an
    # unknown pseudo-element, and getComputedStyle does not resolve the native
    # <progress> shadow pseudo-elements, so this samples the painted pixel.
    progress = page.locator("#progress-bar-default progress")
    expect(progress).to_be_visible()
    # The example renders at 42%, so the left edge sits inside the fill.
    image = Image.open(io.BytesIO(progress.screenshot())).convert("RGB")
    left_edge_pixel = image.getpixel((2, image.size[1] // 2))
    match = _RGB_PATTERN.match(page.evaluate(_RESOLVE_PRIMARY_COLOUR))
    assert match is not None
    assert left_edge_pixel == tuple(int(part) for part in match.groups())

    # A progress bar inside a stat tile keeps a usable width. The global `dl`
    # rule's `align-items: baseline` once collapsed it to nothing.
    tile_progress = page.locator("#stat-tile-with-progress progress")
    expect(tile_progress).to_be_visible()
    box = tile_progress.bounding_box()
    assert box is not None
    assert box["width"] > 50

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
        if viewport["width"] >= _PHONE_MAX_WIDTH:
            continue

        # Below md the row's link stretches over the whole <li> via ::after,
        # so the reason text is not the topmost element at its own point;
        # force skips the obscured-element check, which is the tap-target
        # behaviour being proved.
        page.locator("#attention-list-default li").first.get_by_text(
            "4 days idle"
        ).click(force=True)
        expect(page).to_have_url(re.compile(r"#attention-row-target$"))

        header = page.locator("#page-header-with-actions")
        heading_box = header.locator("h1").bounding_box()
        action_box = header.get_by_role("link", name="Add learner").bounding_box()
        assert heading_box is not None
        assert action_box is not None
        assert action_box["y"] > heading_box["y"] + heading_box["height"]
