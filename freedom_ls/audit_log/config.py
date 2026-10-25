from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class AuditLogSettings(AppSettings):
    AUDIT_LOG_EXTRA_ACTIONS: dict[str, str]
    AUDIT_LOG_RETENTION_DAYS: int | None

    declared_settings = {
        "AUDIT_LOG_EXTRA_ACTIONS": Setting(default={}),
        "AUDIT_LOG_RETENTION_DAYS": Setting(default=None),
    }


config = AuditLogSettings()
