# Research: codebase (what the move touches, reuses, conflicts with)

Verified against the current tree on branch `educator-interface-refactor-1-scaffolding-and-common`
(extract_panels_framework 1-3 have landed). Paths are under `freedom_ls/educator_interface/` unless
stated. "V" = `views.py`, "A" = `actions.py`, "F" = `filters.py`, "R" = `reporting.py`.

## 0. Headline findings (the idea needs these corrections)

1. `RelationLinkColumn` no longer exists anywhere in `freedom_ls/` (the whole-repo grep finds only spec
   text). Drop it from `common/tables.py`.
2. `ShowInactiveFilter` is gone (no match in code). The toggle is now the framework `ToggleFilter` plus
   `CohortDataTable.inactive_toggle_key` logic (V:442, 505, 522-525). That logic is cohort code and stays.
   `common/filters.py` holds only `VisibleCourseFilter`.
3. `_uuid_param` and `_staff_member_param` do not exist in `actions.py` any more (grep: no match). Only
   `_uuid_from` (A:289) and `_action_params` (A:296) remain.
4. Four of the six "picker dialog helpers" are gone: `_refresh_on_change`, `_picker_on_get`,
   `_prepare_register_dialog`, `_picker_fragment` no longer exist in `educator_interface` (no match in the
   repo outside spec_dd; `panel_framework/actions.py` now owns the generic picker behaviour, e.g. its
   `get_empty_message` hook at `panel_framework/actions.py:392,410`). Still present: `_empty_message`
   (A:1228), `_picker_title` (A:1234), plus `_register_title` (A:1248), which the idea does not list.
5. `LazyBodyPanel` and `render_region` moved to `freedom_ls/panel_framework/lazy_panels.py` (`__all__` at
   :14, `render_region` :20, `LazyBodyPanel` :30). R:41-46 imports them from there. They do not go to
   `common/report.py`. (Spec 2 idea line 26 and spec 6 idea line 32 still say they come from
   `panels/common/report.py`: those sibling ideas are stale on this point.)
6. `BULK_ACTIONS`, `register_bulk_action`, `bulk_actions_for_table` live in
   `freedom_ls/panel_framework/bulk_actions.py:557,560,568` (exported in `__all__` at :29,:39,:41).
   Not moved here.
7. The table helper group has a hidden dependency: `_registration_columns` (V:423) calls
   `_active_status_column` (V:399), which calls `active_status_badge`. `_active_status_column` is used 3
   times in V (426, 478, 2549) and is not in the idea's list. It must go to `common/tables.py` too (or
   `_registration_columns` would import back from `views.py`, a cycle). `common/tables.py` then imports
   `active_status_badge` from `common/badges.py`.
8. `quick_views.py` already has two lazy imports from `views.py` as a cycle workaround (`quick_views.py:62-74`).
   `_active_status_badge` (L70-74) becomes a plain import from `common/badges` once moved. `_learner_status_badge`
   (L62-67) must stay lazy: `learner_status_badge` is learner code that stays in `views.py` (V:1525).

## 1. Per-name inventory (current location, current name)

### `common/request.py`
| Name | Current | Notes |
|---|---|---|
| `LAST_ORGANISATION_SESSION_KEY` | V:253 (comment 250-252) | used V:2889, 3501, 3502 |
| `OrganisationScopedRequest` | V:256-279 | docstring (V:260-265) mentions quick_views' TYPE_CHECKING import; reword on move |
| `OrganisationSectionConfig` | V:282-331 (`SectionConfigBase` subclass) | uses `can`, `can_on_any`, `VIEW_COHORT`, `VIEW_ORGANISATION_STAFF`, `active_organisation_admins` |
Idea's range 249-327 is now 250-331. Subclassed by `CohortConfig` V:1927, `LearnerConfig` V:1957,
`CourseConfig` V:2608, `DashboardConfig` V:2628, `StaffConfig` V:2729, `AuditLogConfig` V:2837.
Request module deps (all leaf, no flat module): `django.http.HttpRequest`, `Organisation`, `Cohort`,
`GrantableRole` (`learner_management.role_assignment`), `SectionConfigBase`
(`panel_framework.views`), `can`, `can_on_any`, `VIEW_COHORT`, `VIEW_ORGANISATION_STAFF`,
`active_organisation_admins`.

