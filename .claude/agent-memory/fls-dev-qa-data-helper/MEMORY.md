# Memory Index

- [reference_verified_learner_setup.md](reference_verified_learner_setup.md) — Three records needed for a login-ready QA learner (User, verified EmailAddress, UserCourseRegistration); "right password but lands on Verify Your Email Address" = missing/unverified EmailAddress; use update_or_create
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
- [reference_second_site_form_engine_fixture.md](reference_second_site_form_engine_fixture.md) — qa_create_site_scoping_form: form_engine + learner_progress tree on a 2nd Site (default Demo) for admin site-scoping QA; explicit site= on every factory call, Learner site comes from its Organisation, _base_manager lookups, FORCE_SITE_NAME=DemoDev pins every request
- [reference_form_engine_branch_qa_baseline.md](reference_form_engine_branch_qa_baseline.md) — The whole-DB "documented starting state" recipe for the form_engine-extraction QA pass; reset-then-recalculate ordering; CourseProgress.course (not .collection)
- [reference_proving_allauth_login_works.md](reference_proving_allauth_login_works.md) — Proving a QA user can log in: force_login/check_password are false positives; rolled-back real login POST + verified=False negative control (locmem email backend)
- [reference_report_brand_organisations_command.md](reference_report_brand_organisations_command.md) — qa_create_report_brand_organisations: the 6 extra orgs for report cover/footer branding QA; empty-slug trap for a punctuation-only name; how to attach a deliberately-invalid logo
- [reference_form_engine_app_move_db_repair.md](reference_form_engine_app_move_db_repair.md) — carrying form data across the content_engine -> form_engine app move on a populated dev DB, and the dangling ContentType that breaks every course with a quiz
- [reference_report_org_branding_qa_setup.md](reference_report_org_branding_qa_setup.md) — Per-organisation report-branding seed: the org-slug drift (Northside is `northside-2`), Cohort has no slug field, the flat non-grouped report dropdown, and the legacy learners that inflate fixture cohorts to 18
- [reference_qa_complete_form_now_recalculates.md](reference_qa_complete_form_now_recalculates.md) — qa_complete_form DOES fire a recalculation now (complete() sends form_attempt_completed); a 0-score failed quiz still moves no percentage, so use CourseProgress.last_accessed_time to detect the write
- [reference_org_course_registration.md](reference_org_course_registration.md) — Course has NO organisation FK (nor uuid); the learner's registration carries the org; qa_register_org_course; the co-branding TOC header lives in the PLAYER sidebar only
- [reference_background_tasks_dev.md](reference_background_tasks_dev.md) — Dev needs NO db_worker: TASKS is pinned to ImmediateBackend, so report PDFs render inline
- [reference_legacy_report_prefix_staging.md](reference_legacy_report_prefix_staging.md) — Staging a pre-rename `reports/`-prefix GeneratedReport row; in dev ALL storage aliases share MEDIA_ROOT, so only the key prefix separates them
- [reference_storage_qa_dataset.md](reference_storage_qa_dataset.md) — The whole prod_bucket_setup storage-QA dataset in one recipe; --num-flagged undercounts on a quiz-less course; generate_cohort_report() repairs a row in place
- [reference_paginated_progress_matrix_command.md](reference_paginated_progress_matrix_command.md) — qa_create_paginated_progress_matrix; org-owned "QA Pagination Cohort" (32 learners / 26 items) WITH a progress spread; already-complete TopicProgress rows never recalculate progress_percentage; educator URLs are organisation-scoped
- [reference_dual_grant_course_progress_fixture.md](reference_dual_grant_course_progress_fixture.md) — Two grants (cohort + individual) on one course for grant fall-through QA; SiteAwareFactory needs explicit site= outside a request; cohort registration fans out to the WHOLE cohort
- [reference_seeding_form_attempts_around_the_site_bug.md](reference_seeding_form_attempts_around_the_site_bug.md) — `form_progress__site=site` workaround for the CourseFormAttemptFactory NULL-site bug; how to build a real answered/scored cohort-granted sitting; recalculate surfaces unrelated denominator drift
- [reference_organisation_educator_access.md](reference_organisation_educator_access.md) — Getting a persona into the organisation-scoped educator interface: the two independent access paths, why a missing ObjectRoleAssignment does NOT prove a blocked step, and where cohort reports live
- [reference_detaching_a_cohort_membership.md](reference_detaching_a_cohort_membership.md) — Deleting ONE CohortMembership to make grant resolution fall through to the individual registration; nothing FKs to CohortMembership (no cascade, no ProtectedError); there is deliberately no post_delete, so the cohort-granted CourseProgress SURVIVES
- [reference_admin_constraint_fixtures_command.md](reference_admin_constraint_fixtures_command.md) — qa_create_admin_constraint_fixtures: webhook endpoint/secret + CourseInterest + second-org Learner + per-org cohorts for uniqueness-constraint admin QA; WebhookSecret names forbid hyphens
- [reference_half_nulled_deadline_contenttype.md](reference_half_nulled_deadline_contenttype.md) — qa_create_half_nulled_deadlines: making `content_type IS NULL` + `object_id` populated deadline rows; ContentCollectionItem.child_type is CASCADE so deleting the Topic ContentType strips every topic out of every course — use the zero-instance Activity ContentType as the decoy target instead
- [reference_qa_run_residue_cleanup.md](reference_qa_run_residue_cleanup.md) — Tearing down a manual QA run's residue (signup user + LegalConsent x2 + EmailAddress, CourseInterest, a self-service enrolment); Collector.fast_deletes hides half the cascade; CourseProgress PROTECTs LearnerCourseRegistration
- [reference_organisation_admin_summary_counts.md](reference_organisation_admin_summary_counts.md) — Organisation change-page learner-count summary (ngettext 0/1/N): it lives in learner_management/admin.py via ORGANISATION_SUMMARIES, counts inactive learners too, and how to seed an exact-1 org + render the wording headlessly
- [reference_form_first_course_command.md](reference_form_first_course_command.md) — qa_create_form_first_course: course whose item 1 is a Form (no-Previous-button branch of the form start page); FormProgress has a direct `user` FK; last_accessed_item is a plain FK; sequential unlock IS enforced by URL now
- [reference_shell_savepoint_does_not_roll_back.md](reference_shell_savepoint_does_not_roll_back.md) — `transaction.savepoint()` is a NO-OP in `manage.py shell` (autocommit): the "rolled-back probe" pattern silently COMMITS; use `transaction.atomic()` + raise, and re-read the field to prove the restore

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

