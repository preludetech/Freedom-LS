# Memory Index

- [reference_verified_learner_setup.md](reference_verified_learner_setup.md) — Three records needed for a login-ready QA learner (User, verified EmailAddress, UserCourseRegistration)
- [reference_course_progress_pagination.md](reference_course_progress_pagination.md) — Educator course-progress panel: rows = CohortMembership@20/page, columns = Topic+Form (CourseParts excluded)@15/page
- [reference_completing_a_course.md](reference_completing_a_course.md) — How to mark a course Completed for a user; the save-hook and missing-site gotchas to avoid
- [reference_course_player_learner_command.md](reference_course_player_learner_command.md) — qa_create_course_player_learner command: login-ready learner for the 3 course-player redirect/resume cases
- [reference_sequential_item_unlock.md](reference_sequential_item_unlock.md) — Player items unlock sequentially; complete items 1..N-1 to make item N reachable (image/lightbox + form/quiz QA)
- [reference_demo_content_loader.md](reference_demo_content_loader.md) — Use `content_save <dir> <site>` to (re)load demo course content after markdown edits; idempotent via frontmatter UUID
- [reference_educator_cmodal_trigger.md](reference_educator_cmodal_trigger.md) — Give a QA educator a reachable c-modal trigger (cohort Delete confirmation / Create Cohort modal-form); perms + qa_create_educator_modal_target command
- [reference_form_question_types_command.md](reference_form_question_types_command.md) — qa_create_form_question_types command: QUIZ form with all 4 question types on a dedicated course for demodev@email.com
- [reference_rich_dashboard_learner_command.md](reference_rich_dashboard_learner_command.md) — qa_create_rich_dashboard_learner: demodev_s1 with all 3 dashboard sections + real scored/passing quiz attempt + completed course
- [reference_password_reset_learner_command.md](reference_password_reset_learner_command.md) — qa_create_password_reset_learner command; demodev_s1@email.com is a SHARED fixture (also enrolled by course-player command)
- [reference_course_access_types_command.md](reference_course_access_types_command.md) — qa_create_course_access_types: free + application_gated courses + unenrolled verified learner; children() memoization gotcha; DemoDev domain is 127.0.0.1:8000
- [reference_application_docs_scenario_command.md](reference_application_docs_scenario_command.md) — qa_create_application_docs_scenario: premium gated course + learner w/ in-flight CourseApplication + in-progress free course (demodev_applicant); TopicProgress.complete_time gotcha
- [reference_additional_registration_form_qa.md](reference_additional_registration_form_qa.md) — Require post-verification "Complete registration" form (Workflow 7): only test-fixture forms exist; SiteSignupPolicy row overrides terms setting; demodev@ is superuser (gate exempt)
- [reference_course_visibility_command.md](reference_course_visibility_command.md) — qa_create_course_visibility: learner+educator + 4 courses (published-free/coming_soon/hidden/hidden-registered) for Coming Soon & Hidden Courses QA; educator interface gated only by @login_required
- [reference_course_detail_variants_command.md](reference_course_detail_variants_command.md) — qa_create_course_detail_variants: TOC-in-development (with/without assessment) + hidden courses + free-course 3-lesson top-up for the override course-access/details-page QA
- [reference_registration_completion_scenario_command.md](reference_registration_completion_scenario_command.md) — qa_create_registration_completion_scenario: free+gated courses + complete learner + SiteSignupPolicy w/ DB-backed QAProfileCompletionForm (gates new signups, seeded learner stays complete)
- [reference_webhook_qa_setup.md](reference_webhook_qa_setup.md) — Webhooks browser QA: reuse access-types free/gated courses + fresh unenrolled webhook_qa_learner for course.registered / apply flows
- [reference_organisation_scenarios_command.md](reference_organisation_scenarios_command.md) — qa_create_organisation_scenarios: 3 orgs + 4 cohorts + 7 personas for Organisations QA; assign_object_role needs a thread-local site + SITE_ID in a command; unregistered learners can never reach the player, so the player's "no organisation / no logo chip" branch is unreachable in the browser (QA §7.6)
- [reference_learner_visible_deadlines.md](reference_learner_visible_deadlines.md) — Deadlines render ONLY in the course TOC partial (course detail + player sidebar), never on the dashboard; use a course-level CohortDeadline so badges show without expanding CourseParts; qa_create_soft_deadline defaults to -7 days (overdue)
- [reference_multiselect_quiz_scoring_command.md](reference_multiselect_quiz_scoring_command.md) — qa_create_multiselect_quiz_scoring: dedicated learner + checkbox quiz (pass%=50) + NULL-pass-% quiz; `checkboxes` not `checkbox`; force_login/axes + start_form gotchas
- [reference_report_fixture_commands.md](reference_report_fixture_commands.md) — qa_create_report_fixtures/_course/_cohort: the eleven-fixture cohort-progress-report QA matrix (incl. blank-answer-cohort for "Not answered"), scored attempts, at-risk flag mix, and the auto-timestamp / CourseProgress-site gotchas
- [reference_quiz_progression_block_command.md](reference_quiz_progression_block_command.md) — qa_create_quiz_progression_block: 3-item course (topic/checkbox-quiz@80%/topic) proving a FAILED quiz blocks the next item; URL-level unlock is NOT enforced
- [reference_free_text_survey_command.md](reference_free_text_survey_command.md) — qa_create_free_text_survey: non-scored CATEGORY_VALUE_SUM questionnaire of short_text/long_text; only 2 strategies exist, so CATEGORY_VALUE_SUM is "the survey one"
- [reference_legacy_checkbox_score_command.md](reference_legacy_checkbox_score_command.md) — qa_create_legacy_checkbox_score: how to craft a pre-fix checkbox attempt whose stored score disagrees with exact-match rescoring (complete() then queryset.update(scores=...)), in a report-ready cohort
- [reference_checkbox_scoring_quiz_and_reset.md](reference_checkbox_scoring_quiz_and_reset.md) — qa_create_checkbox_scoring_quiz (clean option-backed quiz, OPTIONAL checkbox q so "tick nothing" is submittable) + qa_reset_learner_progress; retake = GET start_form; unanswered != incorrect
- [reference_qa_command_site_arg_styles.md](reference_qa_command_site_arg_styles.md) — Which qa_ commands take SITE_NAME positionally vs --site-name, plus the required-option / cohort-membership prerequisites that make them exit 2
- [reference_educator_cohort_visibility_grants.md](reference_educator_cohort_visibility_grants.md) — cohorts_visible_to needs a guardian view_cohort grant; large/empty cohort commands grant none, so assign_perm after running them
- [reference_demodev_s1_fixture_collisions.md](reference_demodev_s1_fixture_collisions.md) — demodev_s1@email.com is shared by 4 commands that overwrite each other; run order and how to repair
- [reference_learner_deadline_admin_fixtures.md](reference_learner_deadline_admin_fixtures.md) — qa_create_learner_deadlines; the three deadline models are not interchangeable; LearnerDeadlineAdmin.search_fields has no email
- [reference_column_pagination_scenario.md](reference_column_pagination_scenario.md) — qa_create_column_pagination_scenario; both course-progress paginators live at once WITHOUT padding functionality-demo-course-parts
- [reference_second_site_form_engine_fixture.md](reference_second_site_form_engine_fixture.md) — qa_create_site_scoping_form: tiny form_engine tree on a 2nd Site for admin site-scoping QA; explicit site= on every factory call, _base_manager lookups, FORCE_SITE_NAME=DemoDev pins every request
- [reference_form_engine_branch_qa_baseline.md](reference_form_engine_branch_qa_baseline.md) — The whole-DB "documented starting state" recipe for the form_engine-extraction QA pass; reset-then-recalculate ordering; CourseProgress.course (not .collection)
- [reference_proving_allauth_login_works.md](reference_proving_allauth_login_works.md) — Proving a QA user can log in: force_login/check_password are false positives; rolled-back real login POST + verified=False negative control (locmem email backend)
- [reference_qa_complete_form_now_recalculates.md](reference_qa_complete_form_now_recalculates.md) — qa_complete_form DOES fire a recalculation now (complete() sends form_attempt_completed); a 0-score failed quiz still moves no percentage, so use CourseProgress.last_accessed_time to detect the write

