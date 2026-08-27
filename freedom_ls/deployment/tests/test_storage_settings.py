from __future__ import annotations

from django.conf import settings

from freedom_ls.deployment.tests.conftest import EXPECTED_ALIASES

#: Every alias that writes to disk uses the stock backend; the one that overwrites
#: differs only in an OPTIONS flag, so the location invariant below covers it too.
FILESYSTEM_BACKENDS = {"django.core.files.storage.FileSystemStorage"}


def test_storages_declares_all_seven_aliases() -> None:
    assert set(settings.STORAGES.keys()) == EXPECTED_ALIASES


def _filesystem_alias_locations() -> dict[str, object]:
    """Every FileSystemStorage-backed alias mapped to its declared OPTIONS location."""
    locations: dict[str, object] = {}
    for alias, entry in settings.STORAGES.items():
        if entry["BACKEND"] not in FILESYSTEM_BACKENDS:
            continue
        options = entry.get("OPTIONS")
        locations[alias] = (
            options.get("location") if isinstance(options, dict) else None
        )
    return locations


def test_no_filesystem_backed_alias_pins_a_location() -> None:
    locations = _filesystem_alias_locations()

    assert locations
    assert set(locations.values()) == {None}