The **prod bucket / file-storage QA run** (Aug 2026) has now been set up TWICE. Full
recipe in [[reference_storage_qa_dataset]]. The second pass was almost entirely
verification — the fixtures survive between runs — so ALWAYS inspect first and only
repair the deltas: a report row left staged on the legacy `reports/` prefix, and a
flag count short because `--num-flagged`'s `failing` flavour needs a pass-marked quiz.
If it is asked for a third time, wrap the recipe in one command.

**Course-progress pagination fixtures have now been asked for three times** (large
cohort, then `qa_create_column_pagination_scenario`, then the org-scoped
`qa_create_paginated_progress_matrix`). Check which shape is wanted before seeding:
default-org + 0% (column scenario) vs named organisation + real percentage spread
(progress matrix). See [[reference_paginated_progress_matrix_command]].

**"Persona X's password works but login bounces to /accounts/confirm-email/" has now been
reported once** (Eve, better_course_progress_tracking). It is never a password bug: it is a
missing or unverified allauth `EmailAddress`. Fix the seeding command's user helper (so the
next run self-heals) AND backfill the existing rows with a targeted script — do NOT re-run a
whole `qa_create_*` command to fix a login, because it rewrites the progress rows the tester
is mid-assertion on. Prove the fix with the rolled-back POST + negative control from
[[reference_proving_allauth_login_works]]; the negative control reproduces the tester's exact
symptom, which is what confirms the diagnosis. See [[reference_verified_learner_setup]].

**Never pad `functionality-demo-course-parts` for pagination QA.** It is the shared
course-player / resume / TOC fixture. `qa_add_course_items_for_pagination` DEFAULTS to it;
always pass an explicit `--course-slug`, or use `qa_create_column_pagination_scenario`.

**Site-scoping / multi-tenant demos need data on a SECOND site. Asked TWICE now** (Bloom form
tree, then a Demo/site-2 Form + FormProgress + CourseFormAttempt tree for the form_engine app
split). The dev DB is almost entirely DemoDev, so "prove the admin filters per site" always means
seeding a small tree on another Site. `qa_create_site_scoping_form` now covers the whole chain down
to the attempt join row and defaults to `Demo`; extend that command rather than writing a new one.
See [[reference_second_site_form_engine_fixture]]; the pattern generalises to any app whose models
subclass SiteAwareModel. Expect the ask to be phrased as "the check is vacuous" — the deliverable is
per-site counts showing a non-zero row on BOTH sites.

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

