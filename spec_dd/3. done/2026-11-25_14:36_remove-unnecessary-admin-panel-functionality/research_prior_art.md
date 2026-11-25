# Research: prior art

Topic: what has already been tried, here or elsewhere. Method note: this worker had no shell, so `git log` was not run. Findings come from reading `spec_dd/`, `docs/product/` and the current `admin.py` files. A follow-up should run `git log --oneline -- freedom_ls/{content_engine,form_engine,learner_management,learner_progress,hr_attributes,organisations}/admin.py` to confirm history. No `upgrade_notes/` directory exists in this worktree. The external section is from general knowledge, not fetched, and is marked as such.

## 1. Nothing has removed an admin here before

No done spec removes an admin. The history is all additive: admins were built, then hardened (delete refused, read-only inlines).

- `spec_dd/3. done/2026-03-08_18:18_refactor-student-model`: renamed `student_management/admin.py` (to `learner_management`) and used the admin-interface skill. That is the origin of the Learner admin.
- `spec_dd/3. done/2026-02-19_19:25_deadlines` and the later `deadlines` specs: added deadline inlines and standalone admins to the learner and cohort admins.
- `spec_dd/3. done/2026-03-13_21:21_security-audit`: edited `content_engine/admin.py`.
- Delete-denial is already widespread. `docs/product/admin-interface.md` says authored content cannot be deleted in the admin except Articles, and that registrations with progress cannot be deleted.
- The `has_delete_permission` overrides on the content, form-definition, Organisation and Learner admins were added as guardrails. This spec supersedes them for the removed models, because removing the admin makes them moot.

## 2. Current admin surface in scope (from `admin.py` files)

- `content_engine/admin.py`: Topic, Article, Activity, CourseCategory, Course, CoursePart, ContentCollectionItem and File admins. It also has `ContentCollectionItemInline` and `CoursePartChildDueDateInline`, and it does `admin.site.unregister(FormQuestion)` then re-registers `FormQuestionWithSectionsAdmin` (lines 364-406).
  - **Trap:** `content_engine/admin.py` subclasses the `form_engine` `FormQuestionAdmin`, so removing the `form_engine` admins breaks the import and the unregister call. The two files have to be changed together.
- `form_engine/admin.py`:
  - Definition admins: QuestionOption (plus inline), FormContent, FormQuestion, FormPage, Form, and their inlines.
  - Answer and attempt admins: FormProgress (line 320), QuestionAnswer (453), QuestionAnswerFile (487). FormProgress has the answers change form and `answers_change_form.html`.
  - Per `sacaa-complianc-deletion-and-declaration-1-force-delete/research_user_deletion.md`, the answer and attempt admins currently have no `has_delete_permission` override, so staff can delete them today. The answers decision (no add, change or delete) closes this.
- `learner_management/admin.py`:
  - Learner admin with the seams `LEARNER_SUMMARIES`, `LEARNER_SUMMARIES_FIELD` and `ScopedLearnerAutocompleteSelect`, plus the read-only learner record inlines.
  - Cohort admin (`GuardedSiteAwareModelAdmin`) with the `CohortMembershipInline` and `CohortCourseRegistrationInline`.
  - LearnerCourseRegistration and CohortCourseRegistration admins.
  - `OrganisationCohortInline` and `OrganisationLearnerInline` (lines 392 and 412), which are consumed by the Organisation admin.
- `learner_progress/admin.py`:
  - TopicProgress, CourseProgress and CourseFormAttempt admins, with the course progress inlines.
  - It imports `LEARNER_SUMMARIES` and `LearnerAdmin` from `learner_management.admin` (line 23), appends `learner_progress_links` at line 466, and defines `LearnerCourseProgressInline` (line 370).
  - It must be edited in the same change as `learner_management/admin.py`, or the import fails at startup.
- `hr_attributes/admin.py`: `LearnerHRAttributesInline` (line 128) is the Learner seam; `OrganisationHRSettingsInline` (line 180) stays on Organisation. The `ListEntryAdmin` for JobTitle, Department and Location is separate and not obviously in scope.
- `organisations/admin.py`: `OrganisationAdmin` (line 31) pulls in the cohort and learner inlines and a Learner changelist link. It is the answered scope for removing those pieces.

