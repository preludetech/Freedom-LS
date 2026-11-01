from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class ApiConfig(AppSettings):
    API_THROTTLE_RATE: str
    API_PAGE_SIZE: int
    API_MAX_PAGE_SIZE: int

    declared_settings = {
        "API_THROTTLE_RATE": Setting(default="600/min"),
        "API_PAGE_SIZE": Setting(default=100),
        "API_MAX_PAGE_SIZE": Setting(default=500),
    }


config = ApiConfig()
