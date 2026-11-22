# Research: codebase impact of moving the learner area into `panels/learner/`

Checked against the tree on branch `educator-interface-refactor-5-learner` (specs 1 and 2 landed; 3 and 4 not).
Paths are under `freedom_ls/educator_interface/` unless they start with `freedom_ls/`, `test_organisation/` or `claude_plugins/`.
Line numbers are today's; re-find each name by grep before cutting it.

Current sizes: `views.py` 3040+ lines, `actions.py` about 3320, `reporting.py` 294, `filters.py`, `quick_views.py` 172. `tests/test_views.py` about 8700 lines (the idea's ranges predate a lot of growth), `tests/test_actions.py` about 9750.

## 0. Headlines (things the idea gets wrong or misses)

1. **Learner actions DO call the cohort-owned `inactive_cohort_response`** (see 2a). Place it in `panels/common/actions.py`. `cohort_not_empty_sentence` is cohort-only.
2. **`visible_registrations_with_progress` is NOT used by the cohort quick view.** Its users are `LearnerQuickView` and `LearnerCoursesPanel` (`reporting.py:277`). Nothing else, staff included. It stays in the learner area (`quick_view.py`). The idea's "the cohort quick view imports it from there" is false.
3. **Intra-learner import cycle on `learner_status_badge`.** The idea puts it (with `_LEARNER_STATUS_TONES`) in `instance_view.py`. But `data_tables.py` (`LearnerDataTable` uses it at views.py:514) and `panels.py` (`LearnerDetailsPanel`, views.py:606) both need it, while `instance_view.py` imports `panels.py` and `data_table_panels.py`, which import `data_tables.py`. That is `data_tables -> instance_view -> data_table_panels -> data_tables` and `panels -> instance_view -> panels`. It must live in a leaf. Options: `panels/common/badges.py` (already holds `active_status_badge`; recommended) or the bottom of `panels/learner/data_tables.py`. It also removes the lazy-import wrapper `_learner_status_badge` in `quick_views.py:65-70`.
4. **`partial_oversight_thread_older` cannot sit in `messages.py` as a plain top-level import.** It needs `_attach_organisation` (shell, views.py:2406) and `LearnerConfig` (views.py:2454). `config.py -> instance_view.py -> messages.py -> config.py` is a cycle, and `messages.py -> shell views.py -> every config` is another. Put it in `import_views.py` (the one learner module no config imports, which already imports the shell) or in a separate plain-view module, or lazy-import inside the function. `urls.py` only needs it as a dotted attribute.
5. **`import_views.py` also needs `scope_request`** from the shell (views.py:2474), not only `standalone_page_context` (2504). And `_attach_organisation` for the oversight view.
6. **There are 6 learner import plain views, not 8**: `learner_import`, `learner_import_preview`, `learner_import_template`, `learner_import_errors`, `learner_import_result`, `partial_learner_import_status` (the six `urls.py` entries). Plus `partial_oversight_thread_older` = 7 plain views to repoint in `urls.py`.
7. **`templatetags/educator_tags.py` does not use `learner_status_badge`.** It imports only `LearnerCourseSummary`, `learner_course_summaries` (educator_tags.py:21-24).
8. **`AddExistingLearnersAction` (actions.py:1265-1315) sits inside the idea's "shared membership block" range but is cohort-owned** (`RequiresActiveCohortMixin`). Same for `AddLearnerToCohortAction` (1478-1489). They stay for spec 6. `_picker_cohorts` (955-968) is a helper the idea does not list; it goes with `_cohort_picker`.
9. **`test_0001_rename_unregister_bulk_runs.py` will break when a new migration exists**: it migrates to `leaf` (the newest node), so its `untouched` row `actions.DeactivateLearnersBulkAction` and the renamed `actions.DeactivateRegistrationBulkAction` row would be rewritten by the new migration and the asserted paths no longer match. The test must migrate to `("freedom_ls_educator_interface", "0001_rename_unregister_bulk_runs")` instead of `leaf` (edit the test, never the migration). See 2c.
10. **`_course_title_column` / `_cohort_links_column`** (views.py:268-292) are used by `LearnerDataTable` (views.py:516) and `CohortCourseRegistrationDataTable` (1157), `CourseDataTable` (1655, 1678). Spec 4 (in progress, `educator-interface-refactor-4-course`) moves both to `panels/common/tables.py` in its slice 1 and repoints `LearnerDataTable` itself. Spec 5 depends on whichever lands first; if spec 5 lands first, it must do that move. `learner/data_tables.py` imports them from `common/tables.py`.
11. **`_NEW_REPORTING_FILES` guard** (`tests/test_reporting.py:1483-1494`) lists `"reporting.py"` and reads the source for the string `progress_percentage`. `LearnerCoursesPanel` leaves `reporting.py`, so add `"panels/learner/panels.py"` (spec 2 added `panels/dashboard/panels.py` the same way). Do NOT list `panels/learner/data_tables.py`: `LearnerCourseSummary.progress_percentage` is a legitimate name there.
12. **Shared test helpers imported across test modules.** `tests/invariants/test_course_shares.py:36-45` imports `_learner_reregister_url`, `_post` from `tests.test_actions` and `_content_action_url`, `_export_csv`, `_interface_url`, `_learner_page` from `tests.test_views`. `_learner_page` (test_views.py:1741) and `_learner_reregister_url` (test_actions.py:2970) move with learner tests, so they must go to `tests/helpers.py` (spec 2 slice 1 did exactly that for the audit helpers) or the invariant import breaks.
13. `claude_plugins/fls-dev/resources/testing.md:26` names `from freedom_ls.educator_interface.views import learner_import` as an example. Becomes stale. Docs sweep is spec 7's, but the example is a dotted path.

## 1. Re-checked line ranges (today's tree)

### views.py (V)

| Idea's module | Symbol | Today V: lines | Note |
|---|---|---|---|
| `config.py` | `LearnerConfig` | 1534-1565 | `quick_view = LearnerQuickView` (1543), `list_view = LearnerDataTable` (1539), `instance_view = LearnerInstanceView`, `get_actions` returns `[AddLearnerAction(), ImportLearnersAction()]` (1547) |
| `data_tables.py` | `LearnerCourseSummary` (dataclass) | 425-431 | |
| | `learner_course_summaries` | 434-459 | |
| | `LearnerDataTable` | 462-567 | uses `LearnerStatusFilter/CohortFilter/CourseFilter` (537-539), `learner_status_badge` (514), `_cohort_links_column` (516) |
| | `_last_active_cell` | 570-575 | |
| | `CohortLearnerDataTable(LearnerDataTable)` | 578-594 | used by cohort `CohortLearnersPanel` (V:1171, spec 6) |
| `cohort/data_tables.py` | `CohortDataTable` | 295-386 | needs `_active_status_column`, `_interface_link`, `VisibleCourseFilter`, `OrganisationScopedRequest` (all common) |
| | `LearnerCohortDataTable(CohortDataTable)` | 389-422 | column template `membership_actions.html` |
| `data_table_panels.py` | `LearnerCohortsPanel` | 611-651 | needs `LearnerCohortDataTable`, `AddToCohortAction`, `RemoveFromCohortAction`, `MoveToCohortAction` |
| | `RegistrationRow` (dataclass) | 654-681 | |
| | `LearnerRegistrationsPanel` | 684-744 | needs `DeactivateRegistrationAction`, `ReactivateRegistrationAction` |
| | `LearnerHistoryPanel(HistoryPanel)` | 765-783 | `HistoryPanel` from `panels.audit_log.data_table_panels` (already imported at V:141-143) |
| `panels.py` | `LearnerDetailsPanel` | 597-608 | uses `learner_status_badge` |
| | `LearnerNamePanel` | 999-1018 | `EditLearnerNameAction` |
| | `LearnerAccountPanel` | 1021-1042 | `ResendSetupEmailAction`, `learner_state_actions` |
| | `LearnerCoursesPanel` | **reporting.py 255-294** (R), to end of file | `RegisterLearnerForCourseAction` (R:16 import), `visible_registrations_with_progress` (R:29, 277), `gather_learner_course_details`. Template `educator_interface/panels/learner_courses.html` |
| `messages.py` | `LearnerMessagesPanel` | 786-842 | |
| | `LearnerOtherConversationsPanel` | 845-871 | |
| | `LearnerMessagesStack` | 874-883 | |
| | `SendToLearnerAction` | 886-930 | `send_message`, `own_conversation_with` looked up in this module (patch target) |
| | `ViewConversationAction` | 933-987 | |
| | `_oversight_role_label` | 990-996 | idea missed it; used only by `ViewConversationAction` (982) |
| | `partial_oversight_thread_older` | 2443-2471 (decorator at 2443) | see headline 4; urls name `oversight_thread_older` |
| `instance_view.py` | `LearnerOverviewStack` | 747-756 | children: details, cohorts, registrations |
| | `LearnerCoursesStack` | 759-762 | |
| | `LearnerSettingsStack` | 1045-1052 | |
| | `settings_actions` | 1055-1062 | |
| | `learner_actions` | 1065-1073 | |
| | `LearnerTabSet` | 1076-1084 | |
| | `LearnerInstanceView` | 1087-1107 | |
| | `_LEARNER_STATUS_TONES`, `learner_status_badge` | 1110-1120 | move to a leaf (headline 3) |
| `import_views.py` | `_see_other` 2537, `_learners_url` 2542, `_import_url` 2549, `FormatRow` 2559, `_format_rows` 2566, `_import_page` 2585, `_import_denied` 2599, `IMPORT_PREVIEW_PAGE_SIZE`/`IMPORT_RESULT_ERROR_ROWS` 2615-2616, `_label_counts` 2619, `_count_of` 2637, `_requested_import_or_404` 2641, `_cohort_learners_url` 2657, `_cohort_import_url` 2667, `_import_upload_url` 2677, `_import_cohort_or_404` 2684 | 2537-2701 | |
| | `learner_import` 2704, `learner_import_preview` 2748, `_csv_attachment` 2826, `learner_import_template` 2832, `learner_import_errors` 2847, `_capped_error_rows` 2881, `_import_status_context` 2889, `learner_import_result` 2933, `partial_learner_import_status` 2955 | 2704-2973 | `interface` view starts 2976 (shell). `_import_denied` uses `LearnerConfig.get_denied_context` (2608) so `import_views` imports `config.py`. Uses `_run_learner_import_task` from `tasks.py`, `learner_management_config`, `panel_framework_config`, `LearnerImportForm`, `entry_count_text`, `login_required_htmx_to` |

Shell, staying in `views.py` (not moved by this spec): `interface_config` 2357, `interface_root` 2367, `_resolve_organisation` 2394, `_attach_organisation` 2406, `_scoped_cohort` 2420, `cohort_report_download` 2429, `scope_request` 2474, `standalone_page_context` 2504, `interface` 2976. Neighbouring cohort/course/staff blocks are interleaved: cohort 1123-1530 (incl. `CohortHistoryPanel` 1418), `CohortConfig` 1504, course 1568-2200, staff 2205-2355.

The import block V:72-176 will lose: `AddLearnerAction`, `AddToCohortAction`, `ImportLearnersAction`, `MoveToCohortAction`, `RemoveFromCohortAction`, `EditLearnerNameAction`, `DeactivateRegistrationAction`, `ReactivateRegistrationAction`, `RegisterLearnerForCourseAction`, `ResendSetupEmailAction`, `learner_state_actions` (actions); the three `Learner*Filter` (112-118, keep `StaffRoleFilter`, `may_see_staff_roles`); `LearnerQuickView` (keep `CohortQuickView`, `StaffQuickView`); `LearnerCoursesPanel` (reporting; keep `DOWNLOAD_COHORT_REPORT`, `CohortNeedsAttentionPanel`, `CohortReportStack`). `cohort_not_empty_sentence` (V:99, used V:1391) stays. A large part of the 3rd-party import block (comms messaging, learner_import, csv) becomes unused in V.

### actions.py (A)

| Name | Today A: lines | Owner |
|---|---|---|
| `EditLearnerNameAction` | 401-445 | learner |
| `LearnerStateAction` 599, `DeactivateLearnerAction` 636, `ReactivateLearnerAction` 647, `learner_state_actions` 658 | 599-661 | learner |
| `record_and_resend_setup_email` 663, `ResendSetupEmailAction` 674 | 663-715 | learner (helper also used by `ResendSetupEmailBulkAction`, A:3098) |
| `KEEPING_NAMES_SHOWN` 716, `DeactivateCohortRegistrationAction` 719-775 | 716-775 | **cohort** (stays) |
| `_registration_changed_response` 777, `RegisterLearnerForCourseAction` 782, `DeactivateRegistrationAction` 820, `ReactivateRegistrationAction` 880 | 777-931 | learner |
| `_membership_changed_response` 933-940, `_joinable_cohorts` 943-952, `_picker_cohorts` 955-967 (not in the idea), `_cohort_picker` 970-981, `MembershipAction` 984-1047, `RemoveFromCohortAction` 1049-1080, `MoveToCohortAction` 1082-1206 | 933-1206 | learner (shared membership block) |
| `AddToCohortAction` | 1209-1262 | learner (idea's list names it only in V imports) |
| `AddExistingLearnersAction` | 1265-1314 | **cohort** (stays); calls `_membership_changed_response` (1312), so cohort imports it from learner |
| `AddLearnerAction` | 1317-1439 | learner |
| `ImportLearnersAction` | 1442-1475 | learner |
| `AddLearnerToCohortAction` | 1478-1488 | **cohort** (stays), subclasses `AddLearnerAction` |
| `cohort_state_actions` | 1491 | cohort |
| `LearnerBulkAction` 2775, `CohortMembershipBulkAction` 2801, `AddToCohortBulkAction` 2869, `RemoveFromCohortBulkAction` 2890, `LearnerStateBulkAction` 2928, `DeactivateLearnersBulkAction` 2941, `ReactivateLearnersBulkAction` 2969, `CourseRegistrationBulkAction` 2993, `RegisterForCourseBulkAction` 3016, `DeactivateRegistrationBulkAction` 3038, `ResendSetupEmailBulkAction` 3074 | 2775-3136 | learner (`CohortBulkAction` starts 3139) |
| `CoursePickerMixin` | already `panels/common/bulk_actions.py:71` | imported at A:73 |

`EducatorBulkAction`, `CoursePickerMixin` (common/bulk_actions.py) and `EducatorReasonMixin`, `_action_params`, `_empty_message`, `_picker_title`, `_register_title`, `_uuid_from` (common/actions.py) are in common already.

### Other flat modules

| Module | Symbols | Today lines |
|---|---|---|
| `filters.py` | `LearnerStatusFilter` 38-59, `LearnerCohortFilter` 60-86, `LearnerCourseFilter(VisibleCourseFilter)` 87-96. Staff: `may_see_staff_roles` 97, `StaffRoleFilter` 110 (stay). | |
| `quick_views.py` | `visible_registrations_with_progress` 47-62, `_learner_status_badge` (lazy wrapper) 65-70, `LearnerQuickView` 73-129. `CohortQuickView` 132 and `StaffQuickView` 152 stay. | |
| `reporting.py` | `LearnerCoursesPanel` 255-294. Everything else is cohort/report. `reporting.py` imports `RegisterLearnerForCourseAction` (R:16) and `visible_registrations_with_progress` (R:29-31) only for this panel, so both imports go with it. `learner_avatars` (R:17) stays for cohort panels. | |

Learner symbols the idea missed: `_picker_cohorts`, `_oversight_role_label`, `_csv_attachment`, `_capped_error_rows`, `_import_status_context`, `_import_page`, `_import_denied`, `_see_other`, `LearnerOverviewStack`/`LearnerCoursesStack`/`LearnerSettingsStack` (the idea says "stacks", fine), `record_and_resend_setup_email`, `_registration_changed_response`, `AddToCohortAction`, `DeactivateLearnerAction`/`ReactivateLearnerAction`/`LearnerStateAction` (covered by "the learner actions" but unnamed), `LearnerStateAction`.

## 2. Answers to the open items

### (a) Cohort-owned helpers called from learner code

- `inactive_cohort_response` (actions.py:289-302). Defined in `actions.py`, depends only on `refusal_response` (panel_framework) and `Cohort`. Used by:
  - learner: `MembershipAction.handle_submit` (A:1043, covers `RemoveFromCohortAction`), `MoveToCohortAction.handle_submit` (A:1181), `AddToCohortAction.form_valid` (A:1259), `AddLearnerAction.form_valid` (A:1409);
  - cohort: `RequiresActiveCohortMixin.refuse_inactive` (A:349).
  Nothing else (also grep-clean in tests, templates, other apps).
  **Recommendation:** move it to `panels/common/actions.py` (imports there: forms, models, `panel_framework.actions`; add `refusal_response`, `PanelContext`, `Cohort`, `HttpResponse`). Then learner imports from common and cohort's `RequiresActiveCohortMixin` (which stays for spec 6) imports from common too. It is generic ("a change aimed at an inactive cohort") and leaves the learner/cohort edge one-way. Alternative with the same graph: leave it in learner `actions.py` and let cohort import it from there (cohort -> learner is the allowed direction), but a cohort-named helper in learner is a smell. Spec 3's research notes that lines 289-332 "are cohort code, so they stay" in `actions.py`; spec 5 therefore has to move only `inactive_cohort_response` (289-302) and leave `cohort_not_empty_sentence` (305-332) and `RequiresActiveCohortMixin` (335-363) for spec 6, which will then import the helper from common.
- `cohort_not_empty_sentence` (A:305-332): users are `DeleteEmptyCohortAction` (A:552, 542), `CohortStateAction` (A:459), views.py:1391 (`CohortStatusPanel`), and tests (`test_actions.py:48,519-559`, `test_cohort_delete_action.py:37,160...`). No learner use. Stays flat for spec 6.
- `RequiresActiveCohortMixin`: no learner class uses it (`AddLearnerToCohortAction` is cohort and stays). Not needed by learner.
- Other cohort-owned names learner code might touch: none. `KEEPING_NAMES_SHOWN` is only used by `DeactivateCohortRegistrationAction`. Learner bulk actions (2775-3136) use no cohort helper; only `cohorts_visible_to`, `can`, `Cohort` model.
- Reverse direction (cohort needs learner, expected, one-way): `AddLearnerAction`, `ImportLearnersAction`, `RemoveFromCohortAction`, `MoveToCohortAction`, `_membership_changed_response` (A:1312), `CohortLearnerDataTable`, `LearnerCohortDataTable`'s base. Cohort spec 6 imports from `panels/learner/`.

### (b) `visible_registrations_with_progress`

Used at `quick_views.py:95` (`LearnerQuickView`) and `reporting.py:277` (`LearnerCoursesPanel`), imported at `reporting.py:29-31`. Not used by `CohortQuickView`, `StaffQuickView` or anywhere in tests/other apps (grep over `freedom_ls/`). It stays with the learner area. `panels/common/` is not needed. In the target tree `panels/learner/panels.py` imports it from `panels/learner/quick_view.py`; no cycle (quick_view does not import panels).

### (c) `@register_bulk_action` learner classes and the migration

Exactly 7 (A:2868, 2889, 2940, 2968, 3015, 3037, 3073):
`AddToCohortBulkAction`, `RemoveFromCohortBulkAction`, `DeactivateLearnersBulkAction`, `ReactivateLearnersBulkAction`, `RegisterForCourseBulkAction`, `DeactivateRegistrationBulkAction`, `ResendSetupEmailBulkAction`.
Unregistered bases: `LearnerBulkAction`, `CohortMembershipBulkAction`, `LearnerStateBulkAction`, `CourseRegistrationBulkAction`. Cohort ones (spec 6, 4 registered): `RegisterCohortForCourseBulkAction` (A:3206), `DeactivateCohortRegistrationBulkAction` (3228), `DeactivateCohortsBulkAction` (3281), `ReactivateCohortsBulkAction` (3311). `BULK_ACTIONS[(table_key, action_name)]` is filled by `register_bulk_action` (`panel_framework/bulk_actions.py:557-564`); `action_path` is `f"{type(self).__module__}.{type(self).__qualname__}"` (bulk_actions.py:401); loaded by `import_string(run.action_path)` (`panel_framework/bulk_runs.py:35`).

Migrations: only `migrations/0001_rename_unregister_bulk_runs.py` exists, so the next is `0002_<name>.py`. App label `freedom_ls_educator_interface` (`apps.py:7`); the panel_framework app's migrations are `0001_initial`, `0002_bulk_action_run_site_has_no_reverse_accessor`. The pattern in 0001: module constant `_ACTIONS = "freedom_ls.educator_interface.actions."`, a `RENAMES` list of tuples, `rename_runs(apps, schema_editor)` using `apps.get_model("freedom_ls_panel_framework", "BulkActionRun")` and `.filter(action_path=old).update(...)`, `dependencies = [("freedom_ls_panel_framework", "0001_initial")]`, `operations = [migrations.RunPython(rename_runs, migrations.RunPython.noop)]` (reverse is a no-op there; the new one needs a real reverse). The new migration should depend on `("freedom_ls_educator_interface", "0001_rename_unregister_bulk_runs")` and keep `action_name` untouched. Note that 0001 maps old names to `actions.DeactivateRegistrationBulkAction`; after 0002 those stored rows end up at the new learner path in order (0001 then 0002).

Existing migration tests: `tests/migrations/__init__.py` and `tests/migrations/test_0001_rename_unregister_bulk_runs.py` only. Pattern: `@pytest.mark.django_db(transaction=True)`, `mock_site_context`, `MigrationExecutor(connection)`, `leaf = executor.loader.graph.leaf_nodes()`, `executor.migrate([(APP, None)])`, historical model from `executor.loader.project_state([(RUNS, "0001_initial")]).apps`, create runs with `site_id`, `requested_by_id`, `action_path`, `table_key="learners"`, `action_name`, `keys=[]`, then `executor.migrate(leaf)` and read back. Gotcha: `leaf` includes the new 0002, so this test must target `[(APP, "0001_rename_unregister_bulk_runs")]` rather than `leaf` or its `untouched` row (`actions.DeactivateLearnersBulkAction`) changes. The new `test_0002_*.py` should cover forward (all 7 rewritten, `action_name` kept), reverse (migrate back to 0001 restores `actions.<Name>`), and untouched (cohort bulk action paths `actions.DeactivateCohortsBulkAction`, an unknown path).

Spec 2 had no migration (`upgrade_notes.md`: `requires_migrations: false`); spec 3 is also "no migration" (no registered staff class). Spec 6 will add the next migration (0003). The dotted-path strings in tests that stay in step through `__module__` (`panels/common/test_bulk_actions.py:35-36`, `test_views.py:4976-4978`, `test_actions.py:7391`) follow the move automatically once the import is repointed. The literal paths in 0001/test_0001 stay as they are.

## 3. Import graph after the move

Direction rule (idea): `panels/common` <- `panels/cohort/data_tables.py` <- `panels/learner/*` <- (spec 6) `panels/cohort/*`. Nothing under `panels/learner/` may import `panels/cohort/` except `panels/cohort/data_tables.py`, which itself imports only `panels/common`.

Within `panels/learner/` (proposed one-way order; arrows mean "imports"):

```
filters.py            -> panels.common.{filters,request}
data_tables.py        -> filters, common.{tables,request}, [badge leaf], common/tables _cohort_links_column
actions.py            -> common.{actions,bulk_actions,request}, forms, learner_import.check_import_gate
bulk_actions.py       -> actions (record_and_resend_setup_email), common.bulk_actions
quick_view.py         -> [badge leaf], common.request, messaging
panels.py             -> actions, quick_view (visible_registrations_with_progress), [badge leaf]
data_table_panels.py  -> data_tables, cohort.data_tables, actions, audit_log.data_table_panels (HistoryPanel)
messages.py           -> messaging, comms (no config, no shell)
instance_view.py      -> panels, data_table_panels, messages, actions, [badge leaf]
config.py             -> data_tables, instance_view, quick_view, actions
import_views.py       -> config (LearnerConfig), shell views (scope_request, standalone_page_context), tasks, learner_import, forms
[oversight view]      -> config + shell _attach_organisation: so NOT in messages.py (headline 4)
```
Nothing in `panels/learner/` imports the shell `views.py` except `import_views.py` (and the oversight view if housed with it). The shell `views.py` imports `panels.learner.config.LearnerConfig` (for `interface_config`) and not `import_views`; `urls.py` imports both `views` and `panels.learner.import_views`. So no cycle with the shell as long as no `config.py` imports `import_views.py` and `import_views.py` is the only learner module that imports `views`.

`HistoryPanel`: now at `panels/audit_log/data_table_panels.py:22` (spec 2); views.py already imports it from there (V:141-143). `LearnerHistoryPanel` imports from `panels.audit_log`, never `views`. Fine. Spec 2's area rule: audit_log imports no other area.

Learner -> cohort (the only edge): `data_table_panels.py` imports `LearnerCohortDataTable` from `panels/cohort/data_tables.py`. `data_tables.py` (cohort) imports `CohortDataTable`'s needs from `common` only (`_interface_link`, `_active_status_column`, `VisibleCourseFilter`, `OrganisationScopedRequest`, `ToggleFilter`) plus `cohorts_visible_to`, `Count`, `Prefetch`, `CohortCourseRegistration`.

Cohort -> learner after spec 6 (one way): `CohortLearnerDataTable` (`panels/learner/data_tables.py`, for `CohortLearnersPanel`), `AddLearnerAction`, `ImportLearnersAction`, `_membership_changed_response`, `RemoveFromCohortAction`, `MoveToCohortAction`, `LearnerStatusFilter`-family if needed. Today (before the move) the cycle is `views.py` internal (`LearnerCohortDataTable` subclasses `CohortDataTable` while `CohortLearnerDataTable` subclasses `LearnerDataTable`), and in actions.py `AddLearnerToCohortAction(AddLearnerAction)` / shared membership actions. Remaining cycle risks:
- the `learner_status_badge` placement (headline 3);
- `partial_oversight_thread_older` placement (headline 4);
- while spec 6 is not landed, flat `views.py` imports from both `panels.learner.*` and still holds cohort code that imports `panels.learner` names; flat modules `actions.py`/`reporting.py` must import learner names from `panels.learner.actions` (e.g. `AddLearnerToCohortAction(AddLearnerAction)` stays in `actions.py` and imports `AddLearnerAction` from `panels.learner.actions`; `AddExistingLearnersAction` imports `_membership_changed_response`). `panels/learner/actions.py` must NOT import `freedom_ls.educator_interface.actions` back (it would use `inactive_cohort_response`, so that must already be in `common/actions.py`; likewise `may_see_staff_roles` from flat `filters.py` is staff-only and not used by learner actions).
- `actions.py:1557` lazy `from freedom_ls.educator_interface.views import interface_config` is in the staff block (`staff_member_changed_response`...), untouched.
- `quick_views.py` today lazily imports `views.learner_status_badge` (68) because `views.py` imports `quick_views.py`; after the badge moves to a leaf this lazy import disappears.
- `tests/test_views.py` imports `from freedom_ls.educator_interface import views as educator_views` (62) and uses it only at 6931-6951 (see section 4).

## 4. External references to moved names

### Production code

| File:line | Reference | New home |
|---|---|---|
| `urls.py:3` `from . import views` | `views.partial_oversight_thread_older` (18), `views.learner_import` (23), `learner_import_preview` (28), `learner_import_template` (33), `learner_import_errors` (38), `learner_import_result` (43), `partial_learner_import_status` (48). Remaining `views.interface_root` 10, `cohort_report_download` 13, `interface` 57 stay. | `panels.learner.import_views` (and wherever the oversight view lands). `urls.py` needs a second import line. |
| `templatetags/educator_tags.py:21-24` | `LearnerCourseSummary`, `learner_course_summaries` | `panels.learner.data_tables` |
| `reporting.py:16`, `reporting.py:29-31` | `RegisterLearnerForCourseAction`, `visible_registrations_with_progress`, both only for `LearnerCoursesPanel` | go away with the panel |
| `views.py:72-176` | see section 1 | |
| `quick_views.py:68` | lazy `views.learner_status_badge` | removed |
| `filters.py` | imports `VisibleCourseFilter` (13) only for `LearnerCourseFilter`; unused imports go with the move (`reduce`, `or_`, `can`, `cohorts_visible_to`, ... check) | |
| `actions.py` | self-referencing only; `AddLearnerToCohortAction(AddLearnerAction)`, `AddExistingLearnersAction` -> `_membership_changed_response` | learner `actions.py` |
| `freedom_ls/qa_helpers/management/commands/qa_create_learner_registrations_panel.py:4` | docstring names `LearnerRegistrationsPanel`, `freedom_ls/educator_interface/views.py` | docstring only; the file imports no learner name (grep-clean) |
| `claude_plugins/fls-dev/resources/testing.md:26` | `from freedom_ls.educator_interface.views import learner_import` | spec 7 docs sweep, but the example breaks now |
| `claude_plugins/fls-dev/skills/educator-interface/SKILL.md:41` | `freedom_ls/educator_interface/filters.py` (names learner/staff filters) | docs (spec 7) |
| other apps | none import learner names from `educator_interface` (grep over `freedom_ls/` found only `qa_helpers` course registration commands: `CourseCohortRegistrationDataTable`, `CourseLearnerRegistrationDataTable`, spec 4's) | |

### Tests: imports of moved names

| File:line | Import | Action |
|---|---|---|
| `tests/playwright/test_learners_list_flow.py:18` (use at 371) | `from ...views import LearnerDataTable` | `panels.learner.data_tables` |
| `tests/test_learner_section.py:24` | `from ...views import LearnerDataTable` | whole file moves to `tests/panels/learner/test_data_tables.py` |
| `tests/test_filters.py:14-19, 27-30` | `Learner*Filter` from `filters`; `CohortDataTable`, `StaffDataTable` from `views` | learner filter tests -> `tests/panels/learner/test_filters.py`; `CohortDataTable` tests -> `tests/panels/cohort/test_data_tables.py`; `StaffDataTable` is spec 3's |
| `tests/test_quick_views.py:38` | `LearnerQuickView` | repoint, learner part -> `tests/panels/learner/test_quick_view.py` |
| `tests/test_views.py:62` | `from freedom_ls.educator_interface import views as educator_views` (used only at 6931-6951) | `educator_views.LearnerDataTable` 6931, `.CohortLearnerDataTable` 6932, `.LearnerCohortDataTable` 6934, `.LearnerHistoryPanel` 6951: import from new modules; `CohortDataTable` 6933 -> `panels.cohort.data_tables` |
| `tests/test_views.py:63` | `DeactivateLearnersBulkAction` from `actions` (used 4977-4978) | `panels.learner.bulk_actions` |
| `tests/test_views.py:94-98` | `CohortDataTable`, `CourseDataTable`, `learner_status_badge` from `views` | `learner_status_badge` to its new leaf; `CohortDataTable` -> `panels.cohort.data_tables` |
| `tests/test_actions.py:34-50` | `AddLearnerAction`, `AddToCohortBulkAction`, `DeactivateLearnersBulkAction`, `DeactivateRegistrationBulkAction`, `RegisterForCourseBulkAction`, `RemoveFromCohortAction`, `RemoveFromCohortBulkAction` (learner); the rest stay | repoint |
| `tests/panels/common/test_bulk_actions.py:15, 35-36` | `DeactivateLearnersBulkAction` | repoint |
| `tests/test_reporting.py:1483-1494` | `_NEW_REPORTING_FILES` | add `panels/learner/panels.py` |
| `tests/invariants/test_course_shares.py:36-45` | `_learner_reregister_url`, `_post` (test_actions), `_content_action_url`, `_export_csv`, `_interface_url`, `_learner_page` (test_views) | move `_learner_page`, `_learner_reregister_url` to `tests/helpers.py` |
| `tests/invariants/test_answer_key_flag.py:22` | expects `educator_interface/views.py` mentions `show_answer_key` (course area, spec 4) | not affected |
| `tests/invariants/test_organisation_isolation.py:33-37` | `CohortCourseRegistrationDataTable`, `CourseCohortRegistrationDataTable`, `CourseDataTable` | not learner; learner URLs in that file are strings (845, 890, 1019: `learners/{pk}/__tabs/overview/__panels/...`) and stay valid |
| `tests/interface_walk.py:21`, `tests/test_interface_urls.py:22` | `interface_config`, `interface` | shell, unaffected |

### mock.patch / monkeypatch strings pointing at moved modules

| File:line | String | Test area | New target |
|---|---|---|---|
| `tests/test_actions.py:2619-2621` | `"freedom_ls.educator_interface.actions.move_between_cohorts"` | learner move (`test_a_member_leaving_mid_move_answers_422_with_the_reason`, 2608) | `...panels.learner.actions.move_between_cohorts` |
| `tests/test_actions.py:6308-6310` | `"freedom_ls.educator_interface.actions.record_learner_entry"` | learner resend (`test_a_failed_entry_sends_no_email_and_leaves_the_resend_open`, 6298) | `...panels.learner.actions.record_learner_entry` (the name is looked up in the module of `record_and_resend_setup_email`; check by running the test) |
| `tests/test_views.py:4461-4462, 4537-4538` | `"freedom_ls.educator_interface.views.own_conversation_with"` | learner messages | `...panels.learner.messages.own_conversation_with` |
| `tests/test_views.py:4515-4516, 4541-4542` | `"freedom_ls.educator_interface.views.send_message"` | learner messages | `...panels.learner.messages.send_message` |
| `tests/test_views.py:5234-5236` | `"freedom_ls.educator_interface.views.MAX_UPLOAD_BYTES"` | learner import (`test_the_upload_page_states_the_row_and_file_size_limits`, 5230) | `...panels.learner.import_views.MAX_UPLOAD_BYTES` |
| `tests/test_actions.py:9660`, `3543, 3941, 3959` | `actions.assign_role` | staff | spec 3, not here |
| `tests/test_actions.py:3746..9526`, `tests/test_views.py:3743, 3774` | `actions.grantable_roles`, `grantable_roles_for` | staff | spec 3 |
| `tests/test_actions.py:4549` | `actions.cohorts_visible_to` (`_reach_only` helper, 4546) | staff; but `cohorts_visible_to` is also looked up by learner actions (`_joinable_cohorts`) and cohort bulk class, so it keeps its flat target for staff | spec 3; no learner test uses `_reach_only` |
| `tests/test_actions.py:4512, 4837, 5232` | `actions.current_role_entries`, `deactivate_role` | staff | spec 3 |
| `tests/test_reporting.py:814, 1572` | `reporting.learner_avatars` | cohort panels (not `LearnerCoursesPanel`) | unchanged (still valid) |
| `tests/test_actions.py:7033, 7363` | `learner_management.learner_actions._fire` | learner bulk | unchanged (other app) |
| `tests/test_cohort_delete_action.py:348` | `mock.patch.object(DeleteEmptyCohortAction, ...)` | cohort | spec 6 |
| `tests/test_learner_import.py:367, 394` | `monkeypatch.setattr(learner_import_module, "add_learner", ...)` | flat domain module `learner_import.py` | unaffected |

No `mock.patch`/`monkeypatch` string anywhere names `educator_interface.filters`, `quick_views`, `reporting.<learner name>`, or a learner panel/table (grep over all of `freedom_ls/`). No playwright patch strings.

### Fixtures / invariants

- `tests/invariants/test_permission_matrix.py`, `test_config_authorisation.py`, `test_organisation_isolation.py`, `test_panel_template_rules.py` walk `interface_config` (via `interface_walk.walk_interface`), not dotted learner paths, so they stay green if `LearnerConfig` is imported in `views.py` unchanged. No invariant imports a learner name from a flat module except those above.
- `test_organisation/mirroring_baseline.txt:42` is the only listed learner line: `freedom_ls/educator_interface/tests/test_learner_section.py`. Other lines under `# educator_interface` (36-44) are for non-learner tests (cohort_delete, course_visibility, create_cohort, document_title, interface_urls, organisation_switcher, sidebar). The hook needs each module to exist before its test file; each new `tests/panels/learner/test_<module>.py` must mirror an existing module, empty `__init__.py` in every new test dir, never add to `mirroring_exemptions.txt`. `import_contracts.toml`/`declared_edges.toml`/`import_baseline.txt` carry no flat-module line for educator_interface (grep-clean); `lint-imports` is among the hooks to run.

## 5. Test split (approximate ranges, today's files)

Do it by test name, never by range (spec 2's plan rule). Learner test modules to create: `tests/panels/__init__.py` exists; add `tests/panels/learner/__init__.py` (empty), `tests/panels/cohort/__init__.py`.

### tests/test_learner_section.py (895 lines, 40 tests)
Whole file is learner. Imports `LearnerDataTable` only (24). Has an autouse `_site_context`, `_make_cohort`, `_make_learner`, `educator_client` fixture (65-76), `_learners_url` (79). -> `tests/panels/learner/test_data_tables.py`. Drop line 42 of `mirroring_baseline.txt`. Includes `TestLearnerDataTableQueryCost` (397-). None of its tests exercise `CohortLearnerDataTable`/`CohortDataTable`.

### tests/test_filters.py (532 lines, 27 tests)
- `CohortDataTable` (+`_cohort_rows` helper 50-52): tests at 56 (`..._hides_inactive_cohorts_while_its_toggle_is_unset`), 68, 91, 122, 503 (`..._widens_to_inactive_cohorts_on_the_inactive_parameter`) -> `tests/panels/cohort/test_data_tables.py`. The first of them (47-146) also uses `ToggleFilter`; the one at 503 uses `CohortDataTable.parse_query`.
- Learner filters: 150-290 (`LearnerStatusFilter` 155/166/177, `_cohort_filter` 181 + tests 186/203/218, `_course_filter` 230 + tests 235/249/265) and the parametrized `test_learner_course_filter_offers_a_course_only_when_it_reaches_the_organisation` at 520-531 -> `tests/panels/learner/test_filters.py`.
- Staff (`StaffRoleFilter`, fixture `staff_request` 292, tests 303-500) stay for spec 3.
- Needs `tests/helpers.py` (`COURSE_REACH_ROWS`, `_any_request`, `_educator_request`, `course_per_reach_row`) and the module-level `pytestmark = usefixtures("_site_context")`, `_site_context` from `tests/conftest.py:36`.

### tests/test_quick_views.py (about 810 lines)
Learner: `TestLearnerQuickView` 92-365 (class), `test_the_learners_list_renders_the_quick_view_trigger_attributes` 479, `TestLearnerQuickViewMessageBox` 575-692 with `_AllowPolicy`/`_ClosedPolicy`/fixtures 520-574, `TestLearnerQuickViewMessageBoxHidden` 693-735, tests 736-790 (nameless learner, other-org learner, unknown learner, malformed pk of a staff row `test_a_malformed_pk_of_a_staff_row_404s` 781 -- this one names staff), `_register_on_shared_course` 791 and `test_a_learner_quick_view_query_count_does_not_grow_with_shared_registrations` 799. Cohort: `TestCohortQuickView` 366-466 and `test_the_cohorts_list_renders...` 501 (spec 6). Shared helpers/fixtures at the top: `_site_context` autouse 53-56, fixture 58, `_quick_view_url` 73, `_get_quick_view` 83. Course: 467 stays. -> `tests/panels/learner/test_quick_view.py` (the file also needs `visible_registrations_with_progress` coverage if any exists: currently none direct).

### tests/test_reporting.py (about 1590 lines)
Learner part: `_courses_panel` 1308-1323 and `TestLearnerCoursesPanel` 1325-1481 -> `tests/panels/learner/test_panels.py`. `test_the_attention_card_names_a_nameless_learner_by_their_email` 1509 is the dashboard/cohort card; stays. `_NEW_REPORTING_FILES` 1483 and its test 1499 stay (edit the list, headline 11).

### tests/test_views.py (about 8700 lines; 373 tests; idea's ranges are stale)
Learner clusters (by today's line numbers, mixed with cohort/course/staff clusters in between):
- header/instance: `test_learner_detail_page_is_titled...` 278; learner header badge tests 535-565; learner settings/cohorts/courses placement 565-700 (`test_the_learner_settings_tab_offers_every_learner_action_to_an_org_admin` 565, `test_add_to_cohort_sits_under_the_learners_cohorts_panel` 587, `test_the_learners_cohorts_table_shows_as_cards_when_its_panel_is_narrow` 602, `test_register_for_a_course_sits_on_the_learners_courses_tab` 624, `test_a_cohort_admin_gets_the_cohort_and_course_actions_but_no_settings_tab` 639 (mixed), `test_the_learner_settings_tab_is_hidden_from_a_cohort_viewer` 666, `test_the_learner_header_refreshes_on_learner_changed` 686) -> `test_instance_view.py`
- learner page/overview/courses/registrations: `_learner_page` 1741, `_region_text` 1748, tests 1755-2040 (registrations card 1865-1985 -> `test_data_table_panels.py`; courses tab 1986-2040 -> `test_panels.py`; tabs/header 1755-1860 -> `test_instance_view.py`; `test_the_learner_cohorts_card_shows_the_join_date` 1848 -> `test_data_table_panels.py`)
- learner history tab and export: 2042-2560 (`_history_rows` 2055, `_cohort_history_access` 2215 is cohort; 2233-2332 are about cohort admin access to learner history, mixed) -> `test_data_table_panels.py`; `_history_export_url` 2347 ... 2560
- cohort-learners membership triggers 2561-2670 (learner remove/move triggers on a cohort's learners tab; mixed owner, cohort spec 6 for `CohortLearnerDataTable` rendering); 2780-2915 mixed (inactive cohort controls; add-to-cohort picker 2828, 2846 are learner)
- 3934-4000 learner history moves; 4159-4185 learner registrations/bulk run on history
- messages: 4186-4570 (`TestLearnerMessagesTab` class 4229-4571 with helpers 3885-3932 `_messaging_on`, `_msg_*`, `_tab_url` 4215, `_send_url` 4219, `_tab_document` 4223), oversight `TestOversight` 4614-4970 (helpers 4572-4613) -> `test_messages.py` (and oversight view tests wherever the view lands)
- bulk run status 4971-5150 (`_run_for`, `_poll`, run status tests, `test_the_learners_bar_promotes_four_actions...` 5097, `test_the_cohorts_bar_...` 5127): learner-table bulk bar 5097 -> learner; run-status tests are table-agnostic (use `DeactivateLearnersBulkAction`); keep with whoever owns `bulk_runs`; they only need the import repointed.
- import: 5153-6925 (`_import_url` test helper 5153, `import_world` fixtures 5169, 6201, tests through 6925; cohort-import tests 6738-6925 test learner `import_views` with `?cohort=`) -> `test_import_views.py`
- 6988-7020 `_learner_in_state`, `test_learner_status_badge_has_one_label_and_tone_per_state` 7011 -> badge leaf's test file (`tests/panels/common/test_badges.py` if the badge goes to `common/badges.py`)
- 7020 `test_the_history_tab_names_a_nameless_actor_by_their_email`; 7043-7105 table-fragment tests for a learner of another organisation (`LearnerConfig` authorisation) -> `test_config.py`
- cross-area picture/shared-course tests: 8295-8400 (`_learners_table`, `_registrations_table`, `_cohort_settings` surfaces), 8601 (`test_learners_list_names_the_owner...`), 8669 (`test_learner_courses_tab_names_the_owner...`) -> learner for 8601, 8669 and the learners/registrations surfaces
- Stays: cohort, course, staff (members), audit log, EDUCATOR_TABLES tests 6930-6985 (parametrized across all areas; only repoint names), `test_a_history_panel_says_what_will_be_recorded` 6953.
Imports used by learner tests that must be kept: `get_interface_page`, `organisation_admin_viewer`, `_audit_log_*`, `_history_entry`, `_record_run`, `_row_details`, `QUERY_BUDGET`, `profile_picture_sources`, `page_after_adding_rows` (all in `tests/helpers.py`); `interface_walk` only for invariants.

### tests/test_actions.py (about 9750 lines; 481 tests)
Learner action clusters: edit name 1038-1146; learner state 1148-1338; remove 1340-1559 (learner page and cohort page both; 1462-1495 on cohort page); add-to-cohort 1561-1745 (1747-1875 are the cohort-tab learner picker -> cohort); add learner 1876-2158 (mixed with cohort-tab variants 2084-2158); resend 2160-2298; move 2300-2659; learner register/unregister/reregister 2661-3135 (`_learner_reregister_url` 2970 -> `tests/helpers.py`); picker-empty/stale 3137-3310 (mixed). Cohort 127-1037 and cohort bits above stay. Staff 3312-5400+. `_post` (148), `_get_fragment` (140), `_picker_dialog` (152), `_dialog_title` (158), `_cohort_url` (127) are shared module helpers; `_confirm` (3358) is staff.
Learner bulk actions: `_bulk_confirm` 6538, tests 6562-6700 (generic), 6664-7035 deactivate/reactivate learners, `_bulk_cohort_post/confirm/_bulk_confirm_with` 7049-7071, 7189-7240 pickers, 7340-7500 add/remove cohort, 7503-7608 background threshold (generic with learner action), 7609-7680 `_bulk_pending_learner`, 7630-7833 register/unregister, 7835-7957 resend, 7957-7975 deactivate entries -> `test_bulk_actions.py`; cohort bulk 7976-8330 and generic `test_every_bulk_action_has_an_expected_weight_and_loading_text` 8408, 8353-8605 (retired slugs, dialog) mixed.
Module helper shared with `tests/helpers.py`: `_bulk_learner`, `_bulk_post`, `_bulk_text`, `_interface_url`, `_learners_bulk_url`, `course_per_reach_row` (already in helpers).

### Cohort table tests to `tests/panels/cohort/test_data_tables.py`
- `tests/test_filters.py` 47-146 and 503-517 (above); `tests/test_views.py` cohort list tests 824-1045 (`_cohort_table_request` 824, `_cohort_names` 834, `test_cohort_list_*` 847-995, `TestCohortListQueryCount` 996) and `test_cohort_list_learners_cell_reads_zero...` 1723; `test_the_cohorts_list_shows_created_as_day_month_year_and_24_hour_time` 1820. No test uses `LearnerCohortDataTable` directly except `EDUCATOR_TABLES` (6934) and the learner cohorts card tests (1848, 2561-2670 membership triggers).
- Conflict note: the `CohortDataTable` tests move in this spec but the rest of the cohort tests move in spec 6; only the table-level tests above go now, otherwise they would be orphaned.

### Conftest/fixtures the tests depend on
`tests/conftest.py`: `panel_request` (15), `_site_context` (36, opt-in via `usefixtures`). Root conftest fixtures used throughout: `site_aware_request`, `mock_site_context`, `logged_in_client`, `staff_client`, `admin_client`, `organisation`. `tests/panels/audit_log/conftest.py` exists (`audit_request`). Module-local fixtures that move with their users: `educator_client` (test_learner_section 65, test_quick_views), `role_holder_client` (test_views 2921, staff), `staff_client`/`import_world`/`_messaging_on` fixtures, `run_world` (4997). `tests/helpers.py` holds the shared helpers (spec 2 slice 1 added the History/audit ones). Rule from spec 2: `conftest.py` holds fixtures only; hand-imported helpers go to `tests/helpers.py`.

## 6. How specs 1 and 2 did it (conventions and gotchas)

Sources: `spec_dd/3. done/*educator-interface-refactor-1*/` and `*-2*/2. plan.md`, and the resulting code under `panels/common/`, `panels/audit_log/`, `panels/dashboard/`.

Conventions to copy:
- Each new module: a one-line purpose docstring (never where it came from, no spec/plan citation), `from __future__ import annotations`, absolute imports only (`from freedom_ls....`), and a sorted `__all__` listing every name the module owns, underscore names included (see `panels/audit_log/config.py:22-24`, `data_table_panels.py:17-19`, `common/request.py` as the model). `__all__` in `RUF022` order. Every `__init__.py` empty.
- Private names cross modules as plain imports (`from ...data_tables import _record_export` in `audit_log/config.py:11-15`; common/tables exports `_active_status_column` etc.). Keep leading underscores.
- Byte-for-byte moves: bodies, decorators, docstrings, comments, `# TODO`/`@claude` comments, test names and order; only import lines change. Quoted `cast("OrganisationScopedRequest", ...)` stay quoted. Drop imports left unused in the shrunk module in the same commit (ruff F401).
- Area import rule (spec 2 plan): a `panels/<area>/` module imports only `panels/common/`, `freedom_ls.panel_framework`, `educator_interface.avatars`/`events`/`paths`/flat domain modules and other apps, never `views`, `reporting`, `filters`, `actions`, `quick_views` flat modules, nor a sibling area (except the documented learner -> `cohort/data_tables.py` and `audit_log/data_table_panels` edges here). Inside an area imports run one way; spec 2 verified with a grep (`panels\.(views|actions|filters|quick_views|reporting)`) and a fresh-interpreter import per new module (`python -I -c "...django.setup(); import freedom_ls.educator_interface.panels.X"`).
- No re-export shim: the flat modules lose each moved name; every import and patch string is repointed. After the move, check each moved name with `grep -rnwE "(def|class) <name>"` (found only in its new module) and an import-reference grep that excludes `spec_dd`, `.git`, `node_modules`, `.venv`. Multi-line parenthesised imports escape one-line greps, so also read hits of `grep -rnw <name>`.
- Patch strings name the module that looks the name up. A stale patch string that still resolves (e.g. `reporting.learner_avatars`, still imported by cohort panels) patches nothing silently; spec 2 verified the dashboard patch by mutation. Attribute patches on a module object need a test run, not a grep.
- Slices and commits: each slice is at least one commit, plain `git commit`, the production module lands in the same or an earlier commit than its test file (the `test-mirroring` hook), every commit leaves the targeted tier green. Targeted tier via `.claude/ds/scripts/select_tests.sh --working-tree`, run its printed command in the background; full tier before the PR via `--range origin/main..HEAD`. Hooks to pass: `test-mirroring`, `lint-imports`, `app-map-fresh`, `mypy`, `ruff`.
- Closing checks (spec 2 slice 6): area-import greps empty; `uv run manage.py check`; `makemigrations --check --dry-run` clean (spec 5 differs: it adds one data migration, so check only that no model migration appears); collect-only count equals before plus new guard cases (spec 2: before-count file under `.sdd-work/`, deleted after); `git diff main -- test_organisation/mirroring_baseline.txt` shows only the removed lines; `git diff main --stat` shows nothing under `templates/`, `static/` and (for spec 5) only one new migration and the `urls.py` import edits.
- Shared test helpers move to `tests/helpers.py` first (spec 2 slice 1) so later moves do not leave cross-imports between test modules; spec 2 kept tests that span areas (e.g. five History tests) in `tests/test_views.py` and moved only the audit-owned ones. Test moves came after the production move in separate slices.
- `upgrade_notes.md`: spec 2 set `requires_migrations: false` and listed old/new dotted paths under Breaking changes (URL names, paths, app label, template paths unchanged). Spec 5 sets `requires_migrations: true` (a data migration), lists the 7 bulk-action old/new paths and notes that `BulkActionRun.action_path` rows are rewritten. The effort's decisions: pure move, no URL/template/app-label change, no shim.

Gotchas the earlier specs hit (relevant here):
- Mirroring hook order (production module before test file).
- Stale-but-resolving patch strings (`reporting.learner_avatars`).
- A guard test reading source files (`_NEW_REPORTING_FILES`) needed its list extended for the new module, which is the only assertion edit spec 2 made; spec 5 should do the same for `panels/learner/panels.py`.
- Cross-test imports (`invariants/test_course_shares.py` pulling private helpers from `tests.test_actions`/`tests.test_views`) force helpers to `tests/helpers.py`.
- Specs 3 and 4 are cutting the same files in parallel (`views.py`, `actions.py`, `test_views.py`, `test_actions.py`, one import block): conflicts are mechanical; each spec removes only its own ranges. Spec 4 adds `_course_title_column`/`_cohort_links_column` to `common/tables.py` (its `spec.md:13,36,63`; `plan.md:77-91`). Spec 3 leaves `inactive_cohort_response`/`cohort_not_empty_sentence` in flat `actions.py` (its `research_codebase.md:24`), so spec 5 owns moving `inactive_cohort_response` to `common/actions.py` and must repoint `RequiresActiveCohortMixin.refuse_inactive` (A:349) to it.

status: ok
