PERMISSIONS: dict[str, str] = {
    # =========================================================================
    # Django built-in model permissions (auto-created, already in auth_permission)
    # Uncomment as they are used in role assignments or permission checks.
    # =========================================================================
    # --- accounts app (label: freedom_ls_accounts) ---
    # "freedom_ls_accounts.view_user": "Can view user",
    # "freedom_ls_accounts.add_user": "Can add user",
    # "freedom_ls_accounts.change_user": "Can change user",
    # "freedom_ls_accounts.delete_user": "Can delete user",
    # "freedom_ls_accounts.view_sitesignuppolicy": "Can view site signup policy",
    # "freedom_ls_accounts.add_sitesignuppolicy": "Can add site signup policy",
    # "freedom_ls_accounts.change_sitesignuppolicy": "Can change site signup policy",
    # "freedom_ls_accounts.delete_sitesignuppolicy": "Can delete site signup policy",
    # --- content_engine app (label: freedom_ls_content_engine) ---
    # "freedom_ls_content_engine.view_topic": "Can view topic",
    # "freedom_ls_content_engine.add_topic": "Can add topic",
    # "freedom_ls_content_engine.change_topic": "Can change topic",
    # "freedom_ls_content_engine.delete_topic": "Can delete topic",
    # "freedom_ls_content_engine.view_activity": "Can view activity",
    # "freedom_ls_content_engine.add_activity": "Can add activity",
    # "freedom_ls_content_engine.change_activity": "Can change activity",
    # "freedom_ls_content_engine.delete_activity": "Can delete activity",
    # "freedom_ls_content_engine.view_course": "Can view course",
    # "freedom_ls_content_engine.add_course": "Can add course",
    # "freedom_ls_content_engine.change_course": "Can change course",
    # "freedom_ls_content_engine.delete_course": "Can delete course",
    # "freedom_ls_content_engine.view_form": "Can view form",
    # "freedom_ls_content_engine.add_form": "Can add form",
    # "freedom_ls_content_engine.change_form": "Can change form",
    # "freedom_ls_content_engine.delete_form": "Can delete form",
    # "freedom_ls_content_engine.view_formcontent": "Can view form content",
    # "freedom_ls_content_engine.add_formcontent": "Can add form content",
    # "freedom_ls_content_engine.change_formcontent": "Can change form content",
    # "freedom_ls_content_engine.delete_formcontent": "Can delete form content",
    # "freedom_ls_content_engine.view_contentcollectionitem": "Can view content collection item",
    # "freedom_ls_content_engine.add_contentcollectionitem": "Can add content collection item",
    # "freedom_ls_content_engine.change_contentcollectionitem": "Can change content collection item",
    # "freedom_ls_content_engine.delete_contentcollectionitem": "Can delete content collection item",
    # "freedom_ls_content_engine.view_questionoption": "Can view question option",
    # "freedom_ls_content_engine.add_questionoption": "Can add question option",
    # "freedom_ls_content_engine.change_questionoption": "Can change question option",
    # "freedom_ls_content_engine.delete_questionoption": "Can delete question option",
    # "freedom_ls_content_engine.view_file": "Can view file",
    # "freedom_ls_content_engine.add_file": "Can add file",
    # "freedom_ls_content_engine.change_file": "Can change file",
    # "freedom_ls_content_engine.delete_file": "Can delete file",
    # --- student_management app (label: freedom_ls_student_management) ---
    # ACTIVE — used in educator_interface and role assignments
    "freedom_ls_student_management.view_cohort": "Can view cohort",
    "freedom_ls_student_management.view_student": "Can view student",
    "freedom_ls_student_management.add_cohort": "Can add cohort",
    "freedom_ls_student_management.change_cohort": "Can change cohort",
    "freedom_ls_student_management.delete_cohort": "Can delete cohort",
    "freedom_ls_student_management.add_student": "Can add student",
    "freedom_ls_student_management.change_student": "Can change student",
    "freedom_ls_student_management.delete_student": "Can delete student",
    # "freedom_ls_student_management.view_cohortmembership": "Can view cohort membership",
    # "freedom_ls_student_management.add_cohortmembership": "Can add cohort membership",
    # "freedom_ls_student_management.change_cohortmembership": "Can change cohort membership",
    # "freedom_ls_student_management.delete_cohortmembership": "Can delete cohort membership",
    # "freedom_ls_student_management.view_studentcourseregistration": "Can view student course registration",
    # "freedom_ls_student_management.add_studentcourseregistration": "Can add student course registration",
    # "freedom_ls_student_management.change_studentcourseregistration": "Can change student course registration",
    # "freedom_ls_student_management.delete_studentcourseregistration": "Can delete student course registration",
    # "freedom_ls_student_management.view_cohortcourseregistration": "Can view cohort course registration",
    # "freedom_ls_student_management.add_cohortcourseregistration": "Can add cohort course registration",
    # "freedom_ls_student_management.change_cohortcourseregistration": "Can change cohort course registration",
    # "freedom_ls_student_management.delete_cohortcourseregistration": "Can delete cohort course registration",
    # "freedom_ls_student_management.view_cohortdeadline": "Can view cohort deadline",
    # "freedom_ls_student_management.add_cohortdeadline": "Can add cohort deadline",
    # "freedom_ls_student_management.change_cohortdeadline": "Can change cohort deadline",
    # "freedom_ls_student_management.delete_cohortdeadline": "Can delete cohort deadline",
    # "freedom_ls_student_management.view_studentdeadline": "Can view student deadline",
    # "freedom_ls_student_management.add_studentdeadline": "Can add student deadline",
    # "freedom_ls_student_management.change_studentdeadline": "Can change student deadline",
    # "freedom_ls_student_management.delete_studentdeadline": "Can delete student deadline",
    # "freedom_ls_student_management.view_studentcohortdeadlineoverride": "Can view student cohort deadline override",
    # "freedom_ls_student_management.add_studentcohortdeadlineoverride": "Can add student cohort deadline override",
    # "freedom_ls_student_management.change_studentcohortdeadlineoverride": "Can change student cohort deadline override",
    # "freedom_ls_student_management.delete_studentcohortdeadlineoverride": "Can delete student cohort deadline override",
    # "freedom_ls_student_management.view_recommendedcourse": "Can view recommended course",
    # "freedom_ls_student_management.add_recommendedcourse": "Can add recommended course",
    # "freedom_ls_student_management.change_recommendedcourse": "Can change recommended course",
    # "freedom_ls_student_management.delete_recommendedcourse": "Can delete recommended course",
    # --- student_progress app (label: freedom_ls_student_progress) ---
    # "freedom_ls_student_progress.view_formprogress": "Can view form progress",
    # "freedom_ls_student_progress.add_formprogress": "Can add form progress",
    # "freedom_ls_student_progress.change_formprogress": "Can change form progress",
    # "freedom_ls_student_progress.delete_formprogress": "Can delete form progress",
    # "freedom_ls_student_progress.view_topicprogress": "Can view topic progress",
    # "freedom_ls_student_progress.add_topicprogress": "Can add topic progress",
    # "freedom_ls_student_progress.change_topicprogress": "Can change topic progress",
    # "freedom_ls_student_progress.delete_topicprogress": "Can delete topic progress",
    # "freedom_ls_student_progress.view_courseprogress": "Can view course progress",
    # "freedom_ls_student_progress.add_courseprogress": "Can add course progress",
    # "freedom_ls_student_progress.change_courseprogress": "Can change course progress",
    # "freedom_ls_student_progress.delete_courseprogress": "Can delete course progress",
    # "freedom_ls_student_progress.view_questionanswer": "Can view question answer",
    # "freedom_ls_student_progress.add_questionanswer": "Can add question answer",
    # "freedom_ls_student_progress.change_questionanswer": "Can change question answer",
    # "freedom_ls_student_progress.delete_questionanswer": "Can delete question answer",
    # --- app_authentication app (label: freedom_ls_app_authentication) ---
    # "freedom_ls_app_authentication.view_client": "Can view client",
    # "freedom_ls_app_authentication.add_client": "Can add client",
    # "freedom_ls_app_authentication.change_client": "Can change client",
    # "freedom_ls_app_authentication.delete_client": "Can delete client",
    # =========================================================================
    # Custom permissions (FUTURE — add via model Meta.permissions when needed)
    # These are for capabilities that don't map to standard CRUD operations.
    # =========================================================================
    #
    #   "freedom_ls_content_engine.publish_content": "Can publish/unpublish content"
    #   "freedom_ls_student_management.manage_enrolment": "Can enrol and remove users"
    #   "freedom_ls_student_progress.view_all_grades": "Can view all student grades"
    #   "freedom_ls_student_progress.manage_grades": "Can create, edit, and finalise grades"
    #   "freedom_ls_role_based_permissions.manage_roles": "Can assign roles within the site"
    #   "freedom_ls_role_based_permissions.view_reports": "Can view site-wide reports"
    #   "freedom_ls_role_based_permissions.manage_sites": "Can create and manage sites"
    #   "freedom_ls_role_based_permissions.view_audit_log": "Can view the system audit log"
}
