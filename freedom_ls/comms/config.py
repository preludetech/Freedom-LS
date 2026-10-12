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
    MESSAGING_ENABLED: bool
    MESSAGE_MAX_LENGTH: int
    MESSAGE_PAGE_SIZE: int

    declared_settings = {
        "NOTIFICATIONS_ENABLED": Setting(default=False),
        "NOTIFICATION_CATEGORIES": Setting(default=FLS_NOTIFICATION_CATEGORIES),
        "NOTIFICATION_DELIVERY_BACKENDS": Setting(default=[]),
        "NOTIFICATION_BADGE_POLL_SECONDS": Setting(default=45),
        "MESSAGING_POLICY": Setting(
            default="freedom_ls.messaging_policy.policy.LayeredMessagingPolicy"
        ),
        "MESSAGING_ENABLED": Setting(default=False),
        "MESSAGE_MAX_LENGTH": Setting(default=2000),
        "MESSAGE_PAGE_SIZE": Setting(default=30),
    }


config = CommsConfig()
