"""Plain helpers for educator_interface's Playwright tests, imported by hand
the way panel_framework/tests/view_helpers.py is.
"""

from __future__ import annotations

import pytest_django.live_server_helper

from django.urls import reverse


def interface_url(
    live_server: pytest_django.live_server_helper.LiveServer,
    organisation_slug: str,
    path_string: str,
) -> str:
    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )
    return f"{live_server.url}{path}"
