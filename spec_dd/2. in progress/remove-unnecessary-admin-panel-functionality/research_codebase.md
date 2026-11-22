# Research: codebase impact of removing the unnecessary admin pages

Scope (from `answers.md`): remove the content_engine admin and the form_engine form-definition admins
outright; remove the learner_management admin and every seam into it; keep the learner_progress admins
(TopicProgress, CourseProgress, CourseFormAttempt) and form answer admins (FormProgress, QuestionAnswer,
QuestionAnswerFile) fully view-only (no add/change/delete, no bulk delete). No opt-in setting.
Paths are relative to the repo root. Line numbers are from the current worktree.

## 0. Headline findings (things the spec must decide)

1. **Admin checks E039/E040 and runtime autocomplete break across other apps.** Many admins outside the removed set use
   `autocomplete_fields` or Unfold `AutocompleteSelectFilter` pointing at models whose admin is going. Section 4 has the full list.
   Django's system check refuses to start (admin.E039/E040) when an `autocomplete_fields` target has no registered admin or no
   `search_fields`. Each of those admins needs a new answer: drop the field, use `raw_id_fields`, use a read-only display, or remove the admin.
2. **`deadlines` wires editable pieces into admins that become view-only or removed.** `freedom_ls/deadlines/admin.py` is the only
   place a deadline override, a pause or an extension can be created, and `docs/product/educator-interface.md:215` and
   `docs/product/admin-interface.md:115` say so ("Policy and overrides are admin-only"). Details in section 3.
3. **Several apps import symbols from the admins being removed at module import time** (`from freedom_ls.learner_management.admin import ...`).
   Removing the module without updating them is an ImportError at startup. Section 2.
4. **Things only editable in the removed admins today**: learner HR attributes (job title, department, location, 4 start dates), a Learner's
   organisation association and email-less create path (partly covered by educator "Add learner"), a LearnerCourseRegistration/CohortCourseRegistration
   add/change/deactivate (partly covered by educator interface), CourseCategory edit (explicitly overwritten by content_save, so no loss), File and
   Course price edit (docs `content-editing-workflow.md:109`: "A price can also be set in the admin"). Section 7.
5. `CourseProgressAdmin` is the host of the deadlines pause/resume/extend `actions_detail` and of deadline-override inlines. "Fully view-only" and these
   controls cannot coexist unless the spec says what happens to them.
6. No models, migrations, settings or URL config change: the admin is plain `admin.site` with `autodiscover`; there is no active `UNFOLD`
   sidebar/navigation dict (`config/settings_base.py:343` is a commented-out block). Permissions codenames (`view_learner`, etc.) still exist because they come from models.

## 1. Admin classes, registrations, inlines, forms affected

### 1.1 `freedom_ls/content_engine/admin.py` (remove module entirely)
Registered: `TopicAdmin`(Topic), `ArticleAdmin`(Article; the only content admin that allowed delete, `has_delete_permission` returns True),
`ActivityAdmin`(Activity), `CourseCategoryAdmin`(CourseCategory; no add, no delete), `CourseAdmin`(Course; inline `ContentCollectionItemInline`),
`CoursePartAdmin`(CoursePart; same inline), `ContentCollectionItemAdmin`(ContentCollectionItem; inline `CoursePartChildDueDateInline`), `FileAdmin`(File; form `FileAdminForm`).
Also in this module: `FormQuestionWithSectionsAdmin` (subclass of `form_engine.admin.FormQuestionAdmin`, adds "Sections" fieldset), and lines 405-406
`admin.site.unregister(FormQuestion); admin.site.register(FormQuestion, FormQuestionWithSectionsAdmin)`. That unregister/register goes with the module.
Imports it uses: `content_base.admin_filters.ContentTagListFilter` (also used by `form_engine/admin.py` FormAdmin; after the removal it has no non-test user, see 1.5).
Admin-only form: `freedom_ls/content_engine/forms.py::FileAdminForm`. Only user is `FileAdmin` and `freedom_ls/content_engine/tests/test_forms.py` (regression test). Safe to delete with the admin (check `forms.py` has nothing else).

