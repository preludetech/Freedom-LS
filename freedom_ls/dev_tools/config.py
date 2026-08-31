from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class DevToolsConfig(AppSettings):
    DEV_TOOLS_ENABLED: bool

    declared_settings = {
        "DEV_TOOLS_ENABLED": Setting(default=False),
    }


config = DevToolsConfig()