## Recurring requests

The **quiz-marking browser QA pass** (multi-select scoring fix) has now been set up twice. The full
recipe is: `qa_create_form_question_types DemoDev`, `qa_create_multiselect_quiz_scoring`,
`qa_create_quiz_progression_block`, `qa_create_free_text_survey`, `qa_create_legacy_checkbox_score`,
`qa_create_checkbox_scoring_quiz`, then
`qa_reset_learner_progress --learner demodev_quizqa@email.com`, then
`content_save demo_content DemoDev`. All are idempotent; run the reset LAST so the walk starts clean.

The **report QA matrix** is repeatedly extended one fixture at a time as the QA plan finds an
unreachable render branch. Always add a new fixture key + (if the data shape needs it) a new course
key to `qa_create_report_fixtures`, never patch the dev DB by hand, and never `--reset` a cohort the
tester has already archived artifacts from.

The **legacy checkbox score discrepancy** cohort (`qa_create_legacy_checkbox_score`) has now been
asked for three times (QA 12.6, then QA 2.11 twice). It is stable across the whole report redesign.
Always **inspect the existing cohort first** — twice now the answer was "already correct, change
nothing".

The **terminology-rename (learner_*) browser QA run** was set up once (Aug 2026). Full recipe in
[[reference_demodev_s1_fixture_collisions]]; the run is: `qa_create_cohort_progress DemoDev`,
`qa_create_large_cohort DemoDev --course-slug functionality-demo-course-parts`,
`qa_create_empty_learner_cohort DemoDev --course-slug functionality-demo-course-parts`,
`qa_create_rich_dashboard_learner DemoDev`, `qa_create_course_player_learner DemoDev`,
`qa_create_organisation_scenarios --site-name DemoDev`,
`qa_create_password_reset_learner --site-name DemoDev`, `qa_create_course_access_types DemoDev`,
add demodev_s1 to the progress cohort, `qa_create_deadline_overrides ...`,
`qa_create_course_visibility DemoDev`, then assign_perm view_cohort for the large/empty cohorts.
NO qa_ command output contains the word "student" as of this branch.

