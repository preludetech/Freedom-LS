from __future__ import annotations

from pathlib import Path

from django.conf import settings

from freedom_ls.icons.app_settings import AppSettings, Setting

# Each setting renamed in this tag, mapped to the name it replaces. The old names
# still work, with a system-check warning, until the next tag removes them.
DEPRECATED_SETTINGS: dict[str, str] = {
    "SEMANTIC_ICONS_SET": "FREEDOM_LS_ICON_SET",
    "SEMANTIC_ICONS_OVERRIDES": "FREEDOM_LS_ICON_OVERRIDES",
    "SEMANTIC_ICONS_BACKEND": "FREEDOM_LS_ICON_BACKEND",
}


def project_value(name: str) -> object | None:
    """The project's value for `name`, or None when it is unset.

    Uses AppSettings' rule for "set": strings are stripped, and None or "" count as unset.
    """
    value = getattr(settings, name, None)
    if isinstance(value, str):
        value = value.strip()
    return None if value in (None, "") else value


class IconsConfig(AppSettings):
    SEMANTIC_ICONS_SET: str
    SEMANTIC_ICONS_OVERRIDES: dict[str, str]
    SEMANTIC_ICONS_BACKEND: str | None
    SEMANTIC_ICONS_ICONIFY_DIR: str | Path | None

    declared_settings = {
        "SEMANTIC_ICONS_SET": Setting(default="heroicons"),
        "SEMANTIC_ICONS_OVERRIDES": Setting(default={}),
        "SEMANTIC_ICONS_BACKEND": Setting(default=None),
        "SEMANTIC_ICONS_ICONIFY_DIR": Setting(default=None),
    }

    def __getattr__(self, name: str) -> object:
        old_name = DEPRECATED_SETTINGS.get(name)
        if old_name is not None and project_value(name) is None:
            old_value = project_value(old_name)
            if old_value is not None:
                return old_value
        return super().__getattr__(name)


config = IconsConfig()
