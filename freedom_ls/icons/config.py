from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class IconsConfig(AppSettings):
    FREEDOM_LS_ICON_SET: str
    FREEDOM_LS_ICON_OVERRIDES: dict[str, str]
    FREEDOM_LS_ICON_BACKEND: str | None

    declared_settings = {
        "FREEDOM_LS_ICON_SET": Setting(default="heroicons"),
        "FREEDOM_LS_ICON_OVERRIDES": Setting(default={}),
        "FREEDOM_LS_ICON_BACKEND": Setting(default=None),
    }


config = IconsConfig()
