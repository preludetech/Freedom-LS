"""Tests for the icon system Django system checks."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from django.test import override_settings

from freedom_ls.icons.checks import (
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

    @override_settings(FREEDOM_LS_ICON_SET="nonexistent_set")
    def test_unknown_set_produces_e001(self) -> None:
        errors = check_iconify_json_exists()
        assert len(errors) == 1
        assert errors[0].id == "freedom_ls.E001"

    @override_settings(FREEDOM_LS_ICON_SET="heroicons")
    def test_missing_json_file_produces_e002(self) -> None:
        with patch("freedom_ls.icons.checks.iconify_json_path") as mock_path:
            mock_path.return_value.exists.return_value = False
            errors = check_iconify_json_exists()
        assert len(errors) == 1
        assert errors[0].id == "freedom_ls.E002"


class TestCheckMappingValuesExist:
    def test_valid_config_no_errors(self) -> None:
        errors = check_mapping_values_exist()
        assert errors == []

    @override_settings(FREEDOM_LS_ICON_SET="heroicons")
    def test_heroicons_mappings_valid(self) -> None:
        errors = check_mapping_values_exist()
        assert errors == []

    @override_settings(FREEDOM_LS_ICON_SET="heroicons")
    def test_variant_suffixed_names_are_validated(self) -> None:
        """Checks should also validate that variant-suffixed names exist in JSON."""
        errors = check_mapping_values_exist()
        # All heroicons variant-suffixed names should be valid
        assert not any(e.id == "freedom_ls.E004" for e in errors)


class TestCheckOverridesExist:
    def test_no_overrides_no_errors(self) -> None:
        errors = check_overrides_exist()
        assert errors == []

    @override_settings(FREEDOM_LS_ICON_OVERRIDES={"success": "star"})
    def test_valid_override_no_errors(self) -> None:
        errors = check_overrides_exist()
        assert errors == []

    @override_settings(FREEDOM_LS_ICON_OVERRIDES={"success": "nonexistent-icon-xyz"})
    def test_bad_override_value_produces_e006(self) -> None:
        errors = check_overrides_exist()
        assert any(e.id == "freedom_ls.E006" for e in errors)

    @override_settings(FREEDOM_LS_ICON_OVERRIDES={"not_a_semantic_name": "star"})
    def test_bad_override_key_produces_e005(self) -> None:
        errors = check_overrides_exist()
        assert any(e.id == "freedom_ls.E005" for e in errors)


class TestCheckVariantSupport:
    @override_settings(FREEDOM_LS_ICON_SET="heroicons")
    def test_heroicons_supports_common_variants(self) -> None:
        warnings = check_variant_support()
        assert warnings == []

    @override_settings(FREEDOM_LS_ICON_SET="lucide")
    def test_lucide_warns_about_solid_variant(self) -> None:
        warnings = check_variant_support()
        assert any(w.id == "freedom_ls.W001" for w in warnings)
        assert any("solid" in w.msg for w in warnings)