## 3. Conflicts and dependencies found in other work

### 3a. Admin-only features hang off the removed admins (largest risk)

`docs/product/admin-interface.md` states several things that exist only inside the Learner, Cohort and registration admins:

- **Learner roster.** "An organisation's learners are curated in the admin and only there" (line 10, and line 52: the educator Learners section is read-only). An administrator associates a user with an organisation and deactivates a learner there.
  - Removing Learner admin removes the only place to create a Learner outside self-registration and `create_demo_data`.
  - Deactivation also exists in the educator interface (`educator_interface/actions.py`, `deactivate_learner`, with audit entries). The product doc is out of date on that point, which suggests the roster-curation statement needs rewriting rather than the feature moving.
- **Deadline overrides** (lines 12 and 83-115). Cohort and learner course-registration deadline overrides, pause and extend on the learner's course progress page, and the per-level deadline policy.
  - The doc says "Policy and overrides are admin-only: the educator interface has no screen for either" (line 115).
  - `deadlines/admin.py` defines `CohortDeadlineOverrideInline` and `LearnerDeadlineOverrideInline`, `CoursePauseInline` and `DeadlineExtensionInline`. Registration-level deadline config admins (`CohortCourseRegistrationDeadlineConfigAdmin`, `LearnerCourseRegistrationDeadlineConfigAdmin`) are standalone and may survive.
  - `spec_dd/1. next/deadlines/research_current_deadlines.md` and `research_deadline_integration_points.md` list the inline wiring in `learner_management/admin.py` (about lines 390 and 461).
  - The spec must decide: keep these inlines alive via some other admin, or accept the loss until the educator interface gets them (`deadlines-6-educator-management`, in `1. next`).
- **Registration rules.** Line 27 says a course registration's admin page shows which rule made it. That page goes.
- **HR attributes.** Line 26 says a learner's page records job title, department, location and four start dates. Removing Learner admin removes the only editing UI for `LearnerHRAttributes` (answered: remove the inline). `docs/product/hr-attributes.md` and `registration-rules.md` describe this as the way HR data is entered; those docs and any `spec_dd/1. next/corporate-job-course-recommendations*` specs rely on it.
- **Learner progress links** (line 62): the learner admin gathers cohorts, registrations and progress. This goes with the seam removal.
- **Registration delete guard** (line 56): "the admin refuses to delete [a registration with progress] and lists the progress standing in the way." The guard may also live in the model layer (line 161 says "underneath the admin the same protection holds"), so the tests for it may need to stay or move.

### 3b. `sacaa-compliance-4-attempt-review` (in progress)

- It is the only other in-progress spec touching these admins. It says the only per-attempt view today is the admin's `answer_groups` (`form_engine/admin.py`, via `form_engine/queries.py`). It leaves open whether the admin attempt answers move onto the new reader.
- Keeping FormProgress read-only in the admin (answered) is compatible. Removing the FormQuestion and FormPage admins does not affect `answer_groups`, but `answers_change_form.html` and `_answers.html` render `row.question.rendered_question` from the form definition. Those must keep working after the definition admins go.
- Both specs edit `form_engine/admin.py`, so there is a likely merge conflict.

### 3c. Other `spec_dd/1. next` specs that rely on these admins

- `sacaa-complianc-deletion-and-declaration-1-force-delete`: wants a "force delete" action on `UserAdmin` and `LearnerAdmin`. It notes `LearnerAdmin.has_delete_permission` is always False. Removing LearnerAdmin deletes that spec's second target. Its research also lists the unprotected answer and progress admins.
- `sacaa-complianc-deletion-and-declaration-2-quiz-declaration`: says a declaration would need adding to `FormProgressAdmin` to be seen. Read-only FormProgress stays, so this is still possible.
- `sacaa-compliance-content-versions-and-access-3-question-versions` and `-4-question-access`: the idea of removing question viewing from the admin is already in those specs.
  - `question-versions` notes that `FormQuestionAdmin` and `QuestionOptionInline` bypass `content_save` and "editing goes with it".
  - `question-access` flags `QuestionOptionAdmin` as the one admin page exposing the correct answer, and considers hiding or removing it. It does not settle it, so this spec effectively does it. The two specs should be marked as partly satisfied or at least cross-referenced.
