from __future__ import annotations

import copy
from typing import NamedTuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class Setting(NamedTuple):
    """One declared setting: its fallback value and whether the project must set it."""

    default: object = None
    required: bool = False


def project_value(name: str) -> object | None:
    """The project's value for setting ``name``, or None when it is unset.

    Strings are stripped, and None or "" count as unset.
    """
    value = getattr(settings, name, None)
    if isinstance(value, str):
        value = value.strip()
    return None if value in (None, "") else value


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
        value = project_value(name)
        if value is not None:
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
