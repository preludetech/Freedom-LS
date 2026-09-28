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

BASE_ROLES = SiteRolesConfig(
    {
        # --- Roles with currently-existing permissions ---
        "site_admin": Role(
            display_name="Site admin",
            assignment_scope=SCOPE_SITE,
            lti_role=None,  # FUTURE: assign LTI URI when LTI is implemented
            description="Everything, in every organisation on the site.",
            permissions=frozenset(
                {
                    # Django built-in permissions
                    "freedom_ls_organisations.view_organisation",
                    "freedom_ls_learner_management.view_cohort",
                    "freedom_ls_learner_management.view_learner",
                    "freedom_ls_learner_management.add_cohort",
                    "freedom_ls_learner_management.change_cohort",
                    "freedom_ls_learner_management.delete_cohort",
                    "freedom_ls_learner_management.add_learner",
                    "freedom_ls_learner_management.change_learner",
                    "freedom_ls_learner_management.add_cohortmembership",
                    "freedom_ls_learner_management.delete_cohortmembership",
                    "freedom_ls_learner_management.add_cohortcourseregistration",
                    "freedom_ls_learner_management.change_cohortcourseregistration",
                    "freedom_ls_learner_management.add_learnercourseregistration",
                    "freedom_ls_learner_management.change_learnercourseregistration",
                    "freedom_ls_learner_management.view_organisationmember",
                    "freedom_ls_learner_management.add_organisationmember",
                    "freedom_ls_learner_management.change_organisationmember",
                    # Custom permissions
                    "freedom_ls_learner_management.bulk_manage_learners",
                    "freedom_ls_learner_management.download_cohort_report",
                    "freedom_ls_role_based_permissions.assign_site_admin",
                    "freedom_ls_role_based_permissions.assign_organisation_admin",
                    "freedom_ls_role_based_permissions.assign_cohort_admin",
                    "freedom_ls_role_based_permissions.assign_cohort_viewer",
                    # FUTURE: add freedom_ls_role_based_permissions.* custom permissions as site admin features are built
                }
            ),
        ),
        "cohort_admin": Role(
            display_name="Cohort admin",
            assignment_scope=SCOPE_OBJECT,
            lti_role=None,  # FUTURE: assign LTI URI when LTI is implemented
            description="Manages who is in a cohort and what it is registered for.",
            permissions=frozenset(
                {
                    # Django built-in permissions
                    "freedom_ls_learner_management.view_cohort",
                    "freedom_ls_learner_management.view_learner",
                    "freedom_ls_learner_management.add_cohortmembership",
                    "freedom_ls_learner_management.delete_cohortmembership",
                    "freedom_ls_learner_management.add_cohortcourseregistration",
                    "freedom_ls_learner_management.change_cohortcourseregistration",
                    "freedom_ls_learner_management.add_learnercourseregistration",
                    "freedom_ls_learner_management.change_learnercourseregistration",
                    # Custom permissions
                    "freedom_ls_learner_management.download_cohort_report",
                    # FUTURE: add course-level permissions as features are built
                }
            ),
        ),
        "cohort_viewer": Role(
            display_name="Cohort viewer",
            assignment_scope=SCOPE_OBJECT,
            lti_role=None,  # FUTURE: assign LTI URI when LTI is implemented
            description="Sees a cohort and its reports. Changes nothing.",
            permissions=frozenset(
                {
                    # Django built-in permissions
                    "freedom_ls_learner_management.view_cohort",
                    "freedom_ls_learner_management.view_learner",
                    # Custom permissions
                    "freedom_ls_learner_management.download_cohort_report",
                    # FUTURE: add grading/analytics permissions as features are built
                }
            ),
        ),
        "organisation_admin": Role(
            display_name="Organisation admin",
            assignment_scope=SCOPE_OBJECT,
            lti_role=None,
            description="Everything in one organisation, including who else administers it.",
            permissions=frozenset(
                {
                    "freedom_ls_organisations.view_organisation",
                    "freedom_ls_learner_management.view_cohort",
                    "freedom_ls_learner_management.view_learner",
                    "freedom_ls_learner_management.add_cohort",
                    "freedom_ls_learner_management.change_cohort",
                    "freedom_ls_learner_management.delete_cohort",
                    "freedom_ls_learner_management.add_learner",
                    "freedom_ls_learner_management.change_learner",
                    "freedom_ls_learner_management.add_cohortmembership",
                    "freedom_ls_learner_management.delete_cohortmembership",
                    "freedom_ls_learner_management.add_cohortcourseregistration",
                    "freedom_ls_learner_management.change_cohortcourseregistration",
                    "freedom_ls_learner_management.add_learnercourseregistration",
                    "freedom_ls_learner_management.change_learnercourseregistration",
                    "freedom_ls_learner_management.view_organisationmember",
                    "freedom_ls_learner_management.add_organisationmember",
                    "freedom_ls_learner_management.change_organisationmember",
                    # Custom permissions
                    "freedom_ls_learner_management.bulk_manage_learners",
                    "freedom_ls_learner_management.download_cohort_report",
                    "freedom_ls_role_based_permissions.assign_organisation_admin",
                    "freedom_ls_role_based_permissions.assign_cohort_admin",
                    "freedom_ls_role_based_permissions.assign_cohort_viewer",
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
        "learner": Role(
            display_name="Learner",
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