### 1.2 `freedom_ls/form_engine/admin.py`
Remove: `QuestionOptionAdmin`, `FormContentAdmin`, `FormQuestionAdmin`, `FormPageAdmin`, `FormAdmin` (with `save_model` slug minting), and inlines
`QuestionOptionInline`, `FormContentInline`, `FormQuestionInline`, `FormPageInline`. Helper `_condition_label` only serves FormContentAdmin/FormPageAdmin.
Keep and make view-only: `FormProgressAdmin` (currently has add/change/delete; has `get_readonly_fields` that opens `user`/`form` on add, `render_change_form`
adds answers context + application link, `change_form_template = "admin/form_engine/answers_change_form.html"`), `QuestionAnswerAdmin` (editable fieldsets, default delete),
`QuestionAnswerFileAdmin` (already `has_add_permission` False; no change/delete override; custom `get_urls` download route `admin:freedom_ls_form_engine_questionanswerfile_download`
wrapped in `admin_view`, uses `question_answer_file_download_view` in `form_engine/views.py`).
Keep helpers used by others: `answers_context` (imported by `course_applications/admin.py:14`), `applicant_label`, `_with_applicant_select_related`, `FormProgressCompletionFilter`.
`FormProgressAdmin.list_filter` has `("form", AutocompleteSelectFilter)` which needs a registered Form admin with `search_fields` (it is being removed): needs replacing (e.g. `RelatedDropdownFilter` or plain `"form"`).
`QuestionAnswerAdmin.list_filter` `"question__form_page__form"` is a plain related filter and works without a registered admin.
`list_select_related` / `answers_change_form.html` template (`freedom_ls/form_engine/templates/admin/form_engine/`) stay.

### 1.3 `freedom_ls/learner_management/admin.py` (remove module entirely, except decisions on `USER_ERASURE_CASCADE_MODELS`)
Registered: `LearnerAdmin`(Learner; form `LearnerAdminForm`; `has_delete_permission` False; `get_search_results` honours scoped cohort params; `get_inlines`/`get_fields` hide on add),
`CohortAdmin`(Cohort; `GuardedSiteAwareModelAdmin`; form `CohortAdminForm`; inlines `CohortMembershipInline`, `CohortCourseRegistrationInline`; carries an open `@claude:` comment about verifying the guardian object-permissions page, lines 339-344: the comment goes with the class, since it is about the pairing for this model only, but Organisation also uses `GuardedSiteAwareModelAdmin`),
`LearnerCourseRegistrationAdmin` (form `LearnerCourseRegistrationAdminForm`), `CohortCourseRegistrationAdmin` (form `CohortCourseRegistrationAdminForm`).
Support classes/functions: `LEARNER_SUMMARIES`, `LEARNER_SUMMARIES_FIELD`, `SCOPE_TO_*`, `_SCOPE_LOOKUPS`, `narrow_learners`, `ScopedLearnerAutocompleteSelect`, `ReadOnlyLearnerRecordInline`,
`LearnerCohortMembershipInline`, `LearnerRegistrationInline`, `CohortMembershipInline`, `CohortCourseRegistrationInline`.
Seams into the Organisation admin (lines 392-482): `OrganisationCohortInline`, `OrganisationLearnerInline`, `organisation_learner_search_link` (reverses
`admin:freedom_ls_learner_management_learner_changelist`), then `OrganisationAdmin.inlines = [..., OrganisationCohortInline, OrganisationLearnerInline]` and `ORGANISATION_SUMMARIES.append(organisation_learner_search_link)`.
Side effect that is not about the UI: line 279 `USER_ERASURE_CASCADE_MODELS.add(Learner)` (set defined in `freedom_ls/accounts/admin.py:26`, read at `accounts/admin.py:201`
and by `UserAdmin.get_deleted_objects` to strip `perms_needed`). If the module goes, this registration must move (e.g. to `accounts` or another app) or erasing a user from the User admin
will start refusing because `Learner` delete permission is no longer vouched for. (Other adders: `course_applications/admin.py:29-30`, `referral_tracking/admin.py:92,152-153`.)
Admin-only forms (`freedom_ls/learner_management/forms.py`): `CohortAdminForm`, `LearnerAdminForm`, `LearnerCourseRegistrationAdminForm`, `CohortCourseRegistrationAdminForm`.
Whole file is "Admin forms for learner_management models"; only `learner_management/admin.py` and `learner_management/tests/test_forms.py` use them (educator_interface has its own `CohortForm` in `educator_interface/forms.py:126`, unrelated). The whole file can go if nothing else lives in it.
`OrganisationAdmin` itself and `ORGANISATION_SUMMARIES` stay (`freedom_ls/organisations/admin.py`); the seam list ends up empty. `OrganisationAdmin.get_fields` already hides the summaries field when the list is empty, and `inlines` is still extended by `hr_attributes` (`OrganisationHRSettingsInline`). Whether to keep the now-unused `ORGANISATION_SUMMARIES`/`SUMMARIES_FIELD` machinery is a spec decision (it is tested in `organisations/tests/test_admin.py:319-344`).

