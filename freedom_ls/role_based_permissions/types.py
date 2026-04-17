from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Literal

RoleType = Literal["standalone", "composable"]
ROLE_TYPE_STANDALONE: RoleType = "standalone"
ROLE_TYPE_COMPOSABLE: RoleType = "composable"
ROLE_TYPE_DEFAULT: RoleType = ROLE_TYPE_STANDALONE
VALID_ROLE_TYPES: set[RoleType] = {ROLE_TYPE_STANDALONE, ROLE_TYPE_COMPOSABLE}

AssignmentScope = Literal["system", "site", "object"]
SCOPE_SYSTEM: AssignmentScope = "system"
SCOPE_SITE: AssignmentScope = "site"
SCOPE_OBJECT: AssignmentScope = "object"
VALID_ASSIGNMENT_SCOPES: set[AssignmentScope] = {SCOPE_SYSTEM, SCOPE_SITE, SCOPE_OBJECT}
VALID_SPEC_KEYS: set[str] = {
    "inherits",
    "add_permissions",
    "remove_permissions",
    "display_name",
    "lti_role",
    "role_type",
    "description",
    "assignment_scope",
}


@dataclass(frozen=True)
class Role:
    """Defines a single role and its capabilities."""

    display_name: str
    permissions: frozenset[str]
    assignment_scope: AssignmentScope
    lti_role: str | None = None
    role_type: RoleType = (
        ROLE_TYPE_DEFAULT  # called ui_hint in spec; renamed for clarity
    )
    description: str = ""


def _resolve_base_permissions(
    name: str,
    spec: dict[str, str | set[str] | frozenset[str]],
    existing_roles: dict[str, Role],
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
    base_perms: set[str], spec: dict[str, str | set[str] | frozenset[str]]
) -> frozenset[str]:
    """Apply add/remove permission changes to a base permission set."""
    add_perms = spec.get("add_permissions")
    if add_perms is not None:
        if not isinstance(add_perms, (set, frozenset)):
            raise TypeError(
                f"add_permissions must be a set or frozenset, got {type(add_perms).__name__}"
            )
        base_perms |= add_perms
    remove_perms = spec.get("remove_permissions")
    if remove_perms is not None:
        if not isinstance(remove_perms, (set, frozenset)):
            raise TypeError(
                f"remove_permissions must be a set or frozenset, got {type(remove_perms).__name__}"
            )
        base_perms -= remove_perms
    return frozenset(base_perms)


def _resolve_parent_role(
    name: str, parent_name: str | None, existing_roles: dict[str, Role]
) -> Role | None:
    """Find the parent role to inherit field defaults from.

    When parent_name is provided, _resolve_base_permissions has already
    validated that it exists in existing_roles, so we can look it up directly.
    """
    if parent_name is not None:
        return existing_roles[parent_name]
    return existing_roles.get(name)


def _build_role_from_spec(
    name: str,
    spec: dict[str, str | set[str] | frozenset[str]],
    existing_roles: dict[str, Role],
) -> Role:
    """Build a Role from a dict spec, resolving inheritance and permission changes."""
    unknown_keys = set(spec.keys()) - VALID_SPEC_KEYS
    if unknown_keys:
        raise ValueError(
            f"Unknown keys {sorted(unknown_keys)} in spec for role '{name}'. "
            f"Valid keys are: {sorted(VALID_SPEC_KEYS)}"
        )
    base_perms, parent_name = _resolve_base_permissions(name, spec, existing_roles)
    permissions = _apply_permission_changes(base_perms, spec)
    parent_role = _resolve_parent_role(name, parent_name, existing_roles)

    raw_display_name = spec.get("display_name")
    raw_lti_role = spec.get("lti_role")
    raw_role_type = spec.get("role_type")
    raw_description = spec.get("description")
    raw_assignment_scope = spec.get("assignment_scope")

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
    if raw_role_type is not None:
        raw_role_type_str = str(raw_role_type)
        if raw_role_type_str not in VALID_ROLE_TYPES:
            raise ValueError(
                f"Invalid role_type '{raw_role_type_str}' for role '{name}'. "
                f"Must be one of {sorted(VALID_ROLE_TYPES)}."
            )
        role_type: RoleType = raw_role_type_str
    else:
        role_type = parent_role.role_type if parent_role else ROLE_TYPE_DEFAULT
    if raw_assignment_scope is not None:
        raw_scope_str = str(raw_assignment_scope)
        if raw_scope_str not in VALID_ASSIGNMENT_SCOPES:
            raise ValueError(
                f"Invalid assignment_scope '{raw_scope_str}' for role '{name}'. "
                f"Must be one of {sorted(VALID_ASSIGNMENT_SCOPES)}."
            )
        assignment_scope: AssignmentScope = raw_scope_str
    elif parent_role:
        assignment_scope = parent_role.assignment_scope
    else:
        raise ValueError(
            f"Role '{name}' must specify an assignment_scope "
            f"(one of {sorted(VALID_ASSIGNMENT_SCOPES)})."
        )
    description = (
        str(raw_description)
        if raw_description is not None
        else (parent_role.description if parent_role else "")
    )

    return Role(
        display_name=display_name,
        permissions=permissions,
        assignment_scope=assignment_scope,
        lti_role=lti_role,
        role_type=role_type,
        description=description,
    )


class SiteRolesConfig(Mapping[str, Role]):
    """
    Container for a complete role configuration.
    Supports extending a base config with overrides,
    additions, and inheritance (including chained inheritance
    via successive extend() calls).
    """

    def __init__(self, roles: dict[str, Role]) -> None:
        self._roles = dict(roles)

    def extend(
        self, overrides: dict[str, Role | dict[str, str | set[str] | frozenset[str]]]
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
            else:
                raise TypeError(
                    f"Override for role '{name}' must be a Role or dict, "
                    f"got {type(spec).__name__}"
                )

        return SiteRolesConfig(new_roles)

    def __getitem__(self, key: str) -> Role:
        return self._roles[key]

    def __contains__(self, key: object) -> bool:
        return key in self._roles

    def __len__(self) -> int:
        return len(self._roles)

    def __iter__(self) -> Iterator[str]:
        return iter(self._roles)

    def all_permission_strings(self) -> set[str]:
        result: set[str] = set()
        for role in self._roles.values():
            result |= role.permissions
        return result

    def __repr__(self) -> str:
        role_names = ", ".join(sorted(self._roles.keys()))
        return f"SiteRolesConfig([{role_names}])"
