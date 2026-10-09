"""The progress bar's fill colour, proved in a real Chromium engine.

Chromium drops an entire CSS rule when any selector in a comma-separated
list uses a pseudo-element it doesn't recognise (``::-moz-progress-bar``).
A source-level check can't see that — it has to be proved against what
Chromium actually paints. `getComputedStyle(el, '::-webkit-progress-value')`
doesn't resolve reliably for a native `<progress>`'s UA shadow
pseudo-elements in this Playwright/Chromium build (it silently falls back
to the host element's own computed style), so this samples the rendered
pixel colour instead — the same signal a human eyeballing the bug report's
screenshot would use.

The isolated test URLconf carries no allauth login page, so the usual
`logged_in_page` fixture cannot drive a UI login here. Instead, a `Client`
signs in server-side and its session cookie rides along into the browser
context — the same technique `test_component_reference.py` uses.
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

from ..helpers import make_staff_user

_RGB_PATTERN = re.compile(r"rgb\((\d+), (\d+), (\d+)\)")

_RESOLVE_PRIMARY_COLOUR = """() => {
    const probe = document.createElement('div');
    probe.style.backgroundColor = 'var(--color-primary)';
    document.body.appendChild(probe);
    const colour = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return colour;
}"""


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_progress_bar_fill_matches_primary_colour_not_browser_default(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: Site,
    page: Page,
) -> None:
    staff_client = Client()
    staff_client.force_login(make_staff_user())
    session_key = staff_client.cookies[settings.SESSION_COOKIE_NAME].value
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": session_key,
                "url": live_server.url,
            }
        ]
    )

    page.goto(f"{live_server.url}/test-panel/components/")
    progress = page.locator("#progress-bar-default progress")
    expect(progress).to_be_visible()

    # The example renders at 42%, so the left edge of the bar sits inside
    # the filled portion.
    png = progress.screenshot()
    image = Image.open(io.BytesIO(png)).convert("RGB")
    left_edge_pixel = image.getpixel((2, image.size[1] // 2))

    # Resolve --color-primary on a scratch element rather than hardcoding
    # its value, so the assertion tracks the live theme token.
    primary_colour = page.evaluate(_RESOLVE_PRIMARY_COLOUR)
    match = _RGB_PATTERN.match(primary_colour)
    assert match is not None
    primary_rgb = tuple(int(component) for component in match.groups())

    assert left_edge_pixel == primary_rgb
