"""DemoDev site-specific role configuration.

Extends BASE_ROLES with additional roles for the DemoDev site.
These roles add to (not override) the defaults.
"""

from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role

ROLES = BASE_ROLES.extend(
    {
        # DemoDev-specific TA variant: can also manage students
        "senior_ta": {
            "display_name": "Senior Teaching Assistant",
            "inherits": "ta",
            "description": "TA with additional student management permissions.",
            "add_permissions": {
                "freedom_ls_student_management.change_student",
                "freedom_ls_student_management.add_student",
            },
        },
        # Lightweight role for guest reviewers
        "guest_reviewer": Role(
            display_name="Guest Reviewer",
            assignment_scope=SCOPE_OBJECT,
            description="Read-only access for external reviewers.",
            permissions=frozenset(
                {
                    "freedom_ls_student_management.view_cohort",
                    "freedom_ls_student_management.view_student",
                }
            ),
        ),
    }
)