- `reference-material-content` and `-1-authoring` (in progress): `research_educator_content.md` and `research_content_loader.md` list `content_engine/admin.py` changes (a reference part shows in `CoursePartAdmin`) and `reference-material-content-3-educator-reference` mentions "the Django admin inline for reference parts: `reference-material-content-1-authoring`". Removing content admin makes those admin changes moot. Check `reference-material-content-1-authoring`'s plan for admin tasks.
- `audit-log-coverage-gaps`: wants admin hooks in `SiteAwareModelAdmin` and `SiteAwareExportModelAdmin`. Those base classes remain, but the coverage list may shrink.
- `educator-interface-full-polish` and `educator-interface-refactor`: these are the destination of the learner and cohort work. Their prior comparison (`comparable-systems-learner-management.md`) is the best argument that removal is justified, but the educator interface must have the screens that replace admin-only functions.

## 4. Docs to update (not done in research)

- `docs/product/admin-interface.md`: lines 9-10, 16, 26-27, 52-62 and 83-115 (Learner, content-cannot-be-deleted, Organisation inlines, HR, registration rules, deadline overrides). Content-cannot-be-deleted and the registration delete guard sections need reconsidering.
- `docs/product/content-editing-workflow.md`: lines 13, 21, 52 and 109. The Article delete in admin, and "A price can also be set in the admin" (Course price), are not allowed once Course admin goes. This is a behaviour loss: price and Article removal need a new home or an explicit decision.
- `docs/product/hr-attributes.md`, `registration-rules.md` and `configuration-and-extension.md` (line 105) mention the admin as the place HR data is entered.
- `docs/product/educator-interface.md`: the Learners section is read-only; the admin-only roster statement should be reconciled.
- `docs/product/roadmap.md` and `docs/app_structure.md` may need a mention.
- The admin skill and the skills' `admin_unfold.md` documentation may describe `LEARNER_SUMMARIES`; the seam docs need updating.

## 5. External prior art (general knowledge, not fetched)

- WordPress-style and Django-CMS-style projects that moved editing from the built-in admin to a custom UI often reported the same problems: staff lost a low-level fix-it tool, so support had to use the shell; bookmarked admin URLs and links in emails or docs 404'd; permissions that were set up for admin models silently stopped doing anything.
- Django projects that dropped `ModelAdmin` for models that are still referenced by `autocomplete_fields` or `raw_id_fields` on other admins hit startup errors (`admin.E039`/`E040`: the related model admin must define `search_fields`, or must be registered). Here that applies to `autocomplete_fields` on the Learner, Cohort and registration admins from `deadlines/admin.py` and `registration_rules/admin.py`, as well as `ScopedLearnerAutocompleteSelect`.
- Django also refuses `reverse("admin:app_model_changelist")` for an unregistered model, so any `reverse("admin:...")` call, `format_html` link, or `{% url 'admin:...' %}` in templates will raise `NoReverseMatch` after removal. A grep of templates and Python for `admin:freedom_ls_` names would find them (not done here).
- Mitigation commonly used: a deprecation release first (read-only), then removal, plus a documented "register your own admin" note (this matches the answered "no toggle, register your own" decision).

## 6. Suggested checks for the spec

1. Run the `git log` above to confirm no prior removal attempt was reverted.
2. Grep for `admin:` reversals, `autocomplete_fields` and `raw_id_fields` that reference the removed models.
3. Grep tests: `learner_management/tests/test_admin.py`, `content_engine`, `form_engine`, `learner_progress`, `organisations`, `hr_attributes` and `deadlines` admin tests all need deleting or rewriting. `test_admin.py` in `learner_management` has 23 deadline hits per the deadlines research.
4. Decide where deadline overrides, pause and extend, price and Article deletion, and Learner creation live once their admins go.
5. Coordinate with `sacaa-compliance-4-attempt-review` and the two `sacaa-compliance-content-versions-and-access` specs about `form_engine/admin.py`.

status: ok
