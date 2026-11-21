"""The bundled icon data under `freedom_ls/icons/data/` is complete, licensed and small.

It reads only `BUNDLED_DATA_DIR`, so it needs no `node_modules` and runs standalone.
"""

import json
from pathlib import Path
from typing import TypedDict

import pytest

from freedom_ls.icons.loader import BUNDLED_DATA_DIR, PACKAGE_MAP
from freedom_ls.icons.mappings import ICON_SETS, required_glyphs

MAX_FILE_BYTES = 1_000_000


class ManifestEntry(TypedDict):
    package: str
    version: str
    license: str
    license_url: str
    glyphs: list[str]
    missing_glyphs: list[str]


def manifest() -> dict[str, ManifestEntry]:
    data: dict[str, ManifestEntry] = json.loads(
        (BUNDLED_DATA_DIR / "manifest.json").read_text()
    )
    return data


def set_dir(set_name: str) -> Path:
    return BUNDLED_DATA_DIR / PACKAGE_MAP[set_name]


def test_manifest_lists_exactly_the_icon_sets() -> None:
    assert sorted(manifest()) == sorted(ICON_SETS)


@pytest.mark.parametrize("set_name", list(ICON_SETS))
class TestBundledSet:
    def test_icons_plus_missing_glyphs_equal_the_required_glyphs(
        self, set_name: str
    ) -> None:
        icons = json.loads((set_dir(set_name) / "icons.json").read_text())["icons"]
        missing = manifest()[set_name]["missing_glyphs"]

        assert set(icons) | set(missing) == required_glyphs(set_name)

    def test_missing_glyphs_are_absent_from_the_icons_file(self, set_name: str) -> None:
        icons = json.loads((set_dir(set_name) / "icons.json").read_text())["icons"]
        missing = manifest()[set_name]["missing_glyphs"]

        assert set(icons) & set(missing) == set()

    def test_manifest_glyph_list_matches_the_icons_file(self, set_name: str) -> None:
        icons = json.loads((set_dir(set_name) / "icons.json").read_text())["icons"]

        assert manifest()[set_name]["glyphs"] == sorted(icons)

    def test_manifest_records_a_version(self, set_name: str) -> None:
        assert manifest()[set_name]["version"]

    def test_licence_file_is_not_empty(self, set_name: str) -> None:
        licence = set_dir(set_name) / "LICENSE"

        assert licence.stat().st_size > 0

    def test_icons_file_is_under_one_megabyte(self, set_name: str) -> None:
        icons_file = set_dir(set_name) / "icons.json"

        assert icons_file.stat().st_size < MAX_FILE_BYTES


def test_manifest_is_under_one_megabyte() -> None:
    assert (BUNDLED_DATA_DIR / "manifest.json").stat().st_size < MAX_FILE_BYTES
