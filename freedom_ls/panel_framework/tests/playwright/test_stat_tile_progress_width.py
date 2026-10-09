"""A progress bar embedded in a stat tile keeps a usable width.

The global ``dl`` base rule sets ``align-items: baseline``; inside the
stat tile's column flexbox that shrinks the slot ``<dd>`` to its content
width, so the ``w-full`` progress track collapsed to nothing. Only a real
layout engine can show that. Sign-in follows the same server-side session
cookie technique as ``test_progress_bar_fill.py``.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.conf import settings
from django.contrib.sites.models import Site
from django.test import Client

from ..helpers import make_staff_user


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_progress_bar_inside_stat_tile_has_visible_width(
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
    progress = page.locator("#stat-tile-with-progress progress")
    expect(progress).to_be_visible()

    box = progress.bounding_box()
    assert box is not None
    assert box["width"] > 50
