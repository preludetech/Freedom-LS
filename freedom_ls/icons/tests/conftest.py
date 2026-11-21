from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper

from freedom_ls.icons.loader import clear_cache


@pytest.fixture(autouse=True)
def _fresh_icon_cache() -> Iterator[None]:
    """Empty the loader's cache around each test so no test sees another's data."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def bundled_data_only(settings: SettingsWrapper) -> None:
    """Render from the bundled data alone, whatever the project configures."""
    settings.SEMANTIC_ICONS_ICONIFY_DIR = None


@pytest.fixture
def iconify_dir(settings: SettingsWrapper, tmp_path: Path) -> Path:
    """An empty directory configured as SEMANTIC_ICONS_ICONIFY_DIR."""
    settings.SEMANTIC_ICONS_ICONIFY_DIR = tmp_path
    return tmp_path
