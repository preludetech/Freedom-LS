from freedom_ls.role_based_permissions.types import (
    SCOPE_OBJECT,
    SCOPE_SITE,
    SCOPE_SYSTEM,
    Role,
    SiteRolesConfig,
)

# V1: Only includes permissions that exist in code today.
# As features are built, add the relevant permissions from the
# commented lists below and create data migrations for them.

# TODO: update these so there is no mention of rights over students, only rights over users

BASE_ROLES = SiteRolesConfig(
    {
        # --- Roles with currently-existing permissions ---
        "site_admin": Role(
            display_name="Site Administrator",
            assignment_scope=SCOPE_SITE,
            lti_role=None,  # FUTURE: assign LTI URI when LTI is implemented
            description="Manages courses, users, and settings within a site.",
            permissions=frozenset(
                {
                    # Django built-in permissions
                    "freedom_ls_student_management.view_cohort",
                    "freedom_ls_student_management.add_cohort",
                    "freedom_ls_student_management.change_cohort",
                    "freedom_ls_student_management.delete_cohort",
                    "freedom_ls_student_management.view_student",
                    "freedom_ls_student_management.add_student",
                    "freedom_ls_student_management.change_student",
                    "freedom_ls_student_management.delete_student",
                    # FUTURE: add freedom_ls_role_based_permissions.* custom permissions as site admin features are built
                }
            ),
        ),
        "instructor": Role(
            display_name="Instructor",
            assignment_scope=SCOPE_OBJECT,
            lti_role=None,  # FUTURE: assign LTI URI when LTI is implemented
            description="Full course management: content, grading, communication.",
            permissions=frozenset(
                {
                    # Django built-in permissions
                    "freedom_ls_student_management.view_cohort",
                    "freedom_ls_student_management.view_student",
                    "freedom_ls_student_management.change_student",
                    # FUTURE: add course-level permissions as features are built
                }
            ),
        ),
        "ta": Role(
            display_name="Teaching Assistant",
            assignment_scope=SCOPE_OBJECT,
            lti_role=None,  # FUTURE: assign LTI URI when LTI is implemented
            description="Supports instruction with grading and roster access.",
            permissions=frozenset(
                {
                    # Django built-in permissions
                    "freedom_ls_student_management.view_cohort",
                    "freedom_ls_student_management.view_student",
                    # FUTURE: add grading/analytics permissions as features are built
                }
            ),
        ),
        # --- Placeholder roles (no permissions exist yet) ---
        # These roles are defined for completeness but have empty permission
        # sets until the relevant features are built.
        "system_admin": Role(
            display_name="System Administrator",
            assignment_scope=SCOPE_SYSTEM,
            lti_role=None,
            description="Full platform access.",
            permissions=frozenset(),
            # FUTURE: freedom_ls_role_based_permissions.manage_sites, freedom_ls_role_based_permissions.manage_users,
            # freedom_ls_role_based_permissions.manage_settings, freedom_ls_role_based_permissions.view_audit_log
        ),
        "student": Role(
            display_name="Student",
            assignment_scope=SCOPE_OBJECT,
            lti_role=None,
            description="Standard learner role.",
            permissions=frozenset(),
            # FUTURE: freedom_ls_content_engine.view_course, freedom_ls_content_engine.submit_work,
            # freedom_ls_content_engine.view_own_grades
        ),
        "observer": Role(
            display_name="Observer",
            assignment_scope=SCOPE_OBJECT,
            lti_role=None,
            description="Read-only access for parents or mentors.",
            permissions=frozenset(),
            # FUTURE: freedom_ls_content_engine.view_course
        ),
    }
)