### 1.4 Seam contributors elsewhere
- `freedom_ls/hr_attributes/admin.py:24,177`: imports `LearnerAdmin` and does `LearnerAdmin.inlines = [..., LearnerHRAttributesInline]`. Remove import, `LearnerHRAttributesInline`, `_picker_querysets`, `_PICKER_MODELS`, the line-177 wiring (the `Learner` import stays only if still used). `ListEntryAdmin` (JobTitle/Department/Location) stays; it has `autocomplete_fields = ["organisation"]` which still resolves (OrganisationAdmin stays, `search_fields=["name"]`). `OrganisationHRSettingsInline` on `OrganisationAdmin` stays.
- `freedom_ls/learner_progress/admin.py:23,370-466`: `from freedom_ls.learner_management.admin import LEARNER_SUMMARIES, LearnerAdmin`; `LearnerCourseProgressInline`, `_LEARNER_RECORD_LINKS`, `learner_progress_links` (reverses `admin:freedom_ls_learner_progress_topicprogress_changelist` and `..._courseformattempt_changelist`), plus `LearnerAdmin.inlines = ...` and `LEARNER_SUMMARIES.append(...)`. All of 370-466 goes.
- `freedom_ls/deadlines/admin.py:71,686-689`: `from freedom_ls.learner_management.admin import CohortCourseRegistrationAdmin`; appends `CohortDeadlineOverrideInline` to it. See section 3.
- `freedom_ls/registration_rules/admin.py:36,596-612`: `from ...learner_management.admin import LearnerCourseRegistrationAdmin`; adds `registration_rule` readonly field and fieldset to it. `registration_rule` helper (572-593) reverses `admin:freedom_ls_registration_rules_registrationrule_change`. All of that goes. `registration_rules/admin.py:347` uses `has_perm("freedom_ls_learner_management.view_learner")` for "can_view_learners" in the preview; this is a model permission, still valid, but the doc `registration-rules.md:43-45` ("A registration's admin page shows the rule that made it") becomes untrue.
- `freedom_ls/qa_helpers/management/commands/qa_create_org_cohort_pagination.py:34`: `from freedom_ls.learner_management.admin import OrganisationCohortInline` (and line 160 prints an admin URL). The command exists to QA that inline; it needs removal or rewrite.
- `freedom_ls/course_applications/admin.py:14`: `from freedom_ls.form_engine.admin import answers_context` (stays, form_engine.admin stays). Lines 129,132,148,150 use `admin_change_link(request, obj.course)`; `admin_change_link` (`site_aware_models/admin.py:108`) catches `NotRegistered` and renders plain text, so a removed Course admin degrades to text, no crash. Tests may assert a link (see 5).
- `freedom_ls/form_engine/admin.py:415`: `admin_change_link` to the application; unaffected.

### 1.5 Filters / helpers left stranded
`freedom_ls/content_base/admin_filters.py::ContentTagListFilter` (tests: `content_base/tests/test_admin_filters.py` uses `admin:freedom_ls_content_engine_topic_changelist`). Non-test users are content_engine and form_engine admins only (also grep shows `course_applications`, `deadlines`, `learner_progress` use the other filters from `site_aware_models/admin_filters.py`, not this one). After the removal it is unused: delete it and its test, or keep as shared infrastructure; spec decision.

