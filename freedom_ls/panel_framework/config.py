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
    PANEL_FRAMEWORK_SITE_RESOLVER: str
    PANEL_REFERENCE_BASE_TEMPLATE: str

    declared_settings = {
        # A bulk action over more objects than this runs in a background task
        # instead of inside the request.
        "BULK_BACKGROUND_THRESHOLD": Setting(default=250),
        # Rows per page for a table that sets no `page_size` of its own.
        "PANEL_TABLE_PAGE_SIZE": Setting(default=10),
        # Dotted path of a callable that takes the request and returns its Site,
        # or None (or a RequestSite) for no site; what it raises propagates.
        # The default follows django.contrib.sites, where SITE_ID wins over the
        # request's host: a project serving several sites from one process must
        # set its own resolver, or every request shares one site's runs (W002).
        "PANEL_FRAMEWORK_SITE_RESOLVER": Setting(
            default="freedom_ls.panel_framework.sites.current_site_or_none"
        ),
        # The template the component reference page extends. It must define the
        # `head_title` and `content` blocks.
        "PANEL_REFERENCE_BASE_TEMPLATE": Setting(
            default="panel_framework/minimal_shell.html"
        ),
    }


config = PanelFrameworkConfig()
