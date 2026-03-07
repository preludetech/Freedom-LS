# config/role_based_permissions/prelude.py
# Example: This shows the pattern for site-specific customisation.
# The permissions referenced below are FUTURE — they would only be
# added once the relevant features and data migrations exist.

from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import (
    Role,  # noqa: F401 — used in commented examples
)

LTI = "http://purl.imsglobal.org/vocab/lis/v2"

ROLES = BASE_ROLES.extend(
    {
        # Example: Modify existing role — Prelude TAs also get analytics
        # (requires freedom_ls_content_engine.view_analytics permission to exist first)
        # "ta": {
        #     "add_permissions": {"freedom_ls_content_engine.view_analytics"},
        # },
        # Example: New composable micro-role
        # (requires permissions to exist first)
        # "course_announcer": Role(
        #     display_name="Course Announcer",
        #     description="Can send announcements only.",
        #     lti_role=None,
        #     role_type="composable",
        #     permissions=frozenset({
        #         "freedom_ls_content_engine.view_course",
        #         "freedom_ls_content_engine.send_announcements",
        #     }),
        # ),
        # Example: Inheritance-based variant
        # "ta_announcements": {
        #     "display_name": "TA (with Announcements)",
        #     "inherits": "ta",
        #     "add_permissions": {"freedom_ls_content_engine.send_announcements"},
        #     "lti_role": f"{LTI}/membership#Instructor#TeachingAssistant",
        # },
    }
)