## 2. Imports from the admin modules (all of them)
- `content_engine.admin` is imported by: `content_engine/tests/test_admin.py:16` only.
- `form_engine.admin` is imported by: `content_engine/admin.py:11` (FormQuestionAdmin), `course_applications/admin.py:14` (`answers_context`), `form_engine/tests/test_admin.py:16`.
- `learner_management.admin` is imported by: `learner_progress/admin.py:23`, `deadlines/admin.py:71`, `hr_attributes/admin.py:24`, `registration_rules/admin.py:36`, `qa_helpers/.../qa_create_org_cohort_pagination.py:34`, `learner_management/tests/test_admin.py:23`.
- `learner_progress.admin` is imported by: `deadlines/admin.py:72` (CourseProgressAdmin), `learner_progress/tests/test_admin.py:20` (`learner_progress_links`, `quiz_result`).
- `organisations.admin` is imported by: `learner_management/admin.py:20`, `hr_attributes/admin.py:26`, `organisations/tests/test_admin.py`.
No concrete-project hook or `claude_plugins` code imports these modules (checked `claude_plugins/fls-dev`; only `resources/concrete_spec_integration.md:106` mentions the conformance test, which just counts registrations).
`freedom_ls/contrib/conformance/test_admin_site.py` asserts the registry is non-empty; still true afterwards.
No settings reference the admin classes: `config/urls.py` uses `admin.site.urls`; `freedom_ls/base/admin_config.py` only names `default_site`; `UNFOLD = {...}` in `config/settings_base.py:343` is commented out, so there is no sidebar/navigation config to edit. `freedom_ls/base/templates/partials/header_bar_user_menu.html:18` links to `admin:index` only.

## 3. `deadlines` app: the biggest knock-on
`freedom_ls/deadlines/admin.py` (class/function names):
- `DeadlineOverrideInline` (185), `CohortDeadlineOverrideInline` (360), `LearnerDeadlineOverrideInline` (365): the editable override inlines (docs: "Overrides ... set in the Django admin"). Cohort one is attached to `CohortCourseRegistrationAdmin` (686-689, removed admin), learner one to `CourseProgressAdmin` (694-699).
- `CoursePauseInline`, `DeadlineExtensionInline` (read-only, on `CourseProgressAdmin`); `effective_deadlines`, `effective_deadline_policy` read-only fields and a "Deadlines" fieldset set via `setattr` on `CourseProgressAdmin` (700-723).
- `pause_course_action`, `resume_course_action`, `extend_deadline_action` (`unfold_action(..., permissions=["change"])`), `_get_urls`, `_get_actions_detail`, and the `setattr(CourseProgressAdmin, ...)` block 808-822; views `pause_view`, `resume_view`, `extend_view` in `deadlines/admin_views.py` (redirect target line 58 reverses `admin:freedom_ls_learner_progress_courseprogress_change`).
- `CoursePauseAdmin`, `DeadlineExtensionAdmin` (already fully read-only), and five deadline-config admins with `autocomplete_fields` (see section 4).
Conflicts with answers.md: `CourseProgressAdmin` must be view-only, but pause/resume/extend actions require `change` permission and write data, and the override inlines are editable. If `has_change_permission` is False they simply disappear (`permissions=["change"]`), which would silently remove the only way to pause/extend/override. Spec must say: keep CourseProgressAdmin view-only and relocate/remove these, or carve out an exception. `deadlines` also decorates `CourseProgressAdmin.get_urls`/`get_actions_detail` by monkeypatch, so the view-only change must keep those hooks coherent.
Tests: `deadlines/tests/test_admin.py` (CohortCourseRegistration change/add at lines 59-60, CourseProgress change/add/pause/extend at 584, 1022, 1266, 1404) and `deadlines/tests/test_admin_views.py` (PAUSE/RESUME/EXTEND/CHANGE URL names).

