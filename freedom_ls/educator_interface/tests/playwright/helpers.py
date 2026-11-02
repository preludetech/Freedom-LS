"""Plain helpers for educator_interface's Playwright tests, imported by hand
the way panel_framework/tests/view_helpers.py is.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest_django.live_server_helper
from playwright.sync_api import ConsoleMessage, Error, Page

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


@contextmanager
def no_console_errors(page: Page) -> Iterator[None]:
    """Fails the test if the page logged a console error or an uncaught
    exception while the block ran."""
    errors: list[str] = []

    def record(message: ConsoleMessage) -> None:
        if message.type == "error":
            errors.append(message.text)

    def record_exception(error: Error) -> None:
        errors.append(str(error))

    page.on("console", record)
    page.on("pageerror", record_exception)
    try:
        yield
    finally:
        page.remove_listener("console", record)
        page.remove_listener("pageerror", record_exception)
    assert errors == [], errors
