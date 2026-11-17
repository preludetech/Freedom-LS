"""
App-level configuration for panel_framework.

Provides a `config` object that resolves settings by checking Django's
``settings`` first, then falling back to the defaults declared here.

Usage::

    from freedom_ls.panel_framework.config import config

    if count > config.BULK_BACKGROUND_THRESHOLD:
        # run the bulk action in a background task
"""

from __future__ import annotations

from freedom_ls.panel_framework.app_settings import AppSettings, Setting

__all__ = [
    "PanelFrameworkConfig",
    "config",
]


class PanelFrameworkConfig(AppSettings):
    BULK_BACKGROUND_THRESHOLD: int
    PANEL_TABLE_PAGE_SIZE: int

    declared_settings = {
        # A bulk action over more objects than this runs in a background task
        # instead of inside the request.
        "BULK_BACKGROUND_THRESHOLD": Setting(default=250),
        # Rows per page for a table that sets no `page_size` of its own.
        "PANEL_TABLE_PAGE_SIZE": Setting(default=10),
    }


config = PanelFrameworkConfig()