## 4. Autocomplete (E039/E040) and filter dependencies on removed admins
`autocomplete_fields` whose target model's admin is being removed (each needs a decision):
- `learner_progress/admin.py` (admins being kept view-only; autocomplete only matters on edit forms, so drop it when the admin is read-only): `TopicProgressAdmin` 188 (`collection_item`, `topic` are content_engine; `course_progress` stays), `CourseProgressAdmin` 246-252 (`learner`, `course`, `learner_registration`, `cohort_registration`, `last_accessed_item`), `CourseFormAttemptAdmin` 333 (`collection_item`). Also Unfold `AutocompleteSelectFilter` in `list_filter`: `TopicProgressAdmin` 175-177 (learner, topic, course), `CourseProgressAdmin` 231-232 (learner, course), `CourseFormAttemptAdmin` 320-322 (learner, form, course). These filters call the target admin's autocomplete endpoint, which needs a registered admin with `search_fields`; they will break at runtime (not at check time) once Learner/Topic/Course/Form admins are gone. `RelatedDropdownFilter` entries (organisation, cohort) are fine.
- `deadlines/admin.py`: `OrganisationDeadlineConfigAdmin` 863 (organisation: fine), `CourseDeadlineConfigAdmin` 870 (course: BREAKS), `CohortDeadlineConfigAdmin` 877 (cohort: BREAKS), `CohortCourseRegistrationDeadlineConfigAdmin` 884 (cohort_registration: BREAKS), `LearnerCourseRegistrationDeadlineConfigAdmin` 894 (learner_registration: BREAKS); `CoursePauseAdmin` 585 and `DeadlineExtensionAdmin` 652 use `("course_progress__course", AutocompleteSelectFilter)` (BREAKS at runtime). Note these deadline-config admins are editable and, with cohort/course/registration admins gone, have nothing to pick from; raw-id or removal is a spec call.
- `messaging_policy/admin.py`: `CohortMessagingConfigAdmin` 64 (cohort: BREAKS), `LearnerMessagingConfigAdmin` 73 (learner: BREAKS), `LearnerCourseRegistrationMessagingConfigAdmin` 86 (registration: BREAKS), `CohortCourseRegistrationMessagingConfigAdmin` 95 (registration: BREAKS); `OrganisationMessagingConfigAdmin` 55 fine. These admins' `search_fields` reference `cohort__name` etc. (fine, they are about their own queryset).
- `course_interest/admin.py:23`: `autocomplete_fields = ["user", "course"]` (course: BREAKS; user stays since UserAdmin remains, check its `search_fields`).
- `registration_rules/admin.py:151`: `autocomplete_fields = ["organisation", "course"]` (course: BREAKS).
- `hr_attributes/admin.py:41`: organisation: fine.
- `course_applications/admin.py:83,218`: `("course", AutocompleteSelectFilter)` (BREAKS at runtime).
- `form_engine/admin.py:332`: `("form", AutocompleteSelectFilter)` (BREAKS at runtime).
Also `accounts/admin.py` (User admin), `api_admin`, `reports/admin.py`: `reports` admin generates cohort reports from a cohort dropdown (`GeneratedReport`, own form), no ModelAdmin dependency found, but not exhaustively checked.
Run `uv run python manage.py check` after the removal to enumerate the E039/E040 failures; the runtime-only `AutocompleteSelectFilter` ones need a test that opens each changelist.

