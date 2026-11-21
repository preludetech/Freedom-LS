"""Tests for the icon system Django system checks."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from django.apps import apps
from django.core.checks import run_checks
from django.test import override_settings

from freedom_ls.icons.checks import (
    check_deprecated_settings,
    check_iconify_json_exists,
    check_mapping_values_exist,
    check_overrides_exist,
    check_variant_support,
)
from freedom_ls.icons.loader import _cache


@pytest.fixture(autouse=True)
def _clear_loader_cache() -> Iterator[None]:
    _cache.clear()
    yield
    _cache.clear()


class TestCheckIconifyJsonExists:
    def test_valid_config_no_errors(self) -> None:
        errors = check_iconify_json_exists()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_SET="nonexistent_set")
    def test_unknown_set_produces_e001(self) -> None:
        errors = check_iconify_json_exists()
        assert len(errors) == 1
        assert errors[0].id == "icons.E001"

    @override_settings(SEMANTIC_ICONS_SET="heroicons")
    def test_missing_json_file_produces_e002(self) -> None:
        with patch("freedom_ls.icons.checks.iconify_json_path") as mock_path:
            mock_path.return_value.exists.return_value = False
            errors = check_iconify_json_exists()
        assert len(errors) == 1
        assert errors[0].id == "icons.E002"


class TestCheckMappingValuesExist:
    def test_valid_config_no_errors(self) -> None:
        errors = check_mapping_values_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_SET="heroicons")
    def test_heroicons_mappings_valid(self) -> None:
        errors = check_mapping_values_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_SET="heroicons")
    def test_variant_suffixed_names_are_validated(self) -> None:
        """Variant-suffixed names ("bell-solid") must resolve in the icon JSON too."""
        errors = check_mapping_values_exist()

        assert errors == []


class TestCheckOverridesExist:
    def test_no_overrides_no_errors(self) -> None:
        errors = check_overrides_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_OVERRIDES={"success": "star"})
    def test_valid_override_no_errors(self) -> None:
        errors = check_overrides_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_OVERRIDES={"success": "nonexistent-icon-xyz"})
    def test_bad_override_value_produces_e006(self) -> None:
        errors = check_overrides_exist()
        assert any(e.id == "icons.E006" for e in errors)

    @override_settings(SEMANTIC_ICONS_OVERRIDES={"not_a_semantic_name": "star"})
    def test_bad_override_key_produces_e005(self) -> None:
        errors = check_overrides_exist()
        assert any(e.id == "icons.E005" for e in errors)


class TestCheckVariantSupport:
    @override_settings(SEMANTIC_ICONS_SET="heroicons")
    def test_heroicons_supports_common_variants(self) -> None:
        warnings = check_variant_support()
        assert warnings == []

    @override_settings(SEMANTIC_ICONS_SET="lucide")
    def test_lucide_warns_about_solid_variant(self) -> None:
        warnings = check_variant_support()
        assert any(w.id == "icons.W001" for w in warnings)
        assert any("solid" in w.msg for w in warnings)


DEPRECATED_NAMES = [
    ("FREEDOM_LS_ICON_SET", "SEMANTIC_ICONS_SET", "icons.W002"),
    ("FREEDOM_LS_ICON_OVERRIDES", "SEMANTIC_ICONS_OVERRIDES", "icons.W003"),
    ("FREEDOM_LS_ICON_BACKEND", "SEMANTIC_ICONS_BACKEND", "icons.W004"),
]


@pytest.mark.parametrize(("old_name", "new_name", "check_id"), DEPRECATED_NAMES)
def test_an_old_name_gives_one_warning_with_its_id(
    old_name: str, new_name: str, check_id: str
) -> None:
    with override_settings(**{new_name: None, old_name: "heroicons"}):
        found = check_deprecated_settings()

    assert [message.id for message in found] == [check_id]


@pytest.mark.parametrize(("old_name", "new_name", "check_id"), DEPRECATED_NAMES)
def test_the_warning_message_names_the_replacement(
    old_name: str, new_name: str, check_id: str
) -> None:
    with override_settings(**{new_name: None, old_name: "heroicons"}):
        found = check_deprecated_settings()

    assert found[0].msg == f"{old_name} is deprecated; use {new_name}."


@pytest.mark.parametrize(("old_name", "new_name", "check_id"), DEPRECATED_NAMES)
def test_the_message_says_the_old_name_is_ignored_when_both_are_set(
    old_name: str, new_name: str, check_id: str
) -> None:
    with override_settings(**{new_name: "heroicons", old_name: "heroicons"}):
        found = check_deprecated_settings()

    assert found[0].msg == (
        f"{old_name} is deprecated; use {new_name}. "
        f"{old_name} is ignored because {new_name} is set."
    )


@pytest.mark.parametrize(("old_name", "new_name", "check_id"), DEPRECATED_NAMES)
def test_the_hint_gives_the_rename_the_removal_and_the_id(
    old_name: str, new_name: str, check_id: str
) -> None:
    with override_settings(**{new_name: None, old_name: "heroicons"}):
        found = check_deprecated_settings()

    assert found[0].hint == (
        f"Rename the setting: {new_name} = <your value>. {old_name} is removed "
        f"in the next tag. To silence this warning, add '{check_id}' to "
        "SILENCED_SYSTEM_CHECKS."
    )


@pytest.mark.django_db
def test_default_settings_produce_no_icons_check_output() -> None:
    # Checks that are not tied to a model run whatever app_configs says, so other apps'
    # messages are filtered out by id prefix.
    found = run_checks(app_configs=[apps.get_app_config("icons")])

    assert [
        message for message in found if (message.id or "").startswith("icons.")
    ] == []
