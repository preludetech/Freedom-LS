from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class BaseConfig(AppSettings):
    PREMAILER_OPTIONS: dict[str, object]
    VISITOR_COUNTRY_HEADER: str | None

    declared_settings = {
        "PREMAILER_OPTIONS": Setting(default={}),
        # The header the fronting proxy sets to the visitor's ISO 3166-1
        # alpha-2 code, overwritten on every request. Unset means every
        # visitor is unknown and no ad pixel ever loads.
        "VISITOR_COUNTRY_HEADER": Setting(default=None),
    }


config = BaseConfig()
