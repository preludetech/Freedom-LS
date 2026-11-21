"""Tests for the icon system Django system checks."""

from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper

from django.core.checks import CheckMessage
from django.core.checks.registry import registry
from django.test import override_settings

from freedom_ls.icons.checks import (
    check_deprecated_settings,
    check_iconify_dir,
    check_iconify_json_exists,
    check_mapping_values_exist,
    check_overrides_exist,
    check_variant_support,
)

from .helpers import write_icon_set


def _ids(messages: list[CheckMessage]) -> list[str | None]:
    return [message.id for message in messages]


class TestCheckIconifyDir:
    @pytest.mark.parametrize("kind", ["relative", "missing", "file"])
    def test_an_unusable_directory_produces_e008_naming_the_value(
        self, settings: SettingsWrapper, tmp_path: Path, kind: str
    ) -> None:
        (tmp_path / "a-file").write_text("x")
        values = {
            "relative": "node_modules/@iconify-json",
            "missing": str(tmp_path / "does-not-exist"),
            "file": str(tmp_path / "a-file"),
        }
        settings.SEMANTIC_ICONS_ICONIFY_DIR = values[kind]

        errors = check_iconify_dir()

        assert _ids(errors) == ["icons.E008"]
        assert repr(values[kind]) in errors[0].msg

    def test_an_unset_directory_is_silent(self, bundled_data_only: None) -> None:
        assert check_iconify_dir() == []

    def test_a_valid_directory_is_silent(self, iconify_dir: Path) -> None:
        assert check_iconify_dir() == []


class TestCheckIconifyJsonExists:
    def test_valid_config_no_errors(self, bundled_data_only: None) -> None:
        errors = check_iconify_json_exists()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_SET="nonexistent_set")
    def test_unknown_set_produces_e001(self) -> None:
        errors = check_iconify_json_exists()
        assert len(errors) == 1
        assert errors[0].id == "icons.E001"

    def test_a_usable_directory_without_the_active_sets_file_produces_e002(
        self, iconify_dir: Path, settings: SettingsWrapper
    ) -> None:
        settings.SEMANTIC_ICONS_SET = "heroicons"

        errors = check_iconify_json_exists()

        assert _ids(errors) == ["icons.E002"]
        assert str(iconify_dir / "heroicons" / "icons.json") in errors[0].msg
        assert "SEMANTIC_ICONS_ICONIFY_DIR" in (errors[0].hint or "")

    def test_a_usable_directory_with_the_file_is_silent(
        self, iconify_dir: Path, settings: SettingsWrapper
    ) -> None:
        settings.SEMANTIC_ICONS_SET = "heroicons"
        write_icon_set(iconify_dir, "heroicons", {"icons": {}})

        assert check_iconify_json_exists() == []

    def test_an_unusable_directory_gives_e008_and_no_e002(
        self, settings: SettingsWrapper, tmp_path: Path
    ) -> None:
        settings.SEMANTIC_ICONS_ICONIFY_DIR = tmp_path / "does-not-exist"

        found = check_iconify_dir() + check_iconify_json_exists()

        assert _ids(found) == ["icons.E008"]

    def test_unset_with_bundled_data_present_is_silent(
        self, bundled_data_only: None
    ) -> None:
        assert check_iconify_json_exists() == []

    def test_unset_with_bundled_data_missing_produces_e002(
        self,
        bundled_data_only: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr("freedom_ls.icons.checks.BUNDLED_DATA_DIR", tmp_path)

        errors = check_iconify_json_exists()

        assert _ids(errors) == ["icons.E002"]

    def test_no_e002_message_or_hint_mentions_npm_install(
        self,
        iconify_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEMANTIC_ICONS_SET = "heroicons"

        errors = check_iconify_json_exists()

        assert "npm install" not in errors[0].msg
        assert "npm install" not in (errors[0].hint or "")


class TestCheckMappingValuesExist:
    def test_valid_config_no_errors(self, bundled_data_only: None) -> None:
        errors = check_mapping_values_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_SET="heroicons")
    def test_heroicons_mappings_valid(self, bundled_data_only: None) -> None:
        errors = check_mapping_values_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_SET="heroicons")
    def test_variant_suffixed_names_are_validated(
        self, bundled_data_only: None
    ) -> None:
        """Variant-suffixed names ("bell-solid") must resolve in the icon JSON too."""
        errors = check_mapping_values_exist()

        assert errors == []


class TestCheckOverridesExist:
    def test_no_overrides_no_errors(self) -> None:
        errors = check_overrides_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_OVERRIDES={"success": "star"})
    def test_valid_override_no_errors(self, bundled_data_only: None) -> None:
        errors = check_overrides_exist()
        assert errors == []

    @override_settings(SEMANTIC_ICONS_OVERRIDES={"success": "nonexistent-icon-xyz"})
    def test_bad_override_value_produces_e006(self, bundled_data_only: None) -> None:
        errors = check_overrides_exist()
        assert any(e.id == "icons.E006" for e in errors)

    @override_settings(SEMANTIC_ICONS_OVERRIDES={"success": "nonexistent-icon-xyz"})
    def test_e006_hint_names_the_iconify_dir_setting(
        self, bundled_data_only: None
    ) -> None:
        errors = check_overrides_exist()

        assert "SEMANTIC_ICONS_ICONIFY_DIR" in (errors[0].hint or "")

    @override_settings(SEMANTIC_ICONS_OVERRIDES={"not_a_semantic_name": "star"})
    def test_bad_override_key_produces_e005(self, bundled_data_only: None) -> None:
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


def test_default_settings_produce_no_icons_check_output() -> None:
    # Only the icons app's own checks are run: Django's other checks need a database or
    # other installed apps, which a host with no database does not have.
    icons_checks = [
        check
        for check in registry.registered_checks
        if check.__module__ == "freedom_ls.icons.checks"
    ]

    found = [message for check in icons_checks for message in check(app_configs=None)]

    assert len(icons_checks) == 7
    assert found == []
