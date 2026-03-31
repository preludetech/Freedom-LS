from collections.abc import Iterator

import pytest

from freedom_ls.icons.loader import _cache, load_iconify_data


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    _cache.clear()
    yield
    _cache.clear()


class TestLoadIconifyData:
    def test_returns_dict_with_icons_key(self) -> None:
        data = load_iconify_data("heroicons")
        assert isinstance(data, dict)
        assert "icons" in data

    def test_known_icon_exists(self) -> None:
        data = load_iconify_data("heroicons")
        assert "check-circle" in data["icons"]

    def test_unknown_set_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown icon set"):
            load_iconify_data("nonexistent")

    def test_caching_returns_same_object(self) -> None:
        first = load_iconify_data("heroicons")
        second = load_iconify_data("heroicons")
        assert first is second

    def test_all_sets_loadable(self) -> None:
        for set_name in ("heroicons", "lucide", "tabler", "phosphor"):
            data = load_iconify_data(set_name)
            assert "icons" in data
            assert len(data["icons"]) > 0
