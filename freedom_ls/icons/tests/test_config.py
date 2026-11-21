"""Tests for the icons settings reader and its fallback to the old setting names."""

from __future__ import annotations

import warnings

import pytest

from django.test import override_settings

from freedom_ls.icons.app_settings import project_value
from freedom_ls.icons.config import IconsConfig

RENAMED = [
    ("SEMANTIC_ICONS_SET", "FREEDOM_LS_ICON_SET", "lucide", "tabler", "heroicons"),
    (
        "SEMANTIC_ICONS_OVERRIDES",
        "FREEDOM_LS_ICON_OVERRIDES",
        {"success": "star"},
        {"success": "check"},
        {},
    ),
    (
        "SEMANTIC_ICONS_BACKEND",
        "FREEDOM_LS_ICON_BACKEND",
        "a.b.OldBackend",
        "a.b.NewBackend",
        None,
    ),
]
RENAMED_PARAMS = ("new_name", "old_name", "old_value", "new_value", "default")


@pytest.mark.parametrize(RENAMED_PARAMS, RENAMED)
def test_new_name_alone_is_returned(
    new_name: str, old_name: str, old_value: object, new_value: object, default: object
) -> None:
    config = IconsConfig()

    with override_settings(**{new_name: new_value}):
        assert getattr(config, new_name) == new_value


@pytest.mark.parametrize(RENAMED_PARAMS, RENAMED)
def test_old_name_alone_is_returned(
    new_name: str, old_name: str, old_value: object, new_value: object, default: object
) -> None:
    config = IconsConfig()

    with override_settings(**{new_name: None, old_name: old_value}):
        assert getattr(config, new_name) == old_value


@pytest.mark.parametrize(RENAMED_PARAMS, RENAMED)
def test_new_name_wins_when_both_are_set(
    new_name: str, old_name: str, old_value: object, new_value: object, default: object
) -> None:
    config = IconsConfig()

    with override_settings(**{old_name: old_value, new_name: new_value}):
        assert getattr(config, new_name) == new_value


@pytest.mark.parametrize(RENAMED_PARAMS, RENAMED)
def test_default_applies_when_neither_name_is_set(
    new_name: str, old_name: str, old_value: object, new_value: object, default: object
) -> None:
    config = IconsConfig()

    assert getattr(config, new_name) == default


@pytest.mark.parametrize(RENAMED_PARAMS, RENAMED)
def test_whitespace_only_new_value_falls_back_to_old_name(
    new_name: str, old_name: str, old_value: object, new_value: object, default: object
) -> None:
    config = IconsConfig()

    with override_settings(**{new_name: "   ", old_name: old_value}):
        assert getattr(config, new_name) == old_value


def test_undeclared_name_raises_attribute_error() -> None:
    config = IconsConfig()

    with pytest.raises(AttributeError):
        _ = config.SEMANTIC_ICONS_NOT_DECLARED


@pytest.mark.parametrize(
    ("new_name", "old_name"),
    [
        ("SEMANTIC_ICONS_SET", "FREEDOM_LS_ICON_SET"),
        ("SEMANTIC_ICONS_OVERRIDES", "FREEDOM_LS_ICON_OVERRIDES"),
        ("SEMANTIC_ICONS_BACKEND", "FREEDOM_LS_ICON_BACKEND"),
    ],
)
def test_fallback_read_raises_no_python_warning(new_name: str, old_name: str) -> None:
    config = IconsConfig()

    with (
        override_settings(**{new_name: None, old_name: "heroicons"}),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("error")
        value = getattr(config, new_name)

    assert value == "heroicons"


@pytest.mark.parametrize("unset_value", ["  ", "", None])
def test_old_name_fallback_applies_exactly_when_app_settings_returns_the_default(
    unset_value: str | None,
) -> None:
    config = IconsConfig()

    with override_settings(
        SEMANTIC_ICONS_SET=unset_value, FREEDOM_LS_ICON_SET="lucide"
    ):
        assert config.SEMANTIC_ICONS_SET == "lucide"


@pytest.mark.parametrize("unset_value", ["  ", "", None])
def test_project_value_is_none_for_unset_values(unset_value: str | None) -> None:
    with override_settings(SEMANTIC_ICONS_SET=unset_value):
        assert project_value("SEMANTIC_ICONS_SET") is None


def test_project_value_strips_a_set_string() -> None:
    with override_settings(SEMANTIC_ICONS_SET="  tabler  "):
        assert project_value("SEMANTIC_ICONS_SET") == "tabler"
