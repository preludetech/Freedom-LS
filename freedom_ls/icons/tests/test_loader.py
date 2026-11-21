import json
from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper

from freedom_ls.icons.loader import (
    BUNDLED_DATA_DIR,
    PACKAGE_MAP,
    clear_cache,
    load_iconify_data,
    set_file,
)

from .helpers import write_icon_set

SET_NAMES = sorted(PACKAGE_MAP)


@pytest.mark.parametrize("set_name", SET_NAMES)
def test_bundled_data_only_loads_the_bundled_file(
    bundled_data_only: None, set_name: str
) -> None:
    expected = json.loads(set_file(BUNDLED_DATA_DIR, set_name).read_text())["icons"]

    data = load_iconify_data(set_name)

    assert data["icons"] == expected


def test_a_directory_entry_replaces_the_bundled_entry_of_the_same_name(
    iconify_dir: Path,
) -> None:
    write_icon_set(
        iconify_dir,
        "heroicons",
        {"width": 24, "height": 24, "icons": {"check-circle": {"body": "<path/>"}}},
    )

    data = load_iconify_data("heroicons")

    assert data["icons"]["check-circle"] == {"body": "<path/>"}


def test_a_directory_adds_a_glyph_the_bundled_data_lacks(iconify_dir: Path) -> None:
    write_icon_set(
        iconify_dir,
        "heroicons",
        {"width": 24, "height": 24, "icons": {"only-in-full": {"body": "<g/>"}}},
    )

    data = load_iconify_data("heroicons")

    assert data["icons"]["only-in-full"] == {"body": "<g/>"}
    assert "check-circle" in data["icons"]


def test_the_merged_root_size_is_the_bundled_files(iconify_dir: Path) -> None:
    write_icon_set(
        iconify_dir,
        "phosphor",
        {"width": 16, "height": 16, "icons": {"x": {"body": "<g/>"}}},
    )

    data = load_iconify_data("phosphor")

    assert (data["width"], data["height"]) == (256, 256)


def test_a_directory_entry_at_another_size_carries_that_size(
    iconify_dir: Path,
) -> None:
    write_icon_set(
        iconify_dir,
        "heroicons",
        {
            "width": 16,
            "height": 16,
            "icons": {
                "small": {"body": "<g/>"},
                "own": {"body": "<g/>", "width": 20, "height": 20},
            },
        },
    )

    data = load_iconify_data("heroicons")

    assert data["icons"]["small"] == {"body": "<g/>", "width": 16, "height": 16}
    assert data["icons"]["own"] == {"body": "<g/>", "width": 20, "height": 20}


def test_a_directory_entry_at_the_root_size_carries_no_size(
    iconify_dir: Path,
) -> None:
    write_icon_set(
        iconify_dir,
        "heroicons",
        {"width": 24, "height": 24, "icons": {"plain": {"body": "<g/>"}}},
    )

    data = load_iconify_data("heroicons")

    assert data["icons"]["plain"] == {"body": "<g/>"}


def test_a_set_the_directory_lacks_returns_the_bundled_data(
    iconify_dir: Path,
) -> None:
    write_icon_set(
        iconify_dir, "lucide", {"width": 24, "height": 24, "icons": {"x": {"body": ""}}}
    )
    expected = json.loads(set_file(BUNDLED_DATA_DIR, "heroicons").read_text())["icons"]

    data = load_iconify_data("heroicons")

    assert data["icons"] == expected


@pytest.mark.parametrize("kind", ["missing", "relative", "file"])
def test_an_unusable_directory_returns_the_bundled_data(
    settings: SettingsWrapper, tmp_path: Path, kind: str
) -> None:
    values = {
        "missing": tmp_path / "does-not-exist",
        "relative": Path("node_modules/@iconify-json"),
        "file": tmp_path / "a-file",
    }
    (tmp_path / "a-file").write_text("x")
    settings.SEMANTIC_ICONS_ICONIFY_DIR = values[kind]
    expected = json.loads(set_file(BUNDLED_DATA_DIR, "heroicons").read_text())["icons"]

    data = load_iconify_data("heroicons")

    assert data["icons"] == expected


def test_changing_the_directory_serves_the_new_directorys_data(
    settings: SettingsWrapper, tmp_path: Path
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_icon_set(first, "heroicons", {"icons": {"marker": {"body": "<one/>"}}})
    write_icon_set(second, "heroicons", {"icons": {"marker": {"body": "<two/>"}}})
    settings.SEMANTIC_ICONS_ICONIFY_DIR = first
    load_iconify_data("heroicons")
    settings.SEMANTIC_ICONS_ICONIFY_DIR = second

    data = load_iconify_data("heroicons")

    assert data["icons"]["marker"]["body"] == "<two/>"


def test_clearing_the_cache_makes_the_next_read_reread_the_file(
    iconify_dir: Path,
) -> None:
    path = write_icon_set(
        iconify_dir, "heroicons", {"icons": {"marker": {"body": "<one/>"}}}
    )
    load_iconify_data("heroicons")
    path.write_text(json.dumps({"icons": {"marker": {"body": "<two/>"}}}))
    clear_cache()

    data = load_iconify_data("heroicons")

    assert data["icons"]["marker"]["body"] == "<two/>"


def test_the_same_object_is_returned_twice_without_a_clear(
    bundled_data_only: None,
) -> None:
    first = load_iconify_data("heroicons")

    second = load_iconify_data("heroicons")

    assert first is second


def test_a_repeat_read_under_the_same_setting_does_not_touch_the_disk(
    iconify_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    load_iconify_data("heroicons")
    stats: list[Path] = []
    real_is_dir = Path.is_dir

    def spy_is_dir(self: Path) -> bool:
        stats.append(self)
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", spy_is_dir)

    load_iconify_data("heroicons")

    assert stats == []


def test_an_unknown_set_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown icon set"):
        load_iconify_data("nonexistent")
