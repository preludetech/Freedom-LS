from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class RoleBasedPermissionsConfig(AppSettings):
    FREEDOMLS_PERMISSIONS_MODULES: dict[str, str]

    declared_settings = {
        "FREEDOMLS_PERMISSIONS_MODULES": Setting(default={}),
    }


config = RoleBasedPermissionsConfig()