## 5. Tests covering these admins (delete, rewrite or re-home)
Delete with the admins:
- `freedom_ls/content_engine/tests/test_admin.py` (26 hits), `freedom_ls/content_engine/tests/test_forms.py` (FileAdminForm).
- `freedom_ls/learner_management/tests/test_admin.py` (13 hits: LearnerAdmin, CohortMembershipInline narrowing, CohortAdmin), `learner_management/tests/test_forms.py` (the 4 admin forms; check whether other tests in this file cover non-admin forms).
- `freedom_ls/content_base/tests/test_admin_filters.py` (uses `admin:freedom_ls_content_engine_topic_changelist`).
- Form-definition parts of `freedom_ls/form_engine/tests/test_admin.py` (lines ~105-131 Form change/delete, 278 form add, 455 formquestion change, 689-740 formpage/formcontent); the FormProgress/QuestionAnswer/QuestionAnswerFile parts (141-250, 309, 348, 583) must be rewritten for view-only (line 234 `_add`, 248 `_delete` currently parametrised over those models; 583 asserts formprogress add).
Rewrite:
- `freedom_ls/learner_progress/tests/test_admin.py` (12 hits; lines 189 and 180-205 test the LearnerAdmin seam via `learner_progress_links`, remove; others should assert view-only).
- `freedom_ls/hr_attributes/tests/test_admin.py` 242-243: `LEARNER_CHANGE_URL_NAME`/`LEARNER_ADD_URL_NAME` (the LearnerAdmin HR inline tests; remove those tests).
- `freedom_ls/organisations/tests/test_admin.py` ~298-344: tests assert the inlines/summaries list is non-empty (`assert ORGANISATION_SUMMARIES` line 319, `== OrganisationAdmin.inlines` line 309) and monkeypatch it.
- `freedom_ls/site_aware_models/tests/test_admin.py` 22-91: builds `GuardedSiteAwareModelAdmin(Cohort, admin.site)` and asserts `admin:freedom_ls_learner_management_cohort_change` link (`admin_change_link`); these tests must move to `Organisation` (a still-registered guardian admin).
- `freedom_ls/site_aware_models/tests/test_admin_filters.py:21` uses `admin:freedom_ls_learner_progress_topicprogress_changelist` (stays valid if the admin stays).
- `freedom_ls/messaging_policy/tests/test_admin.py:356-362` (`test_the_cohort_admin_page_carries_no_messaging_inline` reverses `admin:freedom_ls_learner_management_cohort_change`); remove. Same file/`tests/test_messages_button.py` may reference admin pages for cohorts/learners (not exhaustively read).
- `freedom_ls/registration_rules/tests/test_admin.py:123` (`LearnerCourseRegistration` change page), `registration_rules/tests/test_signals.py:235-306` and `847-865` (use LearnerCourseRegistration and Learner admin change forms to test detach/deactivate via the admin), `registration_rules/tests/playwright/test_rule_preview_flow.py:117` (changelist of learnercourseregistration).
- `freedom_ls/learner_progress/tests/test_signals.py:649-660` (`test_a_registration_created_through_the_admin_notifies_once` posts to `..._learnercourseregistration_add`).
- `freedom_ls/deadlines/tests/test_admin.py` (CohortCourseRegistration admin, CourseProgress change/add/pause/extend) and `test_admin_views.py`.
- `freedom_ls/course_applications/tests/test_admin.py` (16 hits; lines 176, 252, 388-389 reverse form_engine admin URLs for answer files / form progress; check whether any assert a link to the Course admin or Form admin) and `form_engine/tests/playwright/test_admin_answers_layout.py:68`.
- `freedom_ls/accounts/tests/test_admin.py`: should be checked for user-erasure tests that depend on `Learner` being in `USER_ERASURE_CASCADE_MODELS` (the 15 hits were not individually read).
- `freedom_ls/educator_interface/tests/test_learner_import.py` (66 grep hits on `admin|LearnerFactory`, almost certainly the factory; not admin-dependent).
Tests that only need to keep passing: `freedom_ls/contrib/conformance/test_admin_site.py`, `.../tests/test_conformance_meta.py`.

