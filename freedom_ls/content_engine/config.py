from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class ContentEngineConfig(AppSettings):
    COURSE_ACCESS_CONFIG_VALIDATOR: str | None
    ADMONITION_TYPES: dict[str, dict[str, str]]
    COTTON_SNAKE_CASED_NAMES: bool

    declared_settings = {
        "COURSE_ACCESS_CONFIG_VALIDATOR": Setting(default=None),
        # No safe empty default: the consumer reads registry["default"], so an
        # unset registry would KeyError. Required, and surfaced by checks.py.
        "ADMONITION_TYPES": Setting(required=True),
        # No FLS consumer reads this: django-cotton reads it itself. Declared
        # here purely so it appears in the ownership map for this app.
        "COTTON_SNAKE_CASED_NAMES": Setting(default=False),
    }


config = ContentEngineConfig()
