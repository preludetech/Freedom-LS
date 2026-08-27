from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import InvalidStorageError, Storage, storages


def storage_for_alias(alias: str, setting_name: str) -> Storage:
    """The named STORAGES alias, or a message saying which setting named it.

    Every ``storage=`` callable goes through here. Django resolves those callables
    at class definition, so an alias missing from STORAGES raises while the app
    registry is still importing models — the process never starts, and the bare
    InvalidStorageError names neither the setting that chose the alias nor the
    dict that has to declare it.
    """
    try:
        return storages[alias]
    except InvalidStorageError as err:
        raise ImproperlyConfigured(
            f"settings.STORAGES has no {alias!r} entry, named by {setting_name}. "
            f"Declare {alias!r} in settings.STORAGES, or rebuild the dict with "
            f"build_storages()."
        ) from err
