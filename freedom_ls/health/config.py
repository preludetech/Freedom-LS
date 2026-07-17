from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class HealthConfig(AppSettings):
    HEALTH_READINESS_CHECKS: list[str]

    declared_settings = {
        "HEALTH_READINESS_CHECKS": Setting(default=["health_check.checks.Database"]),
    }


config = HealthConfig()
