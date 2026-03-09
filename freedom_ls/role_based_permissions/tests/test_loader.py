"""Tests for the role configuration loader."""

from collections.abc import Generator
from types import ModuleType
from unittest.mock import patch

import pytest

from freedom_ls.role_based_permissions.loader import clear_caches, get_role_config
from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import SCOPE_SITE, Role, SiteRolesConfig


@pytest.fixture(autouse=True)
def clear_loader_cache() -> Generator[None]:
    """Clear role permission caches between every test."""
    clear_caches()
    yield
    clear_caches()


class TestGetRoleConfig:
    """Tests for the get_role_config function."""

    @pytest.mark.django_db
    def test_returns_base_roles_when_site_not_in_modules(
        self, settings, mock_site_context
    ) -> None:
        """Returns BASE_ROLES when site name is not found in modules dict."""
        settings.FREEDOMLS_PERMISSIONS_MODULES = {"OtherSite": "some.module"}
        result = get_role_config(site_name="TestSite")
        assert result is BASE_ROLES

    @pytest.mark.django_db
    def test_returns_site_specific_config(self, settings, mock_site_context) -> None:
        """Returns site-specific config when site name is in modules dict."""
        custom_config = SiteRolesConfig(
            {
                "custom_role": Role(
                    display_name="Custom",
                    permissions=frozenset(),
                    assignment_scope=SCOPE_SITE,
                ),
            }
        )

        fake_module = ModuleType("fake_site_roles")
        fake_module.ROLES = custom_config

        settings.FREEDOMLS_PERMISSIONS_MODULES = {
            "TestSite": "fake_site_roles",
        }

        with patch(
            "freedom_ls.role_based_permissions.loader.import_module",
            return_value=fake_module,
        ):
            result = get_role_config(site_name="TestSite")

        assert result is custom_config

    @pytest.mark.django_db
    def test_falls_back_to_base_roles_attribute(
        self, settings, mock_site_context
    ) -> None:
        """Falls back to module.BASE_ROLES when module has no ROLES attribute."""
        fake_module = ModuleType("fake_site_roles_no_roles")
        fake_module.BASE_ROLES = BASE_ROLES

        settings.FREEDOMLS_PERMISSIONS_MODULES = {
            "TestSite": "fake_site_roles_no_roles",
        }

        with patch(
            "freedom_ls.role_based_permissions.loader.import_module",
            return_value=fake_module,
        ):
            result = get_role_config(site_name="TestSite")

        assert result is BASE_ROLES

    @pytest.mark.django_db
    def test_uses_current_site_when_site_name_is_none(
        self, mock_site_context, mocker
    ) -> None:
        """Falls back to current site name when site_name=None."""
        mocker.patch(
            "freedom_ls.role_based_permissions.loader.Site.objects.get_current",
            return_value=mock_site_context,
        )
        result = get_role_config(site_name=None)
        assert result is BASE_ROLES

    @pytest.mark.django_db
    def test_cache_returns_same_object(self, mock_site_context) -> None:
        """Calling get_role_config twice returns the same object (identity check)."""
        result1 = get_role_config(site_name="TestSite")
        result2 = get_role_config(site_name="TestSite")
        assert result1 is result2
