from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting
from freedom_ls.base.notification_categories import (
    FLS_NOTIFICATION_CATEGORIES,
    NotificationCategory,
)


class CommsConfig(AppSettings):
    NOTIFICATIONS_ENABLED: bool
    NOTIFICATION_CATEGORIES: list[NotificationCategory]
    NOTIFICATION_DELIVERY_BACKENDS: list[str]
    NOTIFICATION_BADGE_POLL_SECONDS: int
    MESSAGING_POLICY: str

    declared_settings = {
        "NOTIFICATIONS_ENABLED": Setting(default=False),
        "NOTIFICATION_CATEGORIES": Setting(default=FLS_NOTIFICATION_CATEGORIES),
        "NOTIFICATION_DELIVERY_BACKENDS": Setting(default=[]),
        "NOTIFICATION_BADGE_POLL_SECONDS": Setting(default=45),
        "MESSAGING_POLICY": Setting(
            default="freedom_ls.messaging_policy.policy.LayeredMessagingPolicy"
        ),
    }


config = CommsConfig()
