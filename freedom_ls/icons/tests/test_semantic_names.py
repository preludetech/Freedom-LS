from collections.abc import Iterator

import pytest

from django.test import override_settings

from freedom_ls.icons.backend import get_icon_backend
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


@pytest.fixture(autouse=True)
def _clear_backend_cache() -> Iterator[None]:
    # get_icon_backend caches per process; each case below pins a different set.
    get_icon_backend.cache_clear()
    yield
    get_icon_backend.cache_clear()


@pytest.mark.parametrize("set_name", list(ICON_SETS))
def test_every_set_maps_every_semantic_name(set_name: str) -> None:
    missing = set(SEMANTIC_ICON_NAMES) - ICON_SETS[set_name].mapping.keys()
    assert not missing


@pytest.mark.parametrize("set_name", list(ICON_SETS))
@pytest.mark.parametrize("name", sorted(SEMANTIC_ICON_NAMES))
def test_every_semantic_name_renders_in_every_set(name: str, set_name: str) -> None:
    with override_settings(FREEDOM_LS_ICON_SET=set_name):
        assert "<svg" in get_icon_backend().render(name)