### `common/tables.py`
| Name | Current |
|---|---|
| `_interface_link` | V:345-370 |
| `_learner_column` | V:385-396 |
| `_registration_columns` | V:423-433 |
| `_active_status_column` (not in idea; required by `_registration_columns`) | V:399-405 |
| `RelationLinkColumn` | DOES NOT EXIST |
Stay in V (used by one or two areas): `_course_title_column` V:373 (uses `_interface_link`; used V:1580,
2078), `_cohort_links_column` V:408 (used V:654, 2101). Both then import `_interface_link` from `common`.
Idea range 341-409 is now 345-433. The `# TODO` block (V:334-342) sits immediately above `_interface_link`.
Table deps: `Column`, `BadgeColumn` (`panel_framework.tables`), `attrgetter`, `Literal`,
`active_status_badge` (-> `common/badges`). Note `_interface_link` hard-codes `url_name="educator_interface:interface"`
(app URL name, fine).
Also needed imports left behind in V after the move: `replace`, `attrgetter` (check; `attrgetter` is only used by
`_active_status_column` in this region, `replace` by `_course_title_column`), `Literal`.

### `common/badges.py`
| Name | Current |
|---|---|
| `active_status_badge` | V:1531-1535 |
| `inactive_badge` | V:1538-1543 |
Idea range 1442-1456 is now 1531-1543. Deps: `StatusBadge` (`panel_framework.views`). Used in V at 404 (via
`_active_status_column`), 815, 1555, 1871; `quick_views.py:72`. `learner_status_badge` (V:1525) and
`_LEARNER_STATUS_TONES` (V:1518) stay (learner).

### `common/ids.py`
`uuid_or_404`: V:1390-1395 (idea 1301-1308). Used V:1356, 2476, 2492, 2974. Deps: `UUID`, `Http404`.
No importer outside V (grep clean).

