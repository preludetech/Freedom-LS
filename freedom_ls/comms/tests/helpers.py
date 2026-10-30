"""Shared test helpers for `comms`."""

from __future__ import annotations

from freedom_ls.base.notification_categories import NotificationCategory

ROLLUP_TEST_CATEGORY = NotificationCategory(
    key="test.rolled_up",
    label="Rolled up",
    icon="message",
    message="Rolled up from %(sender_name)s",
    url_builder=None,
    rollup=True,
)
