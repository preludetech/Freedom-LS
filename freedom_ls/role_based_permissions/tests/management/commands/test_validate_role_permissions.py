"""Tests for the validate_role_permissions management command."""

from collections.abc import Generator
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import pytest
from click import ClickException

from django.contrib.sites.models import Site
from django.core.management import call_command

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.role_based_permissions.factories import SystemRoleAssignmentFactory
from freedom_ls.role_based_permissions.loader import clear_caches, get_role_config
from freedom_ls.role_based_permissions.types import SCOPE_SITE, Role, SiteRolesConfig


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None]:
    """Clear the loader and permission caches between tests."""
    clear_caches()
    yield
    clear_caches()


@pytest.fixture(autouse=True)
def _site_context(mock_site_context: Site) -> None:
    """Every test here builds site-aware objects and assigns roles."""


class TestValidateRolePermissionsValidConfig:
    """Test validate command with valid config."""

    @pytest.mark.django_db
    def test_valid_config_succeeds(self) -> None:
        """validate_role_permissions succeeds with default valid config."""
        out = _call_validate()
        assert "All role configurations are valid." in out


class TestValidateRolePermissionsInvalidRoleName:
    """Test validate command detects invalid role name."""

    @pytest.mark.django_db
    def test_invalid_role_name_reports_error(self) -> None:
        """Role name that is not a valid Python identifier is reported."""
        bad_config = SiteRolesConfig(
            {
                "not-valid-identifier": Role(
                    display_name="Bad Role",
                    permissions=frozenset(),
                    assignment_scope=SCOPE_SITE,
                ),
            }
        )
        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.load_base_config",
                return_value=bad_config,
            ),
            pytest.raises(ClickException, match="not-valid-identifier"),
        ):
            _call_validate()


class TestValidateRolePermissionsUnknownPermission:
    """Test validate command detects unknown permissions in roles."""

    @pytest.mark.django_db
    def test_unknown_permission_reports_error(self) -> None:
        """Permission not in registry is reported as error."""
        bad_config = SiteRolesConfig(
            {
                "test_role": Role(
                    display_name="Test Role",
                    permissions=frozenset(
                        {
                            "nonexistent_app.nonexistent_perm",
                        }
                    ),
                    assignment_scope=SCOPE_SITE,
                ),
            }
        )
        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.load_base_config",
                return_value=bad_config,
            ),
            pytest.raises(ClickException, match=r"nonexistent_app\.nonexistent_perm"),
        ):
            _call_validate()


class TestValidateRolePermissionsInvalidRoleType:
    """Test validate command detects invalid role_type."""

    @pytest.mark.django_db
    def test_invalid_role_type_reports_error(self) -> None:
        """role_type that is neither 'standalone' nor 'composable' is reported."""
        bad_config = SiteRolesConfig(
            {
                "test_role": Role(
                    display_name="Test Role",
                    permissions=frozenset(),
                    assignment_scope=SCOPE_SITE,
                    role_type="invalid_hint",
                ),
            }
        )
        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.load_base_config",
                return_value=bad_config,
            ),
            pytest.raises(ClickException, match="invalid_hint"),
        ):
            _call_validate()


class TestValidateRolePermissionsOrphanedDbAssignment:
    """Test validate command detects orphaned DB assignments."""

    @pytest.mark.django_db
    def test_orphaned_db_assignment_reports_error(self) -> None:
        """Role in assignment table not in any config is reported as error."""
        user = UserFactory()
        # Create assignment with a role not in the config
        SystemRoleAssignmentFactory(user=user, role="nonexistent_role_xyz")

        with pytest.raises(ClickException, match="nonexistent_role_xyz"):
            _call_validate()


class TestValidateRolePermissionsMultipleConfigs:
    """Test validate command validates multiple configs."""

    @pytest.mark.django_db
    def test_multiple_configs_validated(self) -> None:
        """Base + site-specific configs are all validated."""
        bad_site_config = SiteRolesConfig(
            {
                "bad role name!": Role(
                    display_name="Bad",
                    permissions=frozenset(),
                    assignment_scope=SCOPE_SITE,
                ),
            }
        )

        def mock_get_config(site_name: str | None = None) -> SiteRolesConfig:
            if site_name == "bad_site":
                return bad_site_config
            return get_role_config(site_name)

        with (
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions.get_role_config",
                side_effect=mock_get_config,
            ),
            patch(
                "freedom_ls.role_based_permissions.management.commands.validate_role_permissions._get_permissions_modules",
                return_value={"bad_site": "some.module"},
            ),
            pytest.raises(ClickException, match="bad role name!"),
        ):
            _call_validate()


def _call_validate(*args: str) -> str:
    """Call validate_role_permissions and return stdout."""
    out = StringIO()
    with redirect_stdout(out):
        call_command("validate_role_permissions", *args)
    return out.getvalue()
