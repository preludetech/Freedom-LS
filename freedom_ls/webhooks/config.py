from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting
from freedom_ls.base.webhook_event_types import FLS_WEBHOOK_EVENT_TYPES


class WebhooksConfig(AppSettings):
    WEBHOOK_EVENT_TYPES: list[tuple[str, str]]

    declared_settings = {
        "WEBHOOK_EVENT_TYPES": Setting(default=FLS_WEBHOOK_EVENT_TYPES),
    }


config = WebhooksConfig()
