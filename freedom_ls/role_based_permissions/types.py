from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import ItemsView, KeysView, ValuesView

RoleType = Literal["standalone", "composable"]
ROLE_TYPE_STANDALONE: RoleType = "standalone"
ROLE_TYPE_COMPOSABLE: RoleType = "composable"
ROLE_TYPE_DEFAULT: RoleType = ROLE_TYPE_STANDALONE


@dataclass(frozen=True)
class Role:
    """Defines a single role and its capabilities."""

    display_name: str
    permissions: frozenset[str]
    lti_role: str | None = None
    role_type: RoleType = ROLE_TYPE_DEFAULT
    description: str = ""


def _resolve_base_permissions(
    name: str, spec: dict[str, str | set[str]], existing_roles: dict[str, Role]
) -> tuple[set[str], str | None]:
    """Resolve base permissions and parent name from a spec dict."""
    parent_name = str(spec["inherits"]) if "inherits" in spec else None
    if parent_name is not None:
        if parent_name not in existing_roles:
            raise ValueError(
                f"Role '{name}' inherits from unknown role '{parent_name}'"
            )
        return set(existing_roles[parent_name].permissions), parent_name
    if name in existing_roles:
        return set(existing_roles[name].permissions), None
    return set(), None


def _apply_permission_changes(
    base_perms: set[str], spec: dict[str, str | set[str]]
) -> frozenset[str]:
    """Apply add/remove permission changes to a base permission set."""
    add_perms = spec.get("add_permissions")
    if isinstance(add_perms, (set, frozenset)):
        base_perms |= add_perms
    remove_perms = spec.get("remove_permissions")
    if isinstance(remove_perms, (set, frozenset)):
        base_perms -= remove_perms
    return frozenset(base_perms)


def _resolve_parent_role(
    name: str, parent_name: str | None, existing_roles: dict[str, Role]
) -> Role | None:
    """Find the parent role to inherit field defaults from."""
    if parent_name is not None:
        parent = existing_roles.get(parent_name)
        if parent is not None:
            return parent
    return existing_roles.get(name)


def _build_role_from_spec(
    name: str, spec: dict[str, str | set[str]], existing_roles: dict[str, Role]
) -> Role:
    """Build a Role from a dict spec, resolving inheritance and permission changes."""
    base_perms, parent_name = _resolve_base_permissions(name, spec, existing_roles)
    permissions = _apply_permission_changes(base_perms, spec)
    parent_role = _resolve_parent_role(name, parent_name, existing_roles)

    raw_display_name = spec.get("display_name")
    raw_lti_role = spec.get("lti_role")
    raw_role_type = spec.get("role_type")
    raw_description = spec.get("description")

    display_name = (
        str(raw_display_name)
        if raw_display_name is not None
        else (parent_role.display_name if parent_role else name)
    )
    lti_role = (
        str(raw_lti_role)
        if raw_lti_role is not None
        else (parent_role.lti_role if parent_role else None)
    )
    _valid_role_types: dict[str, RoleType] = {
        ROLE_TYPE_STANDALONE: ROLE_TYPE_STANDALONE,
        ROLE_TYPE_COMPOSABLE: ROLE_TYPE_COMPOSABLE,
    }
    if raw_role_type is not None:
        raw_role_type_str = str(raw_role_type)
        if raw_role_type_str not in _valid_role_types:
            raise ValueError(
                f"Invalid role_type '{raw_role_type_str}' for role '{name}'. "
                f"Must be '{ROLE_TYPE_STANDALONE}' or '{ROLE_TYPE_COMPOSABLE}'."
            )
        role_type: RoleType = _valid_role_types[raw_role_type_str]
    else:
        role_type = parent_role.role_type if parent_role else ROLE_TYPE_DEFAULT
    description = (
        str(raw_description)
        if raw_description is not None
        else (parent_role.description if parent_role else "")
    )

    return Role(
        display_name=display_name,
        permissions=permissions,
        lti_role=lti_role,
        role_type=role_type,
        description=description,
    )


class SiteRolesConfig:
    """
    Container for a complete role configuration.
    Supports extending a base config with overrides,
    additions, and inheritance (including chained inheritance
    via successive extend() calls).
    """

    def __init__(self, roles: dict[str, Role]) -> None:
        self._roles = dict(roles)

    def extend(
        self, overrides: dict[str, Role | dict[str, str | set[str]]]
    ) -> SiteRolesConfig:
        """
        Return a new SiteRolesConfig layering overrides onto this one.

        Three override forms:

        1. Full replacement — provide a Role object directly::

            config.extend(
                {
                    "editor": Role(
                        display_name="Editor",
                        permissions=frozenset({"content.edit"}),
                    ),
                }
            )

        2. Modification — dict with ``add_permissions`` and/or
           ``remove_permissions`` to tweak an existing role::

            config.extend(
                {
                    "editor": {"add_permissions": {"content.publish"}},
                }
            )

        3. Inheritance — dict with an ``inherits`` key to create a new
           role based on an existing parent::

            config.extend(
                {
                    "senior_editor": {
                        "inherits": "editor",
                        "display_name": "Senior Editor",
                        "add_permissions": {"content.publish"},
                    },
                }
            )
        """
        new_roles = dict(self._roles)

        for name, spec in overrides.items():
            if isinstance(spec, Role):
                new_roles[name] = spec
            elif isinstance(spec, dict):
                new_roles[name] = _build_role_from_spec(name, spec, new_roles)

        return SiteRolesConfig(new_roles)

    def __getitem__(self, key: str) -> Role:
        return self._roles[key]

    def __contains__(self, key: object) -> bool:
        return key in self._roles

    def __len__(self) -> int:
        return len(self._roles)

    def __iter__(self) -> Iterator[str]:
        return iter(self._roles)

    def items(self) -> ItemsView[str, Role]:
        return self._roles.items()

    def keys(self) -> KeysView[str]:
        return self._roles.keys()

    def values(self) -> ValuesView[Role]:
        return self._roles.values()

    def all_permission_strings(self) -> set[str]:
        result: set[str] = set()
        for role in self._roles.values():
            result |= role.permissions
        return result
