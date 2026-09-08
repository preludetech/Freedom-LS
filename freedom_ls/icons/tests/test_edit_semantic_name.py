"""Tests verifying the 'edit' semantic icon is wired across all icon sets."""

from __future__ import annotations

import pytest

from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


def test_edit_is_a_semantic_name() -> None:
    assert "edit" in SEMANTIC_ICON_NAMES


@pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
def test_edit_is_mapped_in_every_set(set_name: str) -> None:
    config = ICON_SETS[set_name]
    assert "edit" in config.mapping, (
        f"icon set {set_name!r} is missing a mapping for 'edit'"
    )


@pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
def test_edit_glyph_and_variants_resolve(set_name: str) -> None:
    config = ICON_SETS[set_name]
    glyph = config.mapping["edit"]
    data = load_iconify_data(set_name)
    icons = data["icons"]
    assert glyph in icons, f"{set_name}: glyph {glyph!r} not in iconify JSON"
    for variant, suffix in config.variants.items():
        if suffix is None:
            continue
        lookup = glyph + suffix
        assert lookup in icons, (
            f"{set_name}: variant {variant!r} requires {lookup!r} in iconify JSON"
        )