**"Seed deadlines" is ambiguous and has now bitten twice.** Always ask/confirm WHICH of
`CohortDeadline` / `UserCohortDeadlineOverride` / `LearnerDeadline` is wanted, and state in
the report which model you wrote. `qa_create_deadline_overrides` writes only the middle one.

**Never pad `functionality-demo-course-parts` for pagination QA.** It is the shared
course-player / resume / TOC fixture. `qa_add_course_items_for_pagination` DEFAULTS to it;
always pass an explicit `--course-slug`, or use `qa_create_column_pagination_scenario`.

**Site-scoping / multi-tenant demos need data on a SECOND site.** The dev DB is almost entirely
DemoDev, so "prove the admin filters per site" always means seeding a small tree on Bloom (id 4).
See [[reference_second_site_form_engine_fixture]] for the pattern; it generalises to any app whose
models subclass SiteAwareModel.

The **"put the dev DB into the documented QA starting state" whole-run request** (as opposed to
"seed me one fixture") has now been made for the form_engine-extraction branch. It is a fixed
list of ~11 commands plus a cleanup pass; see
[[reference_form_engine_branch_qa_baseline]]. Two things bite every time:
`qa_reset_learner_progress` zeroes `progress_percentage`, so `recalculate_progress_percentages`
must run LAST; and QA plans list every command bare, but `qa_create_cohort_progress` REQUIRES a
positional `DemoDev` ([[reference_qa_command_site_arg_styles]]). If this is asked a third time,
wrap the list in a single `qa_setup_qa_baseline` command.

The **"prove a command fires no recalculation" assertion** was asked once (B4, form_engine
branch). Percentage-diffing is a FALSE NEGATIVE test on this branch: `qa_complete_form`
now calls `complete()` and does fire `form_attempt_completed`, but its 0-score attempts
fail the quiz pass mark and so never change a percentage. Detect the write via the
`auto_now` `CourseProgress.last_accessed_time` instead, and always check `git log -p` on
the command before trusting a QA plan's description of what it does — the plan described
the pre-`7a78c4f6` factory-based version. See
[[reference_qa_complete_form_now_recalculates]].