**`qa_create_report_fixtures` ACCUMULATES the restricted user's grant.** It calls
`assign_perm("view_cohort", restricted, permitted)` and never revokes, so running it in N
organisations leaves `qa-report-restricted@email.com` holding view_cohort on *every* one of the
N "QA Report Standard Cohort" rows, not just the last. Same for
`assign_object_role(org_staff, organisation, ...)`: `qa-report-orgstaff@email.com` ends up
organisation_staff on every organisation the command was ever pointed at. Check and say so before
a permission-scoping QA pass — "cohort B" has to be a cohort with a *different* fixture key.

The **per-organisation report-branding seed** (one `standard-cohort-medium-course`
cohort in each of a dozen organisations) was set up once, Aug 2026, for the
`report-rendered-with-org-name` branch. Full recipe and the four traps in
[[reference_report_org_branding_qa_setup]]. If it is asked again, the loop over
`--organisation-slug` is worth wrapping in one command — but always dump
`(name, slug)` from the DB first, because renamed orgs keep their original slug
and `Northside` is `northside-2`.

The **better_course_progress_tracking branch** introduces per-grant `CourseProgress`: two
nullable grant FKs (`learner_registration` / `cohort_registration`), one record per grant, minted
only by the registration `post_save` signals. Expect repeat asks for "give persona X a second
grant of a different kind". Never hand-create the progress rows; create the registration and let
the signal mint it. See [[reference_dual_grant_course_progress_fixture]]. The follow-on ask is now
also on record: **"take one of the two grants away again"**. Do it by deleting the
`CohortMembership`, not the progress row — the resolver joins through membership, and the
progress row is meant to survive. See [[reference_detaching_a_cohort_membership]].

The `CourseFormAttemptFactory` **NULL-site sub-factory bug is FIXED** by commit 2c2b5e35
(`site=factory.SelfAttribute("..site")` on `form_progress` / `collection_item` in both
`CourseFormAttemptFactory` and `TopicProgressFactory`). Re-verified from a management command in
Aug 2026: an explicit `site=` now reaches the nested rows, so the `form_progress__site=site`
workaround below is belt-and-braces only. Check `git log freedom_ls/learner_progress/factories.py`
before assuming a QA plan's description of the bug is current.

The **"qa_complete_form is blocked by the NULL-site bug, seed the data another way"** request
arrived once (seam QA S9, better_course_progress_tracking). The fix is a single
`form_progress__site=site` kwarg at the call site — no product change needed. If the bug is still
unfixed next time this is asked, promote the scratchpad script to
`qa_helpers/management/commands/qa_complete_form_for_grant.py` (cohort-granted CourseProgress
selected by registration pk, real QuestionAnswers, a pass/fail score spread, and members left
deliberately un-sat). See [[reference_seeding_form_attempts_around_the_site_bug]].

**"Persona X has no role on org Y, the educator step is blocked" arrived once**
(better_course_progress_tracking, Olive/DemoDev). It was a **false diagnosis**: a bare
guardian `view_cohort` grant already opened the cohort page. Always run the rolled-back
counterfactual (delete the grant, hit the URL, roll back) before claiming credit for
unblocking anything — and check the persona's real password, which is usually their own
email rather than whatever the plan quotes. The standalone grant command written that day
has been deleted; grant inline if a persona genuinely needs it. See
[[reference_organisation_educator_access]].

The **"seed me a row so I can try to DUPLICATE it in the admin" pass** arrived once
(final_pre_deploy_db_structure_cleanup, Aug 2026): `WebhookEndpoint`/`WebhookSecret`,
`CourseInterest`, a second-organisation `Learner` and per-organisation `Cohort`s, all at zero
rows on a freshly rebuilt DB. Wrapped in `qa_create_admin_constraint_fixtures`; see
[[reference_admin_constraint_fixtures_command]]. Two things to carry forward:
**(a)** always run the rolled-back *form* probe (`SomeAdminForm(data=...).errors`) to show the
tester the exact message the constraint produces — twice it revealed the requested fixture
value would have failed validation for an unrelated reason (the hyphenated
`qa-existing-secret`); **(b)** `CohortCourseRegistration` creation fans out `CourseProgress`
to every cohort member, so prefer stacking extra `CohortDeadline` rows on the registrations
that already exist over minting new registrations "for variety".

**`CohortDeadline` scope shapes**: `content_type`/`object_id` BOTH NULL = whole-course;
both set = item-scoped. `CohortDeadline.clean()` allows only ONE course-level row per
registration (Python-level, not a DB constraint), while item-level rows are capped by
`unique_cohort_deadline_per_item`. So "4 deadlines across 2 registrations" = one course-level
+ one item-level each. `qa_create_soft_deadline` covers both shapes via `--item-slug`.
`freedom_ls/content_engine/models` is a PACKAGE (`courses.py`/`topics.py`/`files.py`) — import
from `freedom_ls.content_engine.models`, and `ContentCollectionItem`'s GenericFK fields are
`collection_type`/`collection_id` and `child_type`/`child_id` (not `*_content_type`/`*_object_id`).

