import asyncio

import pytest

from django.db import connections

from freedom_ls.tests.playwright_fixtures import (
    close_db_connections_before_playwright_stops,
)


@pytest.mark.django_db(transaction=True)
def test_closes_connection_opened_while_playwright_loop_is_current() -> None:
    # Arrange: mark a loop as running on this thread, as Playwright's sync API
    # does, so Django keeps the connection in contextvar storage.
    loop = asyncio.new_event_loop()
    asyncio._set_running_loop(loop)
    conn = connections["default"]
    try:
        conn.ensure_connection()

        # Act
        close_db_connections_before_playwright_stops()
        asyncio._set_running_loop(None)

        # Assert
        assert conn.connection is None
    finally:
        asyncio._set_running_loop(None)
        conn.close()
        loop.close()
