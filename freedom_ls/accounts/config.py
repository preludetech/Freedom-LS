from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class AccountsConfig(AppSettings):
    TRUSTED_PROXY_IP_HEADER: str | None
    REQUIRE_NAME: bool
    REQUIRE_TERMS_ACCEPTANCE: bool
    ADDITIONAL_REGISTRATION_FORMS: list[str]
    ALLOW_SIGN_UPS: bool
    LEGAL_DOCS_MANIFEST_PATH: str | None

    declared_settings = {
        "TRUSTED_PROXY_IP_HEADER": Setting(default=None),
        "REQUIRE_NAME": Setting(default=True),
        "REQUIRE_TERMS_ACCEPTANCE": Setting(default=False),
        "ADDITIONAL_REGISTRATION_FORMS": Setting(default=[]),
        "ALLOW_SIGN_UPS": Setting(default=True),
        "LEGAL_DOCS_MANIFEST_PATH": Setting(default=None),
    }


config = AccountsConfig()
