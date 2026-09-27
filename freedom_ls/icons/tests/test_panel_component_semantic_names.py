"""Tests verifying the panel-framework semantic icons are wired across all icon sets."""

from __future__ import annotations

import pytest

from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES

PANEL_COMPONENT_ICON_NAMES = ["add", "search", "filter", "trend_up", "trend_down"]

# tabler's installed iconify-json package ships no filled ("-filled") glyph for
# either trending arrow, the same gap several pre-existing mappings already
# have in TABLER_MAPPING (e.g. "next" -> "arrow-right" has no "arrow-right-filled"
# either). The base glyph still resolves and is what the components render by
# default, so only the solid-variant lookup is skipped here.
MISSING_TABLER_VARIANTS: dict[str, frozenset[str]] = {
    "trend_up": frozenset({"solid"}),
    "trend_down": frozenset({"solid"}),
}


@pytest.mark.parametrize("name", PANEL_COMPONENT_ICON_NAMES)
def test_name_is_a_semantic_name(name: str) -> None:
    assert name in SEMANTIC_ICON_NAMES


@pytest.mark.parametrize("name", PANEL_COMPONENT_ICON_NAMES)
@pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
def test_name_is_mapped_in_every_set(name: str, set_name: str) -> None:
    config = ICON_SETS[set_name]
    assert name in config.mapping, (
        f"icon set {set_name!r} is missing a mapping for {name!r}"
    )


@pytest.mark.parametrize("name", PANEL_COMPONENT_ICON_NAMES)
@pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
def test_glyph_and_variants_resolve(name: str, set_name: str) -> None:
    config = ICON_SETS[set_name]
    glyph = config.mapping[name]
    data = load_iconify_data(set_name)
    icons = data["icons"]
    assert glyph in icons, f"{set_name}: glyph {glyph!r} not in iconify JSON"
    for variant, suffix in config.variants.items():
        if suffix is None:
            continue
        if (
            variant in MISSING_TABLER_VARIANTS.get(name, frozenset())
            and set_name == "tabler"
        ):
            continue
        lookup = glyph + suffix
        assert lookup in icons, (
            f"{set_name}: variant {variant!r} requires {lookup!r} in iconify JSON"
        )
