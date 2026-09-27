"""DemoDev site-specific role configuration.

Extends BASE_ROLES with additional roles for the DemoDev site.
These roles add to (not override) the defaults.
"""

from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role

ROLES = BASE_ROLES.extend(
    {
        # DemoDev-specific cohort_viewer variant: currently identical to
        # `cohort_viewer`, kept as the slot a real additional permission gets
        # added to.
        "senior_ta": {
            "display_name": "Senior Teaching Assistant",
            "inherits": "cohort_viewer",
            "description": "Cohort viewer variant reserved for additional permissions.",
            "add_permissions": set(),
        },
        # Lightweight role for guest reviewers
        "guest_reviewer": Role(
            display_name="Guest Reviewer",
            assignment_scope=SCOPE_OBJECT,
            description="Read-only access for external reviewers.",
            permissions=frozenset({"freedom_ls_learner_management.view_cohort"}),
        ),
    }
)