The **"delete a ContentType to half-null a GenericFK" data-integrity fixture** arrived once
(test 5.3, final_pre_deploy_db_structure_cleanup, Aug 2026). Never delete the ContentType the
QA plan names: `ContentCollectionItem.child_type`/`collection_type` are **CASCADE**, so the
Topic ContentType takes 21 course items with it and destroys every TOC. Seed the deadlines
against the zero-instance `content_engine.activity` ContentType instead — 4 unheld permissions
is the entire blast radius. `qa_create_half_nulled_deadlines` wraps it, and its
`_describe_holders()` helper sizes any ContentType deletion. See
[[reference_half_nulled_deadline_contenttype]]. Generalise the habit: before ANY delete of a
shared lookup row, walk `apps.get_models()` for FKs to it and print `on_delete.__name__` —
"expected SET_NULL" in a QA plan only ever describes the rows the plan is thinking about.

The **"delete the genuine course-level deadline so the half-nulled one is isolated"** ask
arrived once (test 5.3, final_pre_deploy_db_structure_cleanup, Aug 2026) as the sequel to the
half-nulling fixture. All three deadline `clean()` methods filter on `content_type__isnull=True`
**alone**, ignoring `object_id`, so a genuine both-NULL row on the same registration blocks the
half-nulled row for an unrelated reason and masks the behaviour under test. Nothing FKs to
`CohortDeadline` / `LearnerDeadline` / `LearnerCohortDeadlineOverride` and they have no delete
signals, so each delete is exactly 1 row with zero cascade. Guard the delete with
`assert row.content_type_id is None and row.object_id is None` — genuine and half-nulled rows
have **identical `__str__`** ("... - Whole course"), so only `object_id` tells them apart. See
[[reference_half_nulled_deadline_contenttype]].

The **"clear a CourseInterest row so the express-interest flow can be re-walked"** ask arrived
once (bug-interested-login-405, Sep 2026). `CourseInterest` (app label
`freedom_ls_course_interest`) has **no inbound relations at all** — `_meta.related_objects` is
empty — and no delete signals, so the delete is exactly 1 row, zero cascade, and the User and
Course are untouched. The deferred-login flow is idempotent (`get_or_create` on the unique
`(site, user, course)` constraint), so a leftover row silently makes the "interest recorded"
assertion pass on a re-run — deleting it is the correct way to re-arm the test, not a repair.
The dev DB holds only a couple of these rows total, so `_base_manager` + print-every-row is a
cheap way to prove the target is the right one; note the row seeded by
`qa_create_admin_constraint_fixtures` (demodev@email.com / content-widgets-demo-reference) is a
different fixture and must survive. `qa_create_course_visibility` deliberately pre-creates NO
interest rows — see [[reference_course_visibility_command]].

The **"clear the residue of the manual QA run"** teardown ask arrived once
(bug-interested-login-405, Sep 2026) as the sequel to the single-CourseInterest delete noted just above —
same branch, same day, now a whole-run list: the ad hoc signup user + its allauth/consent rows,
an earlier run's user (absent), the interest row, and the "Enrol for free"
`LearnerCourseRegistration`. Expect this shape after every browser-QA pass on a signup/interest
flow. Full cascade shapes and the four field-name gotchas in
[[reference_qa_run_residue_cleanup]]. The two that matter: a browser signup writes **two**
`LegalConsent` rows (terms + privacy), and `CourseProgress.learner_registration` is **PROTECT**,
so the enrolment cannot be deleted until its signal-minted progress row (plus any `TopicProgress`
the tester created by opening a lesson) goes first. Size every delete with `Collector` but print
`c.fast_deletes` as well as `c.data` — `c.data` alone under-reported the User delete by 2 rows.
If a third teardown is asked for, wrap it in `qa_helpers` as
`qa_clear_run_residue --user EMAIL --interest-user EMAIL --interest-course SLUG
--unenrol-user EMAIL --unenrol-course SLUG`, with the constraint-fixture pk hard-guarded.

The **"seed a course shaped so template branch X is reachable in a browser"** ask arrived once
(form at index 1, so `course_form.html` renders no Previous button — misc-small-fixes-manual,
Sep 2026). The shape is always: read the template's `{% if %}`, read the pytest that covers the
same branch, then build the smallest course whose item ORDER produces it. Building it as a
`qa_helpers` command took no longer than a shell script and left the branch re-seedable. Do NOT
reorder an existing demo course to get the shape — seed a dedicated one.
See [[reference_form_first_course_command]].
