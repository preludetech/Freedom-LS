from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    """Defines a single role and its capabilities."""

    display_name: str
    permissions: frozenset[str]
    lti_role: str | None = None
    ui_hint: str = "standalone"  # "standalone" | "composable"
    description: str = ""


class SiteRolesConfig:
    """
    Container for a complete role configuration.
    Supports extending a base config with overrides,
    additions, and single-level inheritance.
    """

    def __init__(self, roles: dict[str, Role]) -> None:
        self._roles = dict(roles)

    def extend(
        self, overrides: dict[str, Role | dict[str, str | set[str]]]
    ) -> SiteRolesConfig:
        """
        Return a new SiteRolesConfig layering overrides onto this one.

        Three override forms:
        1. Full replacement (provide a Role)
        2. Modification (dict with add_permissions / remove_permissions)
        3. Inheritance (dict with "inherits" key referencing parent)
        """
        new_roles = dict(self._roles)

        for name, spec in overrides.items():
            if isinstance(spec, Role):
                new_roles[name] = spec
            elif isinstance(spec, dict):
                base_perms: set[str] = set()

                parent_name = str(spec["inherits"]) if "inherits" in spec else None
                if parent_name is not None:
                    if parent_name not in new_roles:
                        raise ValueError(
                            f"Role '{name}' inherits from unknown role '{parent_name}'"
                        )
                    base_perms = set(new_roles[parent_name].permissions)
                elif name in new_roles:
                    base_perms = set(new_roles[name].permissions)

                add_perms = spec.get("add_permissions")
                if isinstance(add_perms, set):
                    base_perms |= add_perms
                remove_perms = spec.get("remove_permissions")
                if isinstance(remove_perms, set):
                    base_perms -= remove_perms

                parent_role: Role | None = None
                if parent_name is not None:
                    parent_role = new_roles.get(parent_name)
                if parent_role is None:
                    parent_role = new_roles.get(name)

                display_name = spec.get("display_name")
                lti_role = spec.get("lti_role")
                ui_hint = spec.get("ui_hint")
                description = spec.get("description")

                new_roles[name] = Role(
                    display_name=str(display_name)
                    if display_name is not None
                    else (parent_role.display_name if parent_role else name),
                    permissions=frozenset(base_perms),
                    lti_role=str(lti_role)
                    if lti_role is not None
                    else (parent_role.lti_role if parent_role else None),
                    ui_hint=str(ui_hint)
                    if ui_hint is not None
                    else (parent_role.ui_hint if parent_role else "standalone"),
                    description=str(description)
                    if description is not None
                    else (parent_role.description if parent_role else ""),
                )

        return SiteRolesConfig(new_roles)

    def __getitem__(self, key: str) -> Role:
        return self._roles[key]

    def __contains__(self, key: object) -> bool:
        return key in self._roles

    def __iter__(self) -> Iterator[str]:
        return iter(self._roles)

    def items(self) -> Iterator[tuple[str, Role]]:
        return iter(self._roles.items())

    def keys(self) -> Iterator[str]:
        return iter(self._roles.keys())

    def all_permission_strings(self) -> set[str]:
        result: set[str] = set()
        for role in self._roles.values():
            result |= role.permissions
        return result
