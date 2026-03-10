"""Tests for the icon registry in freedom_ls.base.icons."""

from freedom_ls.base.icons import ICONS


class TestIconRegistry:
    """Tests for the ICONS dictionary."""

    def test_all_values_are_non_empty_strings(self) -> None:
        for key, value in ICONS.items():
            assert isinstance(value, str), f"ICONS[{key!r}] is not a string"
            assert value != "", f"ICONS[{key!r}] is an empty string"

    def test_all_values_map_to_valid_heroicon_names(self) -> None:
        """Every value in ICONS should be a valid heroicon name that exists
        in the heroicons package's bundled SVG data."""
        from contextlib import closing
        from importlib.resources import files
        from zipfile import ZipFile

        zip_data = (files("heroicons") / "heroicons.zip").open("rb")
        with closing(zip_data), ZipFile(zip_data, "r") as zf:
            available = {
                name.split("/")[1].removesuffix(".svg")
                for name in zf.namelist()
                if name.startswith("outline/") and name.endswith(".svg")
            }

        for key, value in ICONS.items():
            assert value in available, (
                f"ICONS[{key!r}] = {value!r} is not a valid heroicon name"
            )

    def test_values_are_not_all_the_same(self) -> None:
        unique_values = set(ICONS.values())
        assert len(unique_values) > 1, "All ICONS values are the same"

    def test_registry_is_not_empty(self) -> None:
        assert len(ICONS) > 0

    def test_loading_icon_exists(self) -> None:
        """The loading icon is required by the <c-button> loading prop."""
        assert "loading" in ICONS
