from __future__ import annotations

import copy
from typing import NamedTuple

from django.conf import settings
from django.core.checks import CheckMessage, Error
from django.core.exceptions import ImproperlyConfigured


class Setting(NamedTuple):
    """One declared setting: its fallback value and whether the project must set it."""

    default: object = None
    required: bool = False


class AppSettings:
    """Per-app settings: a project's Django settings override declared fallbacks.

    Each app subclass sets ``declared_settings`` to a ``{name: Setting(...)}`` map.
    ``config.NAME`` returns the project's value if set, else the declared default;
    a ``required`` setting the project has not supplied raises ImproperlyConfigured
    on read (lazily, never at import) as a runtime backstop. A caller that must not
    raise (e.g. a system check) wraps the read in ``try/except ImproperlyConfigured``.
    """

    declared_settings: dict[str, Setting] = {}

    def __getattr__(self, name: str) -> object:
        try:
            setting = self.declared_settings[name]
        except KeyError:
            raise AttributeError(name) from None
        value = getattr(settings, name, None)
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, ""):
            return value
        if setting.required:
            raise ImproperlyConfigured(
                f"{name} is required but is not set. "
                f"Set {name} in your Django settings."
            )
        # Copy so a caller mutating a mutable default (list/dict) in place cannot
        # corrupt the shared declared default for every later read.
        return copy.deepcopy(setting.default)

    def missing_required(self) -> list[str]:
        """Names of required settings the project has not supplied. Never raises."""
        missing: list[str] = []
        for name, setting in self.declared_settings.items():
            if not setting.required:
                continue
            try:
                getattr(self, name)
            except ImproperlyConfigured:
                missing.append(name)
        return missing


def required_settings_errors(config: AppSettings, app_label: str) -> list[CheckMessage]:
    """Build ``<app_label>.E001`` Errors for each missing required setting.

    The single reusable body every required-settings check calls, so no
    per-setting boilerplate is hand-written.
    """
    return [
        Error(
            f"{name} is required but is not set.",
            hint=f"Set {name} in your Django settings.",
            id=f"{app_label}.E001",
        )
        for name in config.missing_required()
    ]
