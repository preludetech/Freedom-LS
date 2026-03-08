# Role-Based Permissions

A role-based permission system for Freedom Learning System that maps roles to Django permissions and syncs them to [django-guardian](https://django-guardian.readthedocs.io/) for object-level access control.

## Overview

Permissions are organized into three scopes:

| Scope | Model | Example |
|-------|-------|---------|
| **System** | `SystemRoleAssignment` | Platform-wide admin |
| **Site** | `SiteRoleAssignment` | Admin of a specific site |
| **Object** | `ObjectRoleAssignment` | Instructor on a specific cohort |

Each role is a named collection of permission strings. When a role is assigned or removed, the system automatically syncs the corresponding guardian object permissions so that standard Django permission checks (`user.has_perm("app.codename", obj)`) work as expected.

## Quick start

### Assigning roles

```python
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    assign_system_role,
    remove_object_role,
    remove_site_role,
    remove_system_role,
)

# Assign a site-level role (permissions synced to the Site object)
assign_site_role(user, "site_admin", assigned_by=admin_user)

# Assign an object-level role (permissions synced to the target object)
assign_object_role(user, cohort, "instructor", assigned_by=admin_user)

# Assign a system-level role (no guardian sync — global scope)
assign_system_role(user, "system_admin", assigned_by=admin_user)

# Remove roles (guardian permissions updated automatically)
remove_site_role(user, "site_admin")
remove_object_role(user, cohort, "instructor")
remove_system_role(user, "system_admin")
```

### Checking permissions

After role assignment, use standard Django/guardian permission checks:

```python
# Object-level check
user.has_perm("freedom_ls_student_management.view_cohort", cohort)

# Filter querysets by permission
from guardian.shortcuts import get_objects_for_user
cohorts = get_objects_for_user(user, "freedom_ls_student_management.view_cohort")
```

### Querying role assignments

```python
from freedom_ls.role_based_permissions.utils import get_object_roles

# Get active roles a user has on an object
roles = get_object_roles(user, cohort)  # e.g. {"instructor"}
```

## Built-in roles

Defined in `roles.py` as `BASE_ROLES`:

| Role key | Display name | Description |
|----------|-------------|-------------|
| `site_admin` | Site Administrator | Full CRUD on cohorts and students |
| `instructor` | Instructor | View cohorts, view/change students |
| `ta` | Teaching Assistant | View cohorts and students |
| `system_admin` | System Administrator | Placeholder (no permissions yet) |
| `student` | Student | Placeholder (no permissions yet) |
| `observer` | Observer | Placeholder (no permissions yet) |

## Customizing roles per site

Sites can extend or override the base roles. In your Django settings:

```python
FREEDOMLS_PERMISSIONS_MODULES = {
    "my-site": "myproject.permissions",  # maps site name to module path
}
```

The referenced module must define a `ROLES` attribute (a `SiteRolesConfig`). Typically this extends `BASE_ROLES`:

```python
# myproject/permissions.py
from freedom_ls.role_based_permissions.roles import BASE_ROLES

ROLES = BASE_ROLES.extend({
    # Add permissions to an existing role
    "ta": {
        "add_permissions": frozenset({
            "freedom_ls_student_management.change_student",
        }),
    },

    # Create a new role inheriting from an existing one
    "lead_instructor": {
        "inherits": "instructor",
        "display_name": "Lead Instructor",
        "add_permissions": frozenset({
            "freedom_ls_student_management.add_cohort",
        }),
    },

    # Replace a role entirely
    "observer": Role(
        display_name="Observer",
        permissions=frozenset({
            "freedom_ls_student_management.view_cohort",
        }),
    ),
})
```

Sites not listed in `FREEDOMLS_PERMISSIONS_MODULES` use `BASE_ROLES`.

## Permission registry

All valid permission strings are declared in `registry.py`. Every permission referenced by a role must exist in the `PERMISSIONS` dict:

```python
# registry.py
PERMISSIONS: dict[str, str] = {
    "freedom_ls_student_management.view_cohort": "Can view cohort",
    "freedom_ls_student_management.add_cohort": "Can add cohort",
    # ...
}
```

When adding new permissions, add them to `PERMISSIONS` first, then reference them in roles.

## Management commands

### `sync_role_permissions`

Synchronizes guardian permissions to match all active role assignments. Fixes any drift between role assignments and actual guardian permissions.

```bash
# Preview changes without applying
uv run manage.py sync_role_permissions --dry-run

# Apply changes
uv run manage.py sync_role_permissions

# Also report guardian permissions that have no matching role assignment
uv run manage.py sync_role_permissions --report-orphans

# Sync for a specific site's config
uv run manage.py sync_role_permissions --site my-site
```

### `validate_role_permissions`

Validates role configuration. Run this in CI to catch errors before deployment.

```bash
uv run manage.py validate_role_permissions
```

Checks:
- Role names are valid Python identifiers
- All permissions referenced by roles exist in the registry
- `role_type` values are valid (`"standalone"` or `"composable"`)
- No active role assignments in the database reference roles that no longer exist in any config

## How it works

1. **Role definition** — Roles are defined as frozen dataclasses mapping a role name to a set of permission strings.

2. **Role assignment** — Calling `assign_*_role()` creates (or reactivates) a role assignment record and syncs guardian permissions. Assignments use soft-delete (`is_active=False`) rather than hard deletion.

3. **Permission sync** — When syncing, the system computes the desired permissions from all active roles, compares against current guardian permissions, and applies the diff. Only permissions matching the target object's content type are synced (a guardian requirement).

4. **Permission checking** — Application code checks permissions through Django/guardian's standard API. The role system is transparent at check time.

## Key design decisions

- **Guardian as the enforcement layer** — The role system is an abstraction over guardian. It manages *what* permissions a user should have; guardian enforces them.
- **Content-type filtering** — When syncing permissions to an object, only permissions whose codename matches the object's content type are applied.
- **Soft deactivation** — `is_active=False` preserves audit history and enables reactivation without data loss.
- **Site-awareness** — `SiteRoleAssignment` and `ObjectRoleAssignment` are site-scoped via `SiteAwareModel`. `SystemRoleAssignment` is intentionally global.
- **No middleware or signals** — Role changes happen through explicit function calls, keeping the system predictable and easy to trace.
