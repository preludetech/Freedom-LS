# Memory Index

- [reference_verified_student_setup.md](reference_verified_student_setup.md) — Three records needed for a login-ready QA student (User, verified EmailAddress, UserCourseRegistration)
- [reference_course_progress_pagination.md](reference_course_progress_pagination.md) — Educator course-progress panel: rows = CohortMembership@20/page, columns = Topic+Form (CourseParts excluded)@15/page
- [reference_completing_a_course.md](reference_completing_a_course.md) — How to mark a course Completed for a user; the save-hook and missing-site gotchas to avoid
- [reference_course_player_student_command.md](reference_course_player_student_command.md) — qa_create_course_player_student command: login-ready student for the 3 course-player redirect/resume cases
- [reference_sequential_item_unlock.md](reference_sequential_item_unlock.md) — Player items unlock sequentially; complete items 1..N-1 to make item N reachable (image/lightbox + form/quiz QA)
- [reference_demo_content_loader.md](reference_demo_content_loader.md) — Use `content_save <dir> <site>` to (re)load demo course content after markdown edits; idempotent via frontmatter UUID
- [reference_educator_cmodal_trigger.md](reference_educator_cmodal_trigger.md) — Give a QA educator a reachable c-modal trigger (cohort Delete confirmation / Create Cohort modal-form); perms + qa_create_educator_modal_target command
- [reference_form_question_types_command.md](reference_form_question_types_command.md) — qa_create_form_question_types command: QUIZ form with all 4 question types on a dedicated course for demodev@email.com
- [reference_rich_dashboard_student_command.md](reference_rich_dashboard_student_command.md) — qa_create_rich_dashboard_student: demodev_s1 with all 3 dashboard sections + real scored/passing quiz attempt + completed course
- [reference_password_reset_student_command.md](reference_password_reset_student_command.md) — qa_create_password_reset_student command; demodev_s1@email.com is a SHARED fixture (also enrolled by course-player command)
- [reference_course_access_types_command.md](reference_course_access_types_command.md) — qa_create_course_access_types: free + application_gated courses + unenrolled verified learner; children() memoization gotcha; DemoDev domain is 127.0.0.1:8000
- [reference_application_docs_scenario_command.md](reference_application_docs_scenario_command.md) — qa_create_application_docs_scenario: premium gated course + learner w/ in-flight CourseApplication + in-progress free course (demodev_applicant); TopicProgress.complete_time gotcha
