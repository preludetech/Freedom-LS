from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class OrganisationsConfig(AppSettings):
    ORGANISATION_LOGO_STORAGE_ALIAS: str

    declared_settings = {
        "ORGANISATION_LOGO_STORAGE_ALIAS": Setting(default="public"),
    }


config = OrganisationsConfig()
