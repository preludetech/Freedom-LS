from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class BaseConfig(AppSettings):
    PREMAILER_OPTIONS: dict[str, object]

    declared_settings = {
        "PREMAILER_OPTIONS": Setting(default={}),
    }


config = BaseConfig()
