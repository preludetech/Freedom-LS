"""Tests for Role and SiteRolesConfig types."""

import pytest

from freedom_ls.role_based_permissions.types import Role, SiteRolesConfig


class TestSiteRolesConfig:
    """Tests for the SiteRolesConfig container."""

    @pytest.fixture
    def base_config(self) -> SiteRolesConfig:
        """Create a base config with two roles for testing."""
        return SiteRolesConfig(
            {
                "editor": Role(
                    display_name="Editor",
                    permissions=frozenset({"content.edit", "content.view"}),
                    lti_role="urn:lti:role:editor",
                    ui_hint="standalone",
                    description="Can edit content",
                ),
                "viewer": Role(
                    display_name="Viewer",
                    permissions=frozenset({"content.view"}),
                ),
            }
        )

    def test_getitem(self, base_config: SiteRolesConfig) -> None:
        """SiteRolesConfig supports bracket access."""
        role = base_config["editor"]
        assert role.display_name == "Editor"

    def test_getitem_missing_raises_key_error(
        self, base_config: SiteRolesConfig
    ) -> None:
        """Accessing a missing role raises KeyError."""
        with pytest.raises(KeyError):
            base_config["nonexistent"]

    def test_contains(self, base_config: SiteRolesConfig) -> None:
        """SiteRolesConfig supports 'in' operator."""
        assert "editor" in base_config
        assert "nonexistent" not in base_config

    def test_iter(self, base_config: SiteRolesConfig) -> None:
        """SiteRolesConfig supports iteration over role names."""
        names = list(base_config)
        assert set(names) == {"editor", "viewer"}

    def test_items(self, base_config: SiteRolesConfig) -> None:
        """SiteRolesConfig.items() returns name-role pairs."""
        items = dict(base_config.items())
        assert "editor" in items
        assert "viewer" in items
        assert items["editor"].display_name == "Editor"

    def test_keys(self, base_config: SiteRolesConfig) -> None:
        """SiteRolesConfig.keys() returns role names."""
        assert set(base_config.keys()) == {"editor", "viewer"}

    def test_all_permission_strings(self, base_config: SiteRolesConfig) -> None:
        """all_permission_strings() returns union of all role permissions."""
        result = base_config.all_permission_strings()
        assert result == {"content.edit", "content.view"}

    def test_extend_full_role_replacement(self, base_config: SiteRolesConfig) -> None:
        """extend() with a Role object fully replaces the existing role."""
        new_role = Role(
            display_name="Super Editor",
            permissions=frozenset({"content.edit", "content.view", "content.publish"}),
        )
        extended = base_config.extend({"editor": new_role})
        assert extended["editor"].display_name == "Super Editor"
        assert "content.publish" in extended["editor"].permissions

    def test_extend_add_permissions(self, base_config: SiteRolesConfig) -> None:
        """extend() with add_permissions adds to the existing role's permissions."""
        extended = base_config.extend(
            {"editor": {"add_permissions": {"content.publish"}}}
        )
        assert extended["editor"].permissions == frozenset(
            {"content.edit", "content.view", "content.publish"}
        )

    def test_extend_remove_permissions(self, base_config: SiteRolesConfig) -> None:
        """extend() with remove_permissions removes from the existing role's permissions."""
        extended = base_config.extend(
            {"editor": {"remove_permissions": {"content.edit"}}}
        )
        assert extended["editor"].permissions == frozenset({"content.view"})

    def test_extend_add_and_remove_permissions(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() with both add and remove permissions applies both."""
        extended = base_config.extend(
            {
                "editor": {
                    "add_permissions": {"content.publish"},
                    "remove_permissions": {"content.edit"},
                }
            }
        )
        assert extended["editor"].permissions == frozenset(
            {"content.view", "content.publish"}
        )

    def test_extend_inherits_copies_parent_permissions(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() with 'inherits' copies parent role's permissions."""
        extended = base_config.extend(
            {
                "senior_editor": {
                    "inherits": "editor",
                    "display_name": "Senior Editor",
                    "add_permissions": {"content.publish"},
                }
            }
        )
        assert extended["senior_editor"].permissions == frozenset(
            {"content.edit", "content.view", "content.publish"}
        )

    def test_extend_inherits_unknown_role_raises_value_error(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() with 'inherits' from an unknown role raises ValueError."""
        with pytest.raises(
            ValueError, match="Role 'new_role' inherits from unknown role 'ghost'"
        ):
            base_config.extend(
                {
                    "new_role": {
                        "inherits": "ghost",
                        "display_name": "New Role",
                    }
                }
            )

    def test_extend_preserves_parent_fields_when_not_overridden(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() with inherits preserves parent's display_name, lti_role, ui_hint, description."""
        extended = base_config.extend(
            {
                "senior_editor": {
                    "inherits": "editor",
                }
            }
        )
        parent = base_config["editor"]
        child = extended["senior_editor"]
        assert child.display_name == parent.display_name
        assert child.lti_role == parent.lti_role
        assert child.ui_hint == parent.ui_hint
        assert child.description == parent.description

    def test_extend_overrides_parent_fields_when_specified(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() with inherits allows overriding parent fields."""
        extended = base_config.extend(
            {
                "senior_editor": {
                    "inherits": "editor",
                    "display_name": "Senior Editor",
                    "lti_role": "urn:lti:role:senior",
                    "ui_hint": "composable",
                    "description": "A senior editor",
                }
            }
        )
        child = extended["senior_editor"]
        assert child.display_name == "Senior Editor"
        assert child.lti_role == "urn:lti:role:senior"
        assert child.ui_hint == "composable"
        assert child.description == "A senior editor"

    def test_extend_does_not_mutate_original(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() returns a new config without mutating the original."""
        base_config.extend({"editor": {"add_permissions": {"content.publish"}}})
        assert "content.publish" not in base_config["editor"].permissions

    def test_extend_modification_preserves_parent_fields(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() with dict modification (no inherits) preserves existing role fields."""
        extended = base_config.extend(
            {"editor": {"add_permissions": {"content.publish"}}}
        )
        assert extended["editor"].display_name == "Editor"
        assert extended["editor"].lti_role == "urn:lti:role:editor"
        assert extended["editor"].ui_hint == "standalone"
        assert extended["editor"].description == "Can edit content"

    def test_single_level_inheritance_chain(self) -> None:
        """A role inheriting from an already-inherited role works because parent is resolved."""
        base = SiteRolesConfig(
            {
                "base_role": Role(
                    display_name="Base",
                    permissions=frozenset({"perm.a"}),
                ),
            }
        )
        # First extension: child inherits from base_role
        extended_once = base.extend(
            {
                "child_role": {
                    "inherits": "base_role",
                    "display_name": "Child",
                    "add_permissions": {"perm.b"},
                }
            }
        )
        # Second extension: grandchild inherits from child_role (already resolved)
        extended_twice = extended_once.extend(
            {
                "grandchild_role": {
                    "inherits": "child_role",
                    "display_name": "Grandchild",
                    "add_permissions": {"perm.c"},
                }
            }
        )
        assert extended_twice["grandchild_role"].permissions == frozenset(
            {"perm.a", "perm.b", "perm.c"}
        )

    def test_extend_new_role_via_dict_without_inherits(
        self, base_config: SiteRolesConfig
    ) -> None:
        """extend() with a dict for a new role name (no inherits, not existing) creates a role with given permissions."""
        extended = base_config.extend(
            {
                "new_role": {
                    "display_name": "New Role",
                    "add_permissions": {"custom.perm"},
                }
            }
        )
        assert extended["new_role"].display_name == "New Role"
        assert extended["new_role"].permissions == frozenset({"custom.perm"})
