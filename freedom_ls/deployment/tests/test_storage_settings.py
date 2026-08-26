from __future__ import annotations

from django.conf import settings

FILESYSTEM_BACKEND = "django.core.files.storage.FileSystemStorage"

EXPECTED_STORAGE_ALIASES = {
    "default",
    "staticfiles",
    "public",
    "course_media",
    "user_uploads",
    "reports",
    "certificates",
}


def test_storages_declares_all_seven_aliases() -> None:
    assert set(settings.STORAGES.keys()) == EXPECTED_STORAGE_ALIASES


def _filesystem_alias_locations() -> dict[str, object]:
    """Every FileSystemStorage-backed alias mapped to its declared OPTIONS location."""
    locations: dict[str, object] = {}
    for alias, entry in settings.STORAGES.items():
        if entry["BACKEND"] != FILESYSTEM_BACKEND:
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
