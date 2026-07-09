from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class SiteAwareModelsConfig(AppSettings):
    FORCE_SITE_NAME: str | None
    HEADER_LOGO_STATIC_PATH: str | None
    FAVICON_STATIC_PATH: str | None
    HEADER_TITLE: str | None
    HEADER_TITLE_STYLE: str | None
    EMAIL_LOGO_STATIC_PATH: str | None

    declared_settings = {
        "FORCE_SITE_NAME": Setting(default=None),
        "HEADER_LOGO_STATIC_PATH": Setting(default=None),
        "FAVICON_STATIC_PATH": Setting(default=None),
        "HEADER_TITLE": Setting(default=None),
        "HEADER_TITLE_STYLE": Setting(default=None),
        "EMAIL_LOGO_STATIC_PATH": Setting(default=None),
    }


config = SiteAwareModelsConfig()