## 6. Existing read-only patterns to reuse
- `freedom_ls/referral_tracking/admin.py:55` `ReadOnlyAdminMixin` (`has_add_permission`, `has_change_permission`, `has_delete_permission` all False). Local to that app; adding it to `site_aware_models/admin.py` (next to `SiteAwareModelAdmin`) and reusing in learner_progress/form_engine avoids repeating it (CLAUDE.md "avoid repeating code").
- Hand-rolled read-only: `accounts/admin.py:63-69` and `109-115` (LegalConsent etc.), `audit_log/admin.py:38-46`, `course_applications/admin.py:153-165,239-251`, `mail/admin.py:101-109`, `reports/admin.py:67-88`, `webhooks/admin.py:183-191,228-236`, `deadlines/admin.py:603-610,674-681` (`CoursePauseAdmin`, `DeadlineExtensionAdmin`) and inline version `deadlines/admin.py:484 ReadOnlyInline`.
- `SiteAwareModelAdmin` (`site_aware_models/admin.py:25`) only sets `exclude = ["site"]` and Media; `GuardedSiteAwareModelAdmin` (line 64) is `ModelAdmin + GuardedModelAdmin` for Organisation (and Cohort). `SiteAwareExportModelAdmin` adds CSV export, gated on `has_view_permission` (the course_applications/accounts exports).
- Bulk delete: Django's `delete_selected` is only offered when `has_delete_permission` is True for the model, so `has_delete_permission` returning False removes it (as `LearnerAdmin` already relied on). Caveat: with `has_change_permission` False, Django's change view renders read-only if the user has view permission, so `fieldsets` containing editable fields still display (read-only). The progress admins' `autocomplete_fields` can then simply be dropped.
- Inlines on view-only admins also need to be non-editable (`CourseProgressTopicInline`/`CourseProgressFormAttemptInline`/`CourseProgressItemInline` already have `can_delete=False`, `max_num=0`, `has_add_permission` False but not `has_change_permission`; they only list `readonly_fields = fields`, so there is nothing editable; `QuestionOptionInline`, etc., go away).
- Deleting a view-only parent: Django collects related objects; with delete False this is moot. But `UserAdmin` delete cascades to FormProgress etc. and uses `USER_ERASURE_CASCADE_MODELS` to strip `perms_needed`; FormProgress/TopicProgress/CourseProgress/QuestionAnswer/Learner (and Cohort-related) models are not in it, so deleting a user with progress today already depends on the `perms_needed` check passing; after making those admins delete-less, the permission lookup uses `ModelAdmin.has_delete_permission` only for registered models, so a user with progress becomes harder to delete in the User admin unless these models join `USER_ERASURE_CASCADE_MODELS`. Related sibling spec: `spec_dd/1. next/sacaa-complianc-deletion-and-declaration-1-force-delete/` (touches `LearnerAdmin`, `USER_ERASURE_CASCADE_MODELS`; it plans a force-delete admin action on `LearnerAdmin`, which this spec removes; the two specs conflict and should be reconciled).

## 7. Capabilities only editable through the removed admins, and educator interface coverage
- **Learner (organisation membership)**: create/associate and deactivate. Educator interface has "Add learner", deactivate/reactivate, CSV import (`docs/product/educator-interface.md:56,78`). `docs/product/admin-interface.md:10,52` says roster is admin-only and the educator Learners section is read-only: the product docs are stale versus the educator doc, and both must be reworked. Moving a learner between organisations: no educator path found.
- **Cohort**: educator interface has `CohortForm` (`educator_interface/forms.py:126`, `views.py:332,476,490`) for create/edit; membership and cohort course registrations are managed by cohort admins in the educator interface (`educator-interface.md:56,134`). Cohort `is_active` toggling in educator not verified.
- **LearnerCourseRegistration / CohortCourseRegistration**: educator interface registers/deregisters (docs `educator-interface.md:134`); the admin's `self_registered` and rule detail display (registration_rules) have no equivalent.
- **LearnerHRAttributes** (job title, department, location + 4 dates): only editable in `LearnerAdmin` via `LearnerHRAttributesInline`; `docs/product/hr-attributes.md:12` says "no learner, educator-interface or CSV surface exists". Removing LearnerAdmin removes the only way to enter HR attributes, which in turn makes the registration_rules feature (rules match on those attributes) inert for new data. `ListEntryAdmin` (the lists themselves) stays, as does `OrganisationHRSettingsInline`. Needs an explicit spec decision (accept, or the educator interface/import gets this later).
- **CourseCategory** edit: also overwritten by `content_save` (admin-interface.md:163); no loss. **File**: content_save only. **Course price**: docs `content-editing-workflow.md:109` says "A price can also be set in the admin, and a price set there survives a later content re-save"; the CourseAdmin fieldset "Price" (content_engine/admin.py:228-242) is the only editing UI, so that behaviour disappears (educator interface has no price edit; `educator-interface.md:56`-ish "no admin or educator toggle ... except price" in `content-editing-workflow.md:56`).
- **Article delete** (the only admin delete in content_engine) goes away; `docs/product/content-editing-workflow.md:52` and `admin-interface.md:16,159` describe it.
- **Deadline overrides/pause/extend and per-cohort-registration deadline config**: admin-only (docs `educator-interface.md:215`, `admin-interface.md:115`). See section 3.
- **Cohort object permissions (guardian) page**: `docs/product/admin-interface.md:38-40` "Cohort Permissions"; Organisation retains one, Cohort loses it. Educator access does not use it (role assignments), per the same doc.
- **Course interest, messaging config, deadline config rows referencing cohorts/learners/registrations**: reachable only via the admins that stay but whose pickers break (section 4).