### `common/filters.py`
`VisibleCourseFilter`: F:42-71 (idea: 64). Subclassed by `LearnerCourseFilter` F:123 (stays), used V:506
(`CohortDataTable.get_filters`). `ShowInactiveFilter`: gone. Deps: `RelatedChoiceFilter`,
`CohortCourseRegistration`, `courses_visible_to`, `OrganisationScopedRequest` (F:38-39 TYPE_CHECKING).
F keeps `may_see_staff_roles` (F:133, imported by A:50 and V's filters import block) and the learner/staff/audit filters.

### `common/actions.py`
| Name | Current |
|---|---|
| `EducatorReasonMixin(ReasonMixin)` | A:379-382 (`reason_form_class = EducatorReasonForm`) |
| `_uuid_from` | A:289-293 |
| `_action_params` | A:296-299 |
| `_uuid_param` | does not exist |
| `_staff_member_param` | does not exist |
| `_empty_message` | A:1228-1231 |
| `_picker_title` | A:1234-1245 |
| `_register_title` (not in idea) | A:1248-1260 (uses `_picker_title`; used A:603, 819) |
| `_refresh_on_change`, `_picker_on_get`, `_prepare_register_dialog`, `_picker_fragment` | do not exist |
`ReasonMixin` itself is imported from `panel_framework.actions` (A:166). `EducatorReasonMixin` users (all in A):
502, 545, 655, 739, 839, 1068, 2395, 2487, 2755 (nine; `tests/invariants/test_reason_mixin.py:23,35` asserts
`len(found) == 9` and uses `actions.EducatorReasonMixin`, and walks `inspect.getmembers(actions, inspect.isclass)`).
`_uuid_from`/`_action_params` users in A: 1034, 1412, 2282, 2454, 2471, 2534 (staff and learner/cohort code).
`_empty_message` users A:823, 1294, 1353. `_picker_title` users A:1258, 1288.
Deps for `common/actions.py`: `EducatorReasonForm` from flat `forms.py` (leaf: forms/staff/events/paths/
exceptions/user_display/messaging/learner_import import nothing from views/actions/filters/reporting), `Course`,
`Organisation`, `forms`, `Model`, `Callable`, `Mapping`, `UUID`, `Http404`.
IMPORTANT for `test_reason_mixin.py`: moving `EducatorReasonMixin` out of `actions` means the module attribute
`actions.EducatorReasonMixin` disappears unless A imports it (it will, as a base class name), so
`cls is not actions.EducatorReasonMixin` still works via A's import. But the "len(found) == 9" count and
`getmembers(actions)` rely on the name remaining visible in A; keep a real import in A and the test is unchanged.
It also would pick up `EducatorReasonMixin` re-found via the import, which is excluded explicitly. Verify, or repoint
to `common.actions`.

### `common/bulk_actions.py`
| Name | Current |
|---|---|
| `EducatorBulkAction(PermittedBulkAction[User])` | A:2829-2863 (idea: slimmed half). Overrides `has_permission` (L2837), `scope_for_request` (2841), `objects_for_keys` (2844), `on_finished` (2851), `on_result_shown` (2860) |
| `CoursePickerMixin(RecordedBulkAction)` | A:3084-3111 |
Subclasses: `LearnerBulkAction` A:2866, `CohortBulkAction` A:3260 (extend `EducatorBulkAction`);
`CourseRegistrationBulkAction` A:3114, `CohortCourseBulkAction` A:3283 (use `CoursePickerMixin`). Eleven
`@register_bulk_action` classes at A:2959, 2980, 3031, 3059, 3136, 3158, 3194, 3327, 3349, 3402, 3432 (none move here).
Deps: `PermittedBulkAction`, `RecordedBulkAction` (`panel_framework.bulk_actions`), `run_summary`
(`panel_framework.bulk_runs`), `BulkActionRun`, `raise_notification`/`mark_notifications_read`
(`comms.notify`), `can_on_any`, `registerable_courses`, `CoursePickerForm` and `course_target` (flat
`forms.py`, leaf), `Course`, `Organisation`, `get_object_or_404`, `OrganisationScopedRequest` (from `common.request`),
`User`, `QueryDict`. None of this imports a flat module that stays.
The class-name strings in migration `migrations/0001_rename_unregister_bulk_runs.py:5` and
`tests/migrations/test_0001_rename_unregister_bulk_runs.py:15` use the prefix `freedom_ls.educator_interface.actions.`
for stored `action_path` of the registered concrete classes: unaffected (they do not move).

### `common/report.py`
| Name | Current |
|---|---|
| `PROGRESS_STATUS_TONES` (not in idea; `progress_status_badge` needs it; imported by `tests/test_reporting.py:28`) | R:80-84 |
| `progress_status_badge` | R:87-90 |
| `flag_badge` | R:93-96 |
| `report_over_limit_message` | R:99-110 |
Idea range 74-130 is now 80-110. `LazyBodyPanel`/`render_region`: in panel_framework (see 0.5), not here.
Deps: `StatusBadge`, `ProgressStatus`, `progress_status` (`reports.statuses`), `AtRiskFlag`
(`reports.report_data`), `reports_config` (`reports.config`), `over_limit_message` (`reports.services`),
`cohort_learner_count` (`learner_management.queries`), `Cohort`. All leaf.
`report_over_limit_message` users: R:136, R:193 (cohort report code). `REPORT_POLL_SECONDS` (R:77),
`DOWNLOAD_COHORT_REPORT` (R:78) are not moved. `DOWNLOAD_COHORT_REPORT` is imported by V:156.
Templates call the badges only through `templatetags/educator_tags.py` (tags `progress_status_badge`,
`flag_badge`): `templates/educator_interface/panels/cohort_report_body_region.html:78`,
`templates/educator_interface/partials/learner_badges.html:8,12`. Not touched.

## 2. Cycles: do `common/*` modules need anything staying in the flat modules?

No. Every dependency listed above resolves to a leaf (panel_framework, learner_management, reports, comms,
accounts, content_engine, organisations, or the flat `forms.py`, which imports nothing from educator_interface
views/actions/filters/reporting). Concretely:
- `common/request.py`: none.
- `common/tables.py`: only `common/badges.py`.
- `common/badges.py`, `common/ids.py`, `common/report.py`: none.
- `common/filters.py`: `common/request.py` (for cast type only).
- `common/actions.py`: flat `forms.py` only.
- `common/bulk_actions.py`: flat `forms.py` + `common/request.py`.
Direction after the move is one-way: flat modules and future area packages import `common`; `common` imports
no flat module. Flat-module cross edges that remain (not created by this move): `reporting.py` imports
`actions.py` (R:19 `RegisterLearnerForCourseAction`) and `quick_views.py` (R:25); `views.py` imports all four;
`actions.py` imports `filters.may_see_staff_roles` (A:50); `actions.py:1611` lazy-imports `views.interface_config`.
Existing private-name hazard: nothing outside the module that defines it uses a `_`-prefixed moved name
(`_interface_link`, `_learner_column`, `_registration_columns`, `_uuid_from`, `_action_params`, `_empty_message`,
`_picker_title`): grep shows no importer outside `views.py`/`actions.py`. The spec must decide whether to keep
the leading underscore on a cross-module name (the idea keeps them: it lists them as `_interface_link` etc.).

## 3. The four `TYPE_CHECKING` imports of `OrganisationScopedRequest`

| File | Block | Use |
|---|---|---|
| `actions.py` | A:196-197 (`from freedom_ls.educator_interface.views import OrganisationScopedRequest`) | ~25 string casts `cast("OrganisationScopedRequest", ...)` at A:204, 224, 867, 964, 982, 1018, 1033, 1334, 1340, 1396, 1399, 1454, 1511, 1517, 1539, 1581, 1629, 2838, 2842, 2908, 3093 (and others) |
| `filters.py` | F:38-39 | casts at F:47, 55, 101, 138, 159, 184, 208 |
| `quick_views.py` | L39-41 (`User` also under TYPE_CHECKING at L40; keep that) | annotation L45, casts L89, 118, 142, 170 |
| `reporting.py` | R:73-74 | annotation R:354, casts R:171, 495, 499, 536 |
Also `tests/test_actions.py:60` imports it from views at runtime and uses it at :6519 (`_scoped_request`).
`templatetags/educator_tags.py:11-15` imports it from views at runtime (with `LearnerCourseSummary`,
`learner_course_summaries`); only the `OrganisationScopedRequest` name is repointed, the other two stay on views.
Safe to make real imports: `common/request.py` imports no flat module, so `actions.py`, `filters.py`,
`quick_views.py` and `reporting.py` importing `panels.common.request` cannot cycle. With real imports the
`cast("OrganisationScopedRequest", ...)` string forms still work (a quoted name resolves at runtime to the module
global; `from __future__ import annotations` is on in all four); the spec may leave the strings or unquote them.
If left quoted, ruff/pyright still resolves them. Removing `TYPE_CHECKING` from `filters.py` leaves `cast` import
in use; `typing.TYPE_CHECKING` itself stays needed in `quick_views.py` (for `User`) and drops from the other three
unless used elsewhere (actions.py and reporting.py: check no other `TYPE_CHECKING` use; grep shows only the one
block each).
V:263 docstring wording ("imports it only under TYPE_CHECKING to avoid a runtime import cycle") becomes untrue;
update it in the moved docstring (comment text only).

## 4. Every importer / patch string naming a moved symbol (file:line)

### Production
- `views.py`: imports `VisibleCourseFilter` V:125 (from `filters`); defines/uses everything in section 1 (use lines above).
  Imports from `actions` V:78-110 include no moved name; V:213 imports `BulkAction, bulk_actions_for_table` (not moved).
- `actions.py`: A:50 `may_see_staff_roles` (F, stays); uses `EducatorReasonMixin`, `_uuid_from`, `_action_params`,
  `_empty_message`, `_picker_title`, `_register_title`, `EducatorBulkAction`, `CoursePickerMixin` (lines in section 1).
- `filters.py`: `LearnerCourseFilter(VisibleCourseFilter)` F:123.
- `quick_views.py`: L65 (`learner_status_badge`, stays lazy), L72 (`active_status_badge`, repoint to `common.badges`, can
  become a top-level import, and the `_active_status_badge` wrapper can go).
- `reporting.py`: defines the three; uses `report_over_limit_message` at R:136, 193.
- `templatetags/educator_tags.py`: L10 `from ...reporting import flag_badge, progress_status_badge`; L11-15 views import
  (`OrganisationScopedRequest`); uses at L26, L32, L53, L61.
- `tests/interface_walk.py`: L20 `from freedom_ls.educator_interface.actions import EducatorBulkAction` (also L21
  `interface_config` from views); uses L60, L163.
### Tests
- `tests/test_denied_experience.py:19` `OrganisationSectionConfig` (views); uses :153, 174, 196.
- `tests/invariants/test_config_authorisation.py:31-34` `OrganisationSectionConfig` (views); used :180.
- `tests/invariants/test_reason_mixin.py:13,23` `actions.EducatorReasonMixin`.
- `tests/test_interface_urls.py:19-22` `LAST_ORGANISATION_SESSION_KEY` (views); used :42, 172, 188.
- `tests/test_filters.py:19-27` `VisibleCourseFilter` (filters); used :77, 90, 102, 144, 759, 793.
- `tests/test_reporting.py:27-32` `PROGRESS_STATUS_TONES, flag_badge, over_limit_message, progress_status_badge`
  (reporting); used :606, 613, 625. `over_limit_message` is only imported via `reporting` from `reports.services`
  (test L184 tests that reports function, not `report_over_limit_message`): after the move this import must come from
  `freedom_ls.reports.services` (or the test relocates).
- `tests/test_views.py:84-89` `active_status_badge` (views), used :7564.
- `tests/test_actions.py:60` `OrganisationScopedRequest` (views), used :6519; :94-95 `BULK_ACTIONS` is from
  `panel_framework.bulk_actions` (not moved).
- Other apps / qa_helpers / docs / claude_plugins: no reference to any moved symbol. `qa_helpers` imports only
  `CourseCohortRegistrationDataTable`/`CourseLearnerRegistrationDataTable` from views (area classes, not moved:
  `qa_create_course_cohort_registrations.py:50`, `qa_create_direct_course_registrations.py:42`).
  `claude_plugins/fls-dev/resources/testing.md:26` names `views.learner_import` (not moved). The fls-dev skills
  (`educator-interface/SKILL.md:41`, `panel-framework/SKILL.md:254`) mention `filters.py` / `views.py` generically;
  those are spec 7's.
### `mock.patch` / `monkeypatch` strings
No patch string anywhere targets a moved symbol. Patch strings in educator_interface tests name only staying
names: `educator_interface.actions.{move_between_cohorts, assign_role, grantable_roles, grantable_roles_for,
current_role_entries, cohorts_visible_to, deactivate_role, record_learner_entry}` (`tests/test_actions.py`
2621, 3544, 3747, 3865, 3885, 3911, 3942, 3960, 4108, 4150, 4293, 4513, 4550, 4820, 4905, 4965, 5127, 5215,
6292, 9496, 9660, 9718, 9852; `tests/test_views.py:3754, 3785`) and `educator_interface.views.{own_conversation_with,
send_message, MAX_UPLOAD_BYTES}` (`tests/test_views.py:5000, 5054, 5076, 5080, 5773`). Also
`monkeypatch.setattr("freedom_ls.panel_framework.bulk_runs.run_apply", ...)` (`tests/test_actions.py:8456`).
Careful: `grantable_roles`/`cohorts_visible_to` are looked up in `actions.py`'s own namespace; the moved
`common/bulk_actions.py` and `common/actions.py` use `can_on_any`, `registerable_courses` (not patched), so no
string needs repointing. Spec should still re-grep after the move.

## 5. Test slices (current names and line ranges)

### `tests/test_denied_experience.py` (whole file -> `tests/panels/common/test_request.py`)
Module docstring L1-7, `_cohorts_list_html` L36, `_interface_url` L46; 15 tests L55-L360 ... file ends after
`test_a_member_who_lost_every_role_gets_404_...` (L360). Only three tests call `OrganisationSectionConfig`
directly: `test_denied_context_names_organisation_admins_for_a_viewer_of_staffmember` (L138),
`..._for_a_holder_of_view_organisation_staff` (L162), `test_denied_context_omits_names_for_an_asker_who_may_not_view_staffmember`
(L183). The rest are HTTP end-to-end denial tests over cohorts/staff (cohort/staff area behaviour), which the
idea moves whole anyway. Recommend the spec records this as a deliberate whole-file move (the mirroring rule is
satisfied by the filename, the content is wider than `request.py`).
Also: `tests/test_interface_urls.py` holds `LAST_ORGANISATION_SESSION_KEY` tests (`interface` view tests); it mirrors
`urls.py`/`interface` and stays.

### `tests/test_filters.py` -> `tests/panels/common/test_filters.py` (`VisibleCourseFilter` only)
- L68-81 `test_visible_course_filter_offers_only_courses_visible_to_the_educator`
- L84-94 `test_visible_course_filter_keeps_a_cohort_with_an_active_registration`
- L97-106 `test_visible_course_filter_drops_a_cohort_whose_registration_is_inactive`
- L750-763 `test_visible_course_filter_offers_a_course_only_when_it_reaches_the_organisation` (parametrised over
  `COURSE_REACH_ROWS` L741-747, which is shared with the staying `test_learner_course_filter_offers_a_course_only_when...`
  at L766-777: the constant must be duplicated or moved to `tests/helpers.py`, which already has `course_per_reach_row`)
- L780-800 `test_course_filter_names_the_owner_of_a_course_another_organisation_owns`
- Shared helpers the slice needs: `_site_context` autouse fixture (L48-50), `_educator_request` (L53-60),
  `_any_request` (L63-65). These are also used by staying tests, so the new file needs its own copies (or they move to
  a shared helper; the conftest/test-helper rule in `django-stack/resources/testing.md`: helper used by two test modules
  goes in `tests/helpers.py`/conftest).
- NOT slices: L109-202 and L705-720 test `CohortDataTable` toggle (cohort); L144 uses `VisibleCourseFilter` only as a
  stand-in inside a `CohortDataTable` test (stays with the cohort test).
- No `ShowInactiveFilter` tests exist (class is gone).

### `tests/test_actions.py` (9,9xx lines) -> `tests/panels/common/test_actions.py`
No test calls `_uuid_from`, `_action_params`, `_empty_message`, `_picker_title` or `_register_title` directly (grep of the
test file: no match). They are covered only through HTTP. Candidate common-action slices (all behaviour-level):
- `test_a_reason_posted_to_a_dialog_without_a_reason_field_is_ignored` L489 and the "optional reason in the confirm
  dialogs" section L6374-6507 (`_DialogRequest` helpers L6380-6445 `_reason_post` L6434; tests L6449, 6467, 6482, 6495):
  these exercise `EducatorReasonMixin` across nine concrete actions.
- "empty pickers" section L3135-3322 (`_empty_picker_text` L3138; tests L3153-3296 `test_an_empty_learner_picker_...`,
  `..._add_to_cohort_picker_...`, `..._register_picker_...`, `..._move_picker_...`, `test_a_picker_with_something_to_offer_keeps_its_submit_button` L3296): exercise `_empty_message`.
- "stale picker" tests L6573-6670 (`test_a_stale_cohort_in_a_bulk_picker_...` etc.).
- Picker helpers `_picker_dialog` L153, `_dialog_title` L159, `_picker_options` L7100, `_offered_options` L1574 are shared by many
  staying tests.
Verdict: there is no cleanly separable helper test slice; every candidate depends on `_interface_url`/`_post`/fixtures shared
with the whole file. The spec must decide the cut (or the idea's default "move only where a dedicated slice exists" yields
a thin or empty `test_actions.py`). `tests/invariants/test_reason_mixin.py` is an invariants test (exempt from mirroring)
and stays.

### `tests/test_actions.py` -> `tests/panels/common/test_bulk_actions.py` (educator bulk base)
Idea says "about 8055-8530 on main". Current: the "recorded runs: the organisation scope and the finished notification"
section L8355-8511 is the `EducatorBulkAction` base slice (`GONE`, `DEACTIVATE`, `_learner`, `_run_over`, `_notifications_for`,
`_run_in_background` helpers L8357-8432; tests `test_a_learner_of_another_organisation_is_not_touched` L8383,
`test_a_requester_who_lost_the_grant_skips_every_object_and_the_run_is_done` L8395, `test_the_task_tells_the_requester_the_run_finished`
L8436, `..._where_a_failed_run_stopped` L8450, `test_an_inline_run_raises_no_notification` L8471, `test_an_unfinished_run_is_not_notified`
L8483, `test_the_summary_counts_in_the_actions_own_noun` L8495). Plus `test_a_bulk_action_on_rows_that_left_the_scope_answers_the_unavailable_dialog`
L8520-8537 (scope narrowing, `objects_for_keys`). They use `DeactivateLearnersBulkAction` (an area class) as the concrete action, so the
new file imports an area class from the flat `actions.py` (acceptable: common tests import the flat module; no cycle).
Not part of the base slice: retired-slug tests L8545-8574 (`views` dispatch), `_BULK_ACTION_WEIGHTS` + weight/title tests L8577+
(use `BULK_ACTIONS` registry; framework/area). `CoursePickerMixin` tests: `test_the_register_picker_offers_only_registerable_courses` L7628,
`test_a_bulk_register_picker_resolves_a_course_only_when_it_is_registerable` L9938, `test_a_stale_course_in_a_bulk_picker_answers_422_without_the_id`
L6596, `test_the_cohort_register_picker_offers_only_registerable_courses` L8108: candidates for the `CoursePickerMixin` slice, each
tied to an area (learner/cohort) so they probably stay.
Imports the slice needs from the old file header: `BulkCount`, `NOT_FOUND`, `report_finished`, `run_bulk_action`, `run_summary`,
`BulkActionRun`, `RunStatus`, `BulkResult`, `Notification` (see L94-108). After the cut, the old header must drop any import it no
longer uses (ruff).

### `tests/test_reporting.py` -> `tests/panels/common/test_report.py`
- `TestProgressBadges` L603-628: `test_the_three_statuses_map_to_muted_info_and_success` (L605, `PROGRESS_STATUS_TONES`),
  `test_a_completion_percentage_becomes_its_status_badge` (L612), `test_a_flag_badge_is_toned_by_the_flags_severity` (L617).
  Note `@pytest.mark.django_db` on the class (L603) is not needed for these.
- `report_over_limit_message` has no direct test; it is covered through `TestReportTab` L435-517 (cohort report: over-limit
  tests at L435, 457, 476, 499) which stays (cohort). `test_the_over_limit_message_names_the_cohort_its_size_and_the_limit` L184
  tests `reports.services.over_limit_message`, not the moved function.

### tables, badges, ids
- badges: `tests/test_views.py:7557-7566` `test_active_status_badge_has_one_label_and_tone_per_state` is a dedicated slice for
  `active_status_badge` (parametrised, L7557-7566). Its sibling `test_learner_status_badge_has_one_label_and_tone_per_state` (L7549)
  is learner code and stays. `inactive_badge` is covered only via views HTTP tests. So `tests/panels/common/test_badges.py`
  would hold this one test (plus its `active_status_badge` import).
- tables: no dedicated slice (no test names `_interface_link`, `_learner_column`, `_registration_columns`).
- ids: no dedicated slice (`uuid_or_404` has no direct test).
Default per the idea: no test file for tables or ids; badges gets one only if the spec accepts the one-test file.

### `tests/panels/` directory facts
`tests/panels/__init__.py` and `tests/panels/common/__init__.py` are new (neither exists yet). `tests/helpers.py`,
`tests/conftest.py` exist at the tests root (a conftest in `tests/` applies to the subdirectory). Playwright tests are skipped by the
mirroring check (`check_test_mirroring.py:96`); `tests/invariants/` is exempt (`mirroring_exemptions.txt:18`).

## 6. Mirroring baseline and enforcement

`test_organisation/mirroring_baseline.txt` (educator_interface section, lines 36-46; "# educator_interface" header at 36 per the idea):
```
37 freedom_ls/educator_interface/tests/test_cohort_delete_action.py
38 .../test_course_visibility_and_interest.py
39 .../test_create_cohort_action.py
40 .../test_dashboard.py
41 .../test_denied_experience.py        <-- the line the spec deletes
42 .../test_document_title.py
43 .../test_interface_urls.py
44 .../test_learner_section.py
45 .../test_organisation_switcher.py
46 .../test_sidebar.py
```
(Line 41 confirmed to be `test_denied_experience.py`; the other nine stay. After deletion the educator_interface block has nine lines.)
Mechanism: `[tool.test_organisation]` in `pyproject.toml:108` (`mirroring_baseline = "test_organisation/mirroring_baseline.txt"`) feeds
`claude_plugins/django-stack/scripts/check_test_mirroring.py`, run by the `test-mirroring` pre-commit/CI hook (see
`claude_plugins/fls-dev/skills/testing/SKILL.md:43`). Rules (`check_test_mirroring.py:78-111`): a collected file
`<app>/tests/<sub>/test_<name>.py` conforms iff `<app>/<sub>/<name>.py` exists or `<app>/<sub>/<name>/__init__.py` exists. So
`tests/panels/common/test_request.py` conforms only once `panels/common/request.py` exists (create the package modules in the same
commit or earlier). `test_filters.py`, `test_actions.py`, `test_bulk_actions.py`, `test_report.py` likewise need `common/filters.py`,
`common/actions.py`, `common/bulk_actions.py`, `common/report.py`. A `test_badges.py` would need `common/badges.py` (exists once created).
Failure modes (`check_test_mirroring.py:181,197`): a baseline line that no longer matches a violation is an error, so the
`test_denied_experience.py` line must be deleted in the same commit that moves the file; a path in both baseline and exemptions is an error.
The doc is `claude_plugins/django-stack/resources/testing.md` section "Mirroring" (lines 23-33). `test_organisation/import_baseline.txt`
and `import_contracts.toml` (educator_interface contract at :189-197) only list `test_course_visibility_and_interest -> course_interest.factories`;
no entry mentions a moved path. `docs/app_structure.md` is generated by `/ds:app_map` (hook `app-map-fresh`); the new `panels/`
package may need a regeneration if it lists modules (check; the file is not read here). `tests/test_check_test_mirroring.py` and
`tests/test_generate_app_map.py` (repo-root `tests/`) test the script generically and do not name FLS paths.

## 7. In-progress specs touching these files

`spec_dd/2. in progress/`: `extract_panels_framework-4-template-contract`, `learner-profile-use-panels-framework-2-editable-list-panel`,
`misure-of-admonitions`, `sacaa-compliance-1-served-paper-record`, `spec_dd_efficiency_and_docs`.
Only `extract_panels_framework-4-template-contract` names educator_interface, and only to say `educator_interface` behaviour and
templates "do not change" and that the interface's own tests are the check (`idea.md:76, 85`). It is a template/cotton spec, so it does
not touch `views.py`, `actions.py`, `filters.py`, `reporting.py` or the tests above: no file conflict. The other three do not mention
educator_interface. (Not read in full; grep only. If `learner-profile-use-panels-framework-2-editable-list-panel` edits `educator_interface`
code that mention would show; it did not.)
Sibling ideas in `spec_dd/1. next/` that this spec's output feeds and whose text has gone stale: spec 2 (dashboard) line 26 and spec 6 (cohort)
line 32 say `LazyBodyPanel`/`render_region` come from `panels/common/report.py`; spec 3 (staff) line 27 lists `_uuid_param` and
`ShowInactiveFilter` as already in `common`; spec 5 line 56 / spec 6 line 35 expect "the bulk framework" in `common/bulk_actions.py`.
All four need a note after this spec lands (the registry is framework; only `EducatorBulkAction` and `CoursePickerMixin` are in common).

## 8. The `# TODO` block and the lazy `interface_config` import

- `views.py:334-342` is the `# TODO` block (the idea says 330-339):
  ```
  # TODO
  # Data Tables
  # top level filters (searchable dropdown)
  #   use HTMX to only reload that one panel
  # Bulk delete
  # Export as csv
  #
  # instance edit
  # instance, other actions (eg: send_email)
  ```
  It sits between `OrganisationSectionConfig` (ends V:331) and `_interface_link` (V:345). When both neighbours move out, it stays
  as the first thing after the imports/constants in `views.py`. It must not be deleted (project rule). It is a plain comment block,
  not tied to the moved code.
- Lazy import: `actions.py:1611` `from freedom_ls.educator_interface.views import interface_config` (with a second lazy import
  `from freedom_ls.panel_framework.views import first_visible_section` at A:1612), inside `staff_member_changed_response` (A:1605-1634).
  Idea says "near line 1770"; now 1611. It stays lazy and is untouched (staff code, spec 3). Moving `OrganisationScopedRequest` to
  common does not change it (A:1629 is a string cast in the same function, which will resolve to the new real import).

## 9. Risks / spec decisions the research surfaces

1. `common/tables.py` must also take `_active_status_column` (section 0.7).
2. `PROGRESS_STATUS_TONES` is a fourth name in `common/report.py` and is imported by a test.
3. `tests/test_reporting.py:30` imports `over_limit_message` through `reporting` (re-export by accident); repoint to `reports.services`
   when `reporting.py`'s import list changes (only if `reporting.py` stops importing it; it still uses it? check: R uses
   `over_limit_message` only inside `report_over_limit_message` (R:110), which moves, so the import leaves `reporting.py` and the
   test import would break).
   Verify with grep when implementing: `reporting.py` import block R:65-70 lists `over_limit_message` among the `reports.services` names.
4. `tests/invariants/test_reason_mixin.py` depends on `actions.EducatorReasonMixin` (section 1).
5. `COURSE_REACH_ROWS` and the three helpers in `test_filters.py` are shared between moving and staying tests (section 5).
6. Moved private names keep their underscores per the idea; cross-module use of `_`-names triggers ruff `PLC2701` only if that rule is
   enabled (not checked).
7. After the move `views.py` still imports `VisibleCourseFilter` (now from `panels.common.filters`), `bulk_actions_for_table`, etc.; drop
   unused imports (`attrgetter`, `replace`, `Literal` if no other use, `Http404`, `UUID` check) in each shrunk module.

status: ok
