from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class MetaPixelSettings(AppSettings):
    META_PIXEL_ID: str | None

    declared_settings = {
        # The pixel loads only when this is set and the visitor's country
        # allows it (freedom_ls.base.analytics_events.ad_pixels_allowed).
        "META_PIXEL_ID": Setting(default=None),
    }


config = MetaPixelSettings()