## 8. Docs and skills that describe these admin pages (to update)
- `docs/product/admin-interface.md` (primary; stale bullets 9-18, 26-27, plus sections "Organisation Management", "Learner Rosters", "Learner Progress", "Deadline Overrides", "Pausing and extending", "Content Cannot Be Deleted", "Cohort Permissions"). Its `_Last updated_` date line and bullet 15 ("A course registration that has recorded progress cannot be deleted...") describe model-level protection; the admin-side wording goes.
- `docs/product/educator-interface.md` lines 54, 169, 212, 215 (email changes in the admin: that is the User admin, stays; deadlines are admin-only).
- `docs/product/hr-attributes.md` lines 7, 16, 18 (panel on a learner's admin page, screenshot `screenshots/admin_learner_hr_attributes.png`), `docs/product/registration-rules.md:43-47` ("A registration's admin page shows the rule that made it"), `docs/product/learner-tracking.md:12,41` (admins see progress in admin; learner admin page gathers progress), `docs/product/content-editing-workflow.md:13,21,52,56,109`, `docs/product/configuration-and-extension.md:105`, `docs/product/README.md:24`, `docs/product/roadmap.md` (19 hits on admin), `docs/product/reports.md`, `docs/product/learner-experience.md:311,325` (links to admin interface anchors `#deadline-overrides`, `#organisation-management`, `#learner-rosters` which may be renamed), `docs/product/security-and-data-handling.md` (19 hits, not read).
- `claude_plugins/fls-dev/resources/admin_interface.md` lines 12-16, 46-49, 65-70: examples use `Topic`/`Cohort` as illustration (will be misleading, since TopicAdmin and CohortAdmin no longer exist; examples only, but "all site-aware models MUST use SiteAwareModelAdmin" stays true). `claude_plugins/fls-dev/skills/admin-interface/SKILL.md` unaffected beyond examples. `claude_plugins/django-stack/resources/admin_*.md` are generic and must not change.
- `.claude/agent-memory/sdd-qa-data-helper/*` hold QA references to removed pages (`reference_detaching_a_cohort_membership.md`, `reference_org_cohort_inline_pagination.md`, `reference_organisation_admin_summary_counts.md`, `MEMORY.md:47`); these are agent notes, not product docs, flagged for the owner to prune.
- Done-spec archives under `spec_dd/3. done/` mention admin URLs but are history; leave them.
- `docs/product/screenshots/` contains images of the removed pages (`admin_learner_hr_attributes.png` seen referenced; others not enumerated).

## 9. Suggested order of work (not a plan, just what depends on what)
1. Decide the deadlines and messaging_policy/course_interest/registration_rules replacements for broken `autocomplete_fields` and `AutocompleteSelectFilter` (section 4); this drives most of the editing.
2. Add a shared view-only mixin in `site_aware_models/admin.py` and apply it to the 3 progress + 3 answer admins; strip their `autocomplete_fields`, editable fieldsets, `get_readonly_fields` tweak, and the `AutocompleteSelectFilter`s that point at removed admins.
3. Remove the 3 admin modules and the seam code in `hr_attributes`, `learner_progress`, `deadlines`, `registration_rules`, `organisations` (summaries), the QA command, and the admin-only forms.
4. Move `USER_ERASURE_CASCADE_MODELS.add(Learner)` and reconsider adding the progress models.
5. Update/delete tests (section 5), then docs (section 8). Run `uv run python manage.py check` and open every remaining changelist/change page (a test per admin) since the Unfold filter breakage is runtime-only.
No migrations are needed; there is no model change.

status: ok
