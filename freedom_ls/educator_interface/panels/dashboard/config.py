"""The dashboard's section config."""

from __future__ import annotations

from freedom_ls.educator_interface.panels.common.request import (
    OrganisationSectionConfig,
)
from freedom_ls.educator_interface.panels.dashboard.panels import DashboardPanel
from freedom_ls.panel_framework.views import BaseViewConfig

__all__ = ["DashboardConfig"]


class DashboardConfig(OrganisationSectionConfig, BaseViewConfig):
    url_name = "dashboard"
    menu_label = "Dashboard"
    icon = "home"
    panel = DashboardPanel
