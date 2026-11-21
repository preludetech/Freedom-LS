import pytest

from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.mappings import ICON_SETS, IconSetConfig, required_glyphs
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


class TestMappingKeysMatchSemanticNames:
    @pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
    def test_mapping_keys_match(self, set_name: str) -> None:
        config = ICON_SETS[set_name]
        assert set(config.mapping.keys()) == SEMANTIC_ICON_NAMES


class TestMappingValuesExistInIconifyJson:
    def test_heroicons_values_exist(self) -> None:
        data = load_iconify_data("heroicons")
        icons = data["icons"]
        for semantic, icon_name in ICON_SETS["heroicons"].mapping.items():
            assert icon_name in icons, (
                f"Heroicons mapping[{semantic!r}] = {icon_name!r} not found in Iconify JSON"
            )

    def test_lucide_values_exist(self) -> None:
        data = load_iconify_data("lucide")
        icons = data["icons"]
        for semantic, icon_name in ICON_SETS["lucide"].mapping.items():
            assert icon_name in icons, (
                f"Lucide mapping[{semantic!r}] = {icon_name!r} not found in Iconify JSON"
            )

    def test_tabler_values_exist(self) -> None:
        data = load_iconify_data("tabler")
        icons = data["icons"]
        for semantic, icon_name in ICON_SETS["tabler"].mapping.items():
            assert icon_name in icons, (
                f"Tabler mapping[{semantic!r}] = {icon_name!r} not found in Iconify JSON"
            )

    def test_phosphor_values_exist(self) -> None:
        data = load_iconify_data("phosphor")
        icons = data["icons"]
        for semantic, icon_name in ICON_SETS["phosphor"].mapping.items():
            assert icon_name in icons, (
                f"Phosphor mapping[{semantic!r}] = {icon_name!r} not found in Iconify JSON"
            )


class TestVariantDicts:
    @pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
    def test_has_outline_variant(self, set_name: str) -> None:
        config = ICON_SETS[set_name]
        assert "outline" in config.variants
        assert config.variants["outline"] is None

    @pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
    def test_base_names_exist_in_iconify_json(self, set_name: str) -> None:
        """Every mapping value (base/outline name) must exist in the JSON."""
        data = load_iconify_data(set_name)
        icons = data["icons"]
        config = ICON_SETS[set_name]
        for semantic, icon_name in config.mapping.items():
            assert icon_name in icons, (
                f"{set_name} mapping[{semantic!r}] -> {icon_name!r} not in Iconify JSON"
            )


class TestQuickViewAndOpenPageAreDistinct:
    """One previews a record in place, the other leaves for the record's own
    page, so they must never share a glyph."""

    @pytest.mark.parametrize("set_name", list(ICON_SETS.keys()))
    def test_they_map_to_different_glyphs(self, set_name: str) -> None:
        mapping = ICON_SETS[set_name].mapping
        assert mapping["quick_view"] != mapping["open_page"]


class TestRequiredGlyphs:
    def test_set_without_suffixes_needs_only_the_mapped_glyphs(self) -> None:
        mapping_values = set(ICON_SETS["lucide"].mapping.values())

        result = required_glyphs("lucide")

        assert result == mapping_values

    def test_each_mapped_glyph_is_paired_with_every_variant_suffix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small_set = IconSetConfig(
            mapping={"home": "house", "close": "x"},
            variants={"outline": None, "solid": "-solid", "mini": "-mini"},
        )
        monkeypatch.setitem(ICON_SETS, "small", small_set)

        result = required_glyphs("small")

        assert result == {
            "house",
            "x",
            "house-solid",
            "x-solid",
            "house-mini",
            "x-mini",
        }

    def test_unknown_set_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            required_glyphs("no-such-set")
