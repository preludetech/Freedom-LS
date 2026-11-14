# Research: code inventory for the educator_interface `panels/` refactor

Scope: `freedom_ls/educator_interface/` (repo root `/home/sheena/workspace/lms/freedom-ls-worktrees/main`). Read from `idea.md` first. Pure refactor: no behaviour, URL or template change.

Conventions: `V:` = `views.py` line, `A:` = `actions.py` line, `R:` = `reporting.py` line. Line ranges are inclusive and read from the grep of top-level definitions on the main branch at the time of writing. "Non-empty lines" are used for the small files, so real file lengths are a few percent higher. Test line counts are from `Grep ^` counts (files include blank lines).

## 0. Facts that shape everything (read first)

1. **`BulkActionRun.action_path` stores the dotted path of the bulk action class** (`freedom_ls/panel_framework/bulk_actions.py:348` writes `f"{type(self).__module__}.{type(self).__qualname__}"`; `panel_framework/bulk_runs.py:28` reads it back with `import_string`). 11 classes decorated `@register_bulk_action` in `actions.py` (A:3254, 3275, 3326, 3354, 3433, 3454, 3491, 3645, 3666, 3720, 3750) will change `__module__` when moved. Existing rows in production would then fail to load. Precedent: `freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py` rewrites `action_path` for a rename, with a test at `tests/migrations/test_0001_rename_unregister_bulk_runs.py`. The refactor therefore needs **either** a new data migration `0002` mapping 11 old paths to 11 new paths, **or** a re-export of the 11 classes from the old `educator_interface.actions` module. This is a decision for the spec, not a detail (see section 6). It is the one place where "pure refactor" touches the database.
2. **A circular-import workaround already exists**: `OrganisationScopedRequest` (V:252) is imported only under `TYPE_CHECKING` from `views` by `actions.py:189`, `quick_views.py:40`, `reporting.py:71` and `filters.py:41`; `actions.py:1770` also imports `interface_config` from `views` lazily inside a function (`refusal_response`/`staff_member_changed_response` region, uses `first_visible_section` at A:1780). Moving `OrganisationScopedRequest` into `panels/common/` removes four of five of these. The lazy `interface_config` import has to stay lazy (section 2).
3. **Test mirroring is enforced** (`test_organisation/mirroring_baseline.txt`, `mirroring_exemptions.txt`, hook `test-mirroring`, script `claude_plugins/django-stack/scripts/check_test_mirroring.py`). Rule (`claude_plugins/django-stack/resources/testing.md` "Mirroring", `Skill(fls-dev:testing)`): `<app>/<sub>/<name>.py` is tested by `<app>/tests/<sub>/test_<name>.py`; a cross-cutting test lives in a named subpackage listed in `mirroring_exemptions.txt`; every new test directory needs an empty `__init__.py` (pytest prepend mode; five `test_config.py` files in five directories collide without it). The checker fails on **stale baseline lines**, so moving any of the 10 files listed under `# educator_interface` in `mirroring_baseline.txt:36-46` requires editing that file in the same PR.
4. `test_organisation/import_baseline.txt:46` and `test_organisation/import_contracts.toml:197` name `freedom_ls.educator_interface.tests.test_course_visibility_and_interest` as a string. Moving that test file means editing both.
5. No template references any `educator_interface` Python module by dotted path (grep of `*.html` found none). The templates directory `educator_interface/templates/educator_interface/panels/*.html` is unrelated to a new Python package `educator_interface/panels/`; names do not collide.
6. The idea's `course_staff` area does not exist as a concept in the code. There is a **course** section (`CourseConfig`, V:2416) and a **staff** section (`StaffConfig`, V:2534, organisation staff), plus a cohort-scoped staff panel (`CohortStaffPanel`, V:1644). I propose two areas, `course` and `staff`, and flag it for the human (section 1).

## 1. Inventory by area

### 1.1 `views.py` (3376 lines)

| Lines | Defs | Area | Size |
|---|---|---|---|
| 1-248 | imports | split by use | 248 |
| 249-327 | `LAST_ORGANISATION_SESSION_KEY` (249), `OrganisationScopedRequest` (252), `OrganisationSectionConfig` (278) | common (request scope) | 79 |
| 330-339 | stale `# TODO` block (keep it: CLAUDE.md forbids deleting TODOs) | common/ or stays in views.py | 10 |
| 341-409 | `RelationLinkColumn` (342), `_interface_link` (352), `_learner_column` (380), `_registration_columns` (394) | common (table helpers; used by cohort, learner, course) | 69 |
| 411-501 | `CohortDataTable` | cohort | 91 |
| 502-534 | `LearnerCohortDataTable(CohortDataTable)` | learner page, subclass of a cohort table | 33 |
| 535-571 | `LearnerCourseSummary` (536), `learner_course_summaries` (544) (also imported by `templatetags/educator_tags.py:8`) | learner | 37 |
| 572-692 | `LearnerDataTable` (572), `_last_active_cell` (685) | learner | 121 |
| 693-711 | `CohortLearnerDataTable(LearnerDataTable)` | cohort tab, subclass of a learner table | 19 |
| 712-834 | `LearnerDetailsPanel` (712), `LearnerCohortsPanel` (724), `RegistrationRow` (765), `LearnerRegistrationsPanel` (779), `LearnerOverviewStack` (816), `LearnerCoursesStack` (828) | learner | 123 |
| 835-1075 | `_PERSON_TARGETS`, `_attach_target_users` (842), `_export_when/who/run_id` (873-881), `AuditLogEntryTable` (886), `TargetedAuditLogEntryTable` (978), `_record_export` (996), `HistoryPanel` (1031) | audit_log (shared by learner and cohort History tabs) | 241 |
| 1076-1096 | `LearnerHistoryPanel` | learner | 21 |
| 1097-1300 | `LearnerMessagesPanel` (1097), `LearnerOtherConversationsPanel` (1156), `LearnerMessagesStack` (1185), `SendToLearnerAction` (1197), `ViewConversationAction` (1244) | learner (messages / oversight) | 204 |
| 1301-1308 | `uuid_or_404` (used by learner messages V:1267, course preview V:2285/2296, oversight view V:2776) | common | 8 |
| 1309-1428 | `_oversight_role_label` (1309), `LearnerNamePanel` (1318), `LearnerAccountPanel` (1340), `LearnerSettingsStack` (1364), `settings_actions` (1374), `learner_actions` (1384), `LearnerTabSet` (1395), `LearnerInstanceView` (1406) | learner | 120 |
| 1429-1441 | `_LEARNER_STATUS_TONES`, `learner_status_badge` (1436) | learner (also used by `educator_tags.py`) | 13 |
| 1442-1456 | `active_status_badge` (1442), `inactive_badge` (1449) | common (used by cohort and tables) | 15 |
| 1457-1782 | `CohortDetailsPanel` (1457), `CohortCourseRegistrationDataTable` (1473), `CohortLearnersPanel` (1502), `CohortCoursesPanel` (1535), `CourseCompletion` (1554), `CohortCourseCompletionPanel` (1563), `CohortNamePanel` (1614), `CohortStaffPanel` (1644), `CohortStatusPanel` (1683), `CohortSettingsStack` (1709), `CohortOverviewStack` (1722), `CohortHistoryPanel` (1732), `CohortTabSet` (1745), `CohortInstanceView` (1757) | cohort | 326 |
| 1784-1846 | `CreateCohortAction` (1784), `CohortConfig` (1818) | cohort | 63 |
| 1848-1881 | `LearnerConfig` | learner | 34 |
| 1882-2004 | `CourseDataTable` | course | 123 |
| 2005-2049 | `CourseDetailsPanel(InstanceDetailsPanel)` | course | 45 |
| 2050-2333 | `OutlineRow` (2051), `_form_page_rows` (2091), `_outline_item_rows` (2112), `outline_rows` (2181), `CourseContentPanel` (2201), `_condition_question_text` (2219), `_form_preview_context` (2228), `PreviewContentAction` (2271), `PreviewCourseDetailsAction` (2309) | course (content outline and preview) | 284 |
| 2334-2435 | `CourseCohortRegistrationDataTable` (2334; imported by `qa_helpers`), `CourseCohortRegistrationsPanel` (2362), `CourseLearnerRegistrationDataTable` (2371; imported by `qa_helpers`), `CourseLearnerRegistrationsPanel` (2394), `CoursePanelStack` (2403), `CourseInstanceView` (2412), `CourseConfig` (2416) | course | 102 |
| 2436-2441 | `DashboardConfig` | dashboard | 6 |
| 2443-2591 | `StaffDataTable` (2443), `StaffConfig` (2534) | staff | 149 |
| 2592-2671 | `OrganisationAuditLogTable` (2592), `AuditLogConfig` (2639) | audit_log | 80 |
| 2673-2680 | `interface_config` (needs every config) | shell | 8 |
| 2682-2750 | `interface_root` (2683), `_resolve_organisation` (2710), `_attach_organisation` (2722), `_scoped_cohort` (2736) | shell | 69 |
| 2744-2757 | `cohort_report_download` | cohort (plain view) | 14 |
| 2759-2788 | `partial_oversight_thread_older` | learner (messages, plain view) | 30 |
| 2790-2851 | `scope_request` (2790, the organisation switcher's OOB wiring), `standalone_page_context` (2820) | shell / organisation switcher | 62 |
| 2853-3283 | learner import plain views and helpers: `_see_other`, `_learners_url`, `_import_url`, `FormatRow`, `_format_rows`, `_import_page`, `_import_denied`, `IMPORT_*` constants, `_label_counts`, `_count_of`, `_requested_import_or_404`, `_cohort_learners_url`, `_cohort_import_url`, `_import_upload_url`, `_import_cohort_or_404`, `learner_import` (3021), `learner_import_preview` (3065), `learner_import_template` (3142), `learner_import_errors` (3157), `_capped_error_rows`, `_import_status_context`, `learner_import_result` (3243), `partial_learner_import_status` (3265) | learner import (plain views) | 431 |
| 3285-3376 | `interface` (the one panel-framework entry view) | shell | 92 |

Roll-up of `views.py` (rounded):

| Area | Lines | Notes |
|---|---|---|
| imports (to be split) | 248 | |
| common (scope request, table helpers, badges, `uuid_or_404`) | ~170 | |
| cohort | ~510 | 91 table + 326 panels/instance + 63 config + 19 `CohortLearnerDataTable` + 14 download view |
| learner (panels, tables, messages, badge, config) | ~700 | excl. import views |
| learner import plain views | 431 | not panels |
| audit_log | ~320 | tables 241 + organisation table/config 80 |
| course (incl. content preview) | ~555 | preview/outline is 284 of it |
| staff | 149 | |
| dashboard | 6 | panel is in `reporting.py` |
| shell (`interface`, `interface_root`, switcher, `interface_config`) | ~240 | stays in a residual `views.py` |

### 1.2 `actions.py` (3772 lines)

| Lines | Defs | Area | Size |
|---|---|---|---|
| 1-190 | imports | split by use | 190 |
| 192-280 | `grantable_roles_for` (192), `roles_grantable_on` (204), `role_reach` (213), `actionable_roles` (232), `role_entries_shown_to` (250), `has_grantable_roles` (274) | staff (used by `StaffDataTable`, `StaffConfig`, `CohortStaffPanel`) | 89 |
| 281-309 | `_uuid_from`, `_action_params`, `_uuid_param`, `_staff_member_param` | common (the last is staff) | 29 |
| 310-353 | `inactive_cohort_response` (310), `cohort_not_empty_sentence` (324) | cohort | 44 |
| 354-412 | `RequiresActiveCohortMixin` (354), `ReasonMixin` (385) | `RequiresActiveCohortMixin` cohort; `ReasonMixin` common (used by cohort, learner, staff; `tests/invariants/test_reason_mixin.py` imports it) | 59 |
| 414-448, 498-666 | `EditCohortAction`, `CohortStateAction`, `DeactivateCohortAction`, `ReactivateCohortAction`, `DeleteEmptyCohortAction`, `RegisterCohortForCourseAction` | cohort | 204 |
| 449-497 | `EditLearnerNameAction` | learner | 49 |
| 667-781 | `LearnerStateAction`, `DeactivateLearnerAction`, `ReactivateLearnerAction`, `learner_state_actions`, `record_and_resend_setup_email`, `ResendSetupEmailAction` | learner | 115 |
| 782-843 | `KEEPING_NAMES_SHOWN`, `DeactivateCohortRegistrationAction` | cohort | 62 |
| 844-1025 | `_registration_changed_response`, `RegisterLearnerForCourseAction`, `DeactivateRegistrationAction`, `ReactivateRegistrationAction` | learner | 182 |
| 1026-1279 | `_membership_changed_response`, `_joinable_cohorts`, `_cohort_picker`, `MembershipAction` (1073), `RemoveFromCohortAction` (1134), `MoveToCohortAction` (1167) | **shared by learner and cohort pages** (`LearnerCohortsPanel` V:747 and `CohortLearnersPanel` V:1513-1514 both draw them) | 254 |
| 1280-1366 | `_empty_message`, `_refresh_on_change`, `_picker_on_get`, `_picker_title`, `_prepare_register_dialog`, `_picker_fragment` | common (picker dialog helpers) | 87 |
| 1367-1438 | `AddToCohortAction` | learner | 72 |
| 1439-1505 | `AddExistingLearnersAction` | cohort | 67 |
| 1506-1685 | `AddLearnerAction` (1506), `ImportLearnersAction` (1650) | learner (the learners list; `ImportLearnersAction` is also drawn on the cohort Learners tab V:1512) | 180 |
| 1686-1706 | `AddLearnerToCohortAction(RequiresActiveCohortMixin, AddLearnerAction)`, `cohort_state_actions` | cohort | 21 |
| 1707-1832 | `REFUSAL_MESSAGES`, `SEARCH_LISTBOX_ID`, `_organisation`, `_refused`, `refusal_response`, `staff_member_changed_response`, `staff_member_state`, `_entries_after` | staff | 126 |
| 1833-2982 | `AddStaffMemberAction` (1833, 495 lines), `AddRoleAction`, `AddStaffMemberToCohortAction` (2372), `CohortRoleAction` (2406), `ChangeRoleAction` (2438), `RemoveStaffFromCohortAction` (2541), `StaffRoleAction` (2586), `DeactivateRoleAction` (2634), `CohortChange`, `ChangeCohortsAction` (2758), `StaffMemberStateAction`, `DeactivateStaffMemberAction`, `ReactivateStaffMemberAction` | staff (the three `...Cohort...` ones are drawn only on the cohort Settings tab, V:1662-1664) | 1150 |
| 2983-3160 | `BULK_ACTIONS`, `register_bulk_action`, `bulk_actions_for_table`, `EducatorBulkAction` | common (bulk framework; `tests/interface_walk.py:20` imports `EducatorBulkAction`) | 178 |
| 3161-3577 | `LearnerBulkAction`, `CohortMembershipBulkAction`, `AddToCohortBulkAction`, `RemoveFromCohortBulkAction`, `LearnerStateBulkAction`, `Deactivate/ReactivateLearnersBulkAction`, `CoursePickerMixin` (3379), `CourseRegistrationBulkAction`, `RegisterForCourseBulkAction`, `DeactivateRegistrationBulkAction`, `ResendSetupEmailBulkAction` | learner (7 registered; `CoursePickerMixin` is shared with cohort bulk) | 417 |
| 3578-3772 | `CohortBulkAction`, `CohortCourseBulkAction`, `RegisterCohortForCourseBulkAction`, `DeactivateCohortRegistrationBulkAction`, `CohortStateBulkAction`, `Deactivate/ReactivateCohortsBulkAction` | cohort (4 registered) | 195 |

Roll-up of `actions.py` (rounded): common ~400, cohort ~600, learner ~1015, shared learner/cohort membership 254, staff ~1365, imports 190.

### 1.3 Other modules

| File | Non-empty lines | Contents and area |
|---|---|---|
| `filters.py` | 239 | `ShowInactiveFilter` (44) and `VisibleCourseFilter` (64): common. `LearnerStatusFilter` (85), `LearnerCohortFilter` (108), `LearnerCourseFilter` (135): learner. `may_see_staff_roles` (145), `StaffRoleFilter` (158): staff (`may_see_staff_roles` is also imported by `actions.py:50` and V:128). `AuditActorFilter` (206), `AuditActionFilter` (242), `AuditPeriodFilter` (263): audit_log. |
| `quick_views.py` | 132 | `visible_registrations_with_progress` (43), `LearnerQuickView` (61), `CohortQuickView` (119), `StaffQuickView` (137): one per area, 3 small classes. |
| `reporting.py` | 491 | Shared helpers (74-130: `render_region`, badges `progress_status_badge`/`flag_badge` used by `educator_tags.py`, `report_over_limit_message`); cohort report: `GenerateReportAction` (135), `CohortReportDownloadsPanel` (155), `LazyBodyPanel` (217, base also used by dashboard), `CohortNeedsAttentionPanel` (253), `CohortReportBodyPanel` (305), `CohortReportStack` (322), `QuizConfusionCard`; dashboard: `InlineFigures`..`gathered_figures` (332-523), `DashboardPanel` (524); learner: `LearnerCoursesPanel` (560). |
| `forms.py` | 247 | Forms for cohort (`CohortForm` 65, `CohortCourseRegistrationForm` 91, `LearnerPickerForm` 159), learner (`LearnerImportForm` 34, `LearnerNameForm` 83, `LearnerCourseRegistrationForm` 111, `CohortPickerForm` 131, `AddLearnerForm` 175), staff (`StaffEmailForm` 207, `AddStaffMemberForm` 213, `ChangeRoleForm` 273, `CohortSetForm` 289), common (`choice_error` 25, `BulkTargetPickerForm` 47, `ReasonForm` 300). Consumed by `actions.py` and the import views. |
| `staff.py` | 91 | `RoleEntry`, `staff_role_entries`, `current_role_entries`: domain helper for staff; also imported by `quick_views.py:24`, `actions.py:67`, `views.py:164`. |
| `learner_import.py` | 356 | Import domain logic (gate, row checks, commit, background run); consumed by import views, `actions.py:66`, `tasks.py`. |
| `messaging.py` | 84 | `own_conversation_with`, `oversight_conversations_for`, `other_educator_conversations`; consumed by learner messages panels and `quick_views.py:22`. |
| `urls.py` | 57 | `re_path`s to `views.interface_root`, `cohort_report_download`, `partial_oversight_thread_older`, the 7 learner import views, and `views.interface`. |
| not asked but present | | `paths.py` (12), `events.py` (9), `user_display.py` (13), `exceptions.py` (10), `tasks.py` (10), `notification_urls.py` (20), `templatetags/educator_tags.py`. Domain-helper or framework-glue modules, not panel code. Leave them flat. |

### 1.4 Areas beyond the six, and where they go

| Beyond-six area | Evidence | Proposal |
|---|---|---|
| course (section + content outline + preview) | V:1882-2435, 554 lines, own `CourseConfig` and instance view | its own `course/` area. This is the biggest gap in the idea's list. |
| course content preview | V:2050-2333 (outline rows, preview actions) | `course/content_preview.py` inside `course/` (284 lines; keeps `data_table_panels.py` readable). |
| staff (organisation staff) | V:2443-2591, A:1707-2982 (~1275 lines of actions) | its own `staff/` area; it is probably what the idea means by `course_staff`. Flag the name to the human. |
| learner import | V:2853-3283 (431 lines, 8 plain views, not panels) | `learner/import_views.py` (it is the learners list's "Import" action target; `ImportLearnersAction` already lives with learner). Or its own `learner_import/` area if kept apart from the learner instance code. Plain views are not panels; recommend `learner/import_views.py`. |
| reports / dashboard | `reporting.py` | split: `dashboard/panels.py` (R:332-560), `cohort/report_panels.py` (R:135-330), `learner/` takes `LearnerCoursesPanel` (R:560-end); shared `LazyBodyPanel`/`render_region`/badges go to `common/report.py`. |
| organisation switcher | `scope_request` V:2790, template `educator_interface/partials/organisation_switcher.html`, `tests/test_organisation_switcher.py` | stays in the residual shell `views.py` (with `interface`, `interface_root`, `_attach_organisation`) |
| settings | "Settings" is a tab (`CohortSettingsStack` V:1709, `LearnerSettingsStack` V:1364), not a section | no area; the stacks live in each area's `instance_view.py` |
| notifications / bulk run results | `notification_urls.py`, `tasks.py`, `partial_learner_import_status`; bulk run result modal is in `panel_framework` | not an area; leave `notification_urls.py`, `tasks.py` flat. The import status view goes with import views. |
| quick views | `quick_views.py` 132 lines | per-area `quick_view.py` (optional, see section 3) |
| audit_log | tables V:835-1075 shared by three consumers | its own `audit_log/` area (as in the idea) and a dependency of learner and cohort, not part of them |

### 1.5 What is genuinely shared (`common/`)

1. `OrganisationScopedRequest`, `OrganisationSectionConfig`, `LAST_ORGANISATION_SESSION_KEY` (V:249-327): used by every config, by `actions.py`, `quick_views.py`, `reporting.py`, `filters.py`, `test_denied_experience.py`.
2. Table helpers (V:341-409): `RelationLinkColumn`, `_interface_link`, `_learner_column`, `_registration_columns`; used by cohort, learner and course tables.
3. `active_status_badge`, `inactive_badge`, `uuid_or_404`.
4. `ReasonMixin`, param helpers (A:281-309), picker dialog helpers (A:1280-1366).
5. Bulk framework: `BULK_ACTIONS`, `register_bulk_action`, `bulk_actions_for_table`, `EducatorBulkAction`, `CoursePickerMixin` (A:2983-3160 and 3379).
6. Filters `ShowInactiveFilter`, `VisibleCourseFilter` (used by cohort, learner, course, staff tables).
7. Report helpers: `LazyBodyPanel`, `render_region`, `progress_status_badge`, `flag_badge`.

The audit-log table classes are shared by three consumers but have a natural home, so they are the `audit_log/` area, not `common/`.

## 2. Cross-area references and import dependencies

### 2.1 Edges found (a -> b means "a imports b")

- learner -> common, audit_log (`LearnerHistoryPanel(HistoryPanel)`, V:1076), reports helpers (`LearnerCoursesPanel`), `messaging.py`, `learner_import.py`.
- **learner -> cohort**: `LearnerCohortDataTable(CohortDataTable)` (V:502-534) and `LearnerCohortsPanel.data_table = LearnerCohortDataTable` (V:726). Membership actions `RemoveFromCohortAction`/`MoveToCohortAction` are shared.
- **cohort -> learner**: `CohortLearnerDataTable(LearnerDataTable)` (V:693-711), `CohortLearnersPanel` (V:1502) draws `AddExistingLearnersAction`, `AddLearnerToCohortAction(AddLearnerAction)` (A:1686), `ImportLearnersAction`, `RemoveFromCohortAction`, `MoveToCohortAction` (V:1510-1514).
- cohort -> staff: `CohortStaffPanel` (V:1644-1664) draws `AddStaffMemberToCohortAction`, `ChangeRoleAction`, `RemoveStaffFromCohortAction`; `roles_grantable_on` (V:1679).
- cohort -> audit_log (`CohortHistoryPanel(HistoryPanel)` V:1732, `TargetedAuditLogEntryTable`), cohort -> reports helpers (`CohortReportStack`).
- course -> common only. (Course tables use `_interface_link`, `_registration_columns`, `_learner_column`; `CourseDetailsPanel` uses `course_details_context`.)
- staff -> common, `staff.py`, filters (`StaffRoleFilter`). `StaffDataTable` uses `actionable_roles` (staff actions). **staff -> shell** lazily: A:1770 imports `interface_config` from `views` inside a function.
- audit_log -> common only.
- dashboard -> common only (`DashboardPanel` uses `visible_active_cohorts`, `gathered_figures`, all within `reporting.py`).
- shell (`views.py`, new residual) -> every config (`interface_config`) and `OrganisationScopedRequest`; `cohort_report_download` and `partial_oversight_thread_older` use `CohortConfig.get_instance_view` (V:2741) and `LearnerConfig.get_instance_view` (V:2770); import views use `LearnerConfig.get_denied_context` (V:2924) and `standalone_page_context` (shell).
- `reporting.py` -> `actions.py` (`RegisterLearnerForCourseAction`, R:20) and `quick_views.py` (R:26); `templatetags/educator_tags.py` -> `reporting.py` and `views.py` (`LearnerCourseSummary`, `learner_course_summaries`, `learner_status_badge`).

### 2.2 Graph (arrows are the imports a package split would create)

```
                    +--------- shell views.py / interface_config ----------+
                    |  imports every area's config                          |
                    v                                                       |
   dashboard   course   staff   audit_log   learner  <==>  cohort           |
        \         |       ^        ^           |  \         / |  \          |
         \        |       |        |           |   \       /  |   +--> staff (cohort Settings tab)
          +-------+-------+--------+-----------+----+-----+---+--> audit_log (History tabs)
                                    all  ---->  common
  staff --(lazy, inside refusal_response)--> shell.interface_config   [cycle, exists today]
  learner <==> cohort   [cycle, created by a naive split]
```

### 2.3 Cycles a package split would create, with fixes

1. **learner <-> cohort via the two subclassed tables.** `LearnerCohortDataTable` subclasses `CohortDataTable`; `CohortLearnerDataTable` subclasses `LearnerDataTable`. If both areas keep tables and panels in one module each, `learner/data_table_panels.py` and `cohort/data_table_panels.py` import each other. Fix: a separate `data_tables.py` per area that holds **only that area's base tables and nothing imported from the sibling**, and define each cross-subclass in the area whose rows it lists: `LearnerCohortDataTable` (rows are cohorts) in `cohort/data_tables.py`; `CohortLearnerDataTable` (rows are learners) in `learner/data_tables.py`. Then `cohort/data_tables` and `learner/data_tables` import only `common`; the panels modules import across (`learner/data_table_panels` -> `cohort/data_tables`; `cohort/data_table_panels` -> `learner/data_tables` and `learner/actions`). Package `__init__.py` files must stay empty so no package-level cycle appears. Note the idea's file list (`config.py`, `data_table_panels.py`, instance view) does not name `data_tables.py`; adding it is what makes the split acyclic.
2. **Membership actions shared by learner and cohort** (`MembershipAction`, `RemoveFromCohortAction`, `MoveToCohortAction`, A:1026-1279, 254 lines; plus `_joinable_cohorts`/`_cohort_picker`). Put them in `learner/actions.py` (the learner owns the membership; the cohort Learners tab is the secondary user). Then cohort -> learner is one-way and `learner/actions` must not import `cohort/`. The one thing in the learner action block that names cohorts, `AddToCohortAction` (A:1367), uses only models/forms, no cohort-area import, so this holds. `AddLearnerToCohortAction` (cohort) subclasses `AddLearnerAction` (learner): one-way cohort -> learner. Same for `CohortMembershipBulkAction(LearnerBulkAction)` which is learner-only.
3. **staff -> shell (lazy `interface_config` at A:1770)**. This is a real cycle today (actions -> views -> actions) hidden by a function-level import. It becomes `staff/actions.py -> views.py -> staff/config.py -> staff/actions.py`. Keep the import function-level and update its dotted path; do not try to remove it in this refactor (that is a behaviour-adjacent change). Alternative for a later spec: read the section list from the request/config at call time.
4. **`OrganisationScopedRequest` TYPE_CHECKING imports** (4 files): resolved by moving the class to `common/request.py`; the `if TYPE_CHECKING:` guards can then become ordinary imports (do this in the same PR or leave guards; both work).
5. **`reporting.py` -> `actions.py` -> `views.py`**: `reporting.py` imports `RegisterLearnerForCourseAction` (R:20). After the split `learner/panels` imports `learner/actions`, no cycle, provided `LearnerCoursesPanel` moves into `learner/`.
6. **Config -> instance view -> panels -> actions** is a straight line within each area; no area config imports another area's config. The only config-to-config use is in plain views (`cohort_report_download`, oversight view, import views) calling `CohortConfig`/`LearnerConfig`. These plain views sit in the area they authorise (`cohort/`, `learner/`), so they import their own config; `learner/import_views.py` reaching `standalone_page_context` in the shell is the one place a leaf area imports the shell: acyclic as long as no `config.py` imports `import_views.py` (only `urls.py` does).

## 3. Proposed target tree

```
freedom_ls/educator_interface/
  views.py                      # residual shell, ~240 lines: interface(), interface_root(), _resolve/_attach_organisation,
                                #   scope_request(), standalone_page_context(), interface_config
  urls.py                       # imports views + the area plain-view modules (names unchanged)
  actions.py, quick_views.py, filters.py, reporting.py   # deleted at the end (or reduced to one-line re-exports; see section 6)
  forms.py staff.py learner_import.py messaging.py paths.py events.py ...   # unchanged, flat
  panels/
    __init__.py                 # EMPTY (no package-level imports)
    common/
      __init__.py
      request.py                # OrganisationScopedRequest, OrganisationSectionConfig, LAST_ORGANISATION_SESSION_KEY
      tables.py                 # RelationLinkColumn, _interface_link, _learner_column, _registration_columns
      badges.py                 # active_status_badge, inactive_badge
      ids.py                    # uuid_or_404
      filters.py                # ShowInactiveFilter, VisibleCourseFilter
      actions.py                # ReasonMixin, _uuid_from/_action_params/_uuid_param, picker dialog helpers
      bulk_actions.py           # BULK_ACTIONS, register_bulk_action, bulk_actions_for_table, EducatorBulkAction, CoursePickerMixin
      report.py                 # LazyBodyPanel, render_region, progress_status_badge, flag_badge
    dashboard/
      __init__.py
      config.py                 # DashboardConfig
      panels.py                 # DashboardPanel + InlineFigures..gathered_figures (R:332-560)
    cohort/
      __init__.py
      config.py                 # CohortConfig, CreateCohortAction (it is only the config's action; or actions.py)
      data_tables.py            # CohortDataTable, CohortCourseRegistrationDataTable, LearnerCohortDataTable
      data_table_panels.py      # CohortLearnersPanel, CohortCoursesPanel, CohortHistoryPanel
      panels.py                 # Details, Name, Status, Staff, CourseCompletion panels, report panels (or report_panels.py)
      report_panels.py          # GenerateReportAction, CohortReportDownloadsPanel, CohortNeedsAttentionPanel, CohortReportBodyPanel, CohortReportStack
      instance_view.py          # FILE: CohortSettingsStack, CohortOverviewStack, CohortTabSet, CohortInstanceView
      actions.py                # RequiresActiveCohortMixin, Edit/State/Delete/RegisterCohort..., AddExistingLearners, AddLearnerToCohort, cohort_state_actions
      bulk_actions.py           # CohortBulkAction ... ReactivateCohortsBulkAction (4 registered)
      report_download.py        # cohort_report_download, _scoped_cohort
      quick_view.py             # CohortQuickView (optional)
    learner/
      __init__.py
      config.py                 # LearnerConfig
      data_tables.py            # LearnerDataTable, CohortLearnerDataTable, LearnerCourseSummary, learner_course_summaries
      data_table_panels.py      # LearnerCohortsPanel, LearnerHistoryPanel (and learner registrations if a table)
      panels.py                 # LearnerDetailsPanel, LearnerRegistrationsPanel, LearnerNamePanel, LearnerAccountPanel, LearnerCoursesPanel
      messages.py               # LearnerMessagesPanel, LearnerOtherConversationsPanel, LearnerMessagesStack, SendToLearnerAction, ViewConversationAction, partial_oversight_thread_older
      instance_view.py          # FILE: stacks, LearnerTabSet, LearnerInstanceView, learner_actions, settings_actions, learner_status_badge
      actions.py                # learner state/name/registration actions, membership actions, AddToCohortAction, AddLearnerAction, ImportLearnersAction
      bulk_actions.py           # LearnerBulkAction ... ResendSetupEmailBulkAction (7 registered)
      filters.py                # LearnerStatusFilter, LearnerCohortFilter, LearnerCourseFilter
      import_views.py           # the 8 learner import plain views and helpers (431 lines)
      quick_view.py             # LearnerQuickView (optional)
    course/
      __init__.py
      config.py                 # CourseConfig
      data_tables.py            # CourseDataTable, CourseCohortRegistrationDataTable, CourseLearnerRegistrationDataTable
      data_table_panels.py      # CourseCohortRegistrationsPanel, CourseLearnerRegistrationsPanel
      panels.py                 # CourseDetailsPanel
      content_preview.py        # OutlineRow, outline_rows, CourseContentPanel, PreviewContentAction, PreviewCourseDetailsAction
      instance_view.py          # FILE: CoursePanelStack, CourseInstanceView (~10 lines)
    staff/
      __init__.py
      config.py                 # StaffConfig
      data_tables.py            # StaffDataTable
      actions.py                # all staff actions + refusal/state helpers + role helpers
      filters.py                # StaffRoleFilter, may_see_staff_roles
      quick_view.py             # StaffQuickView (optional)
    audit_log/
      __init__.py
      config.py                 # AuditLogConfig
      data_tables.py            # AuditLogEntryTable, TargetedAuditLogEntryTable, OrganisationAuditLogTable, _attach_target_users, _record_export
      data_table_panels.py      # HistoryPanel
      filters.py                # AuditActorFilter, AuditActionFilter, AuditPeriodFilter
```

### Instance view: file or directory?

**A file (`instance_view.py`), in every area that has one.** Reasons from the code:

- Only two areas have an instance view with real size: cohort (V:1709-1782, about 75 lines for 2 stacks + TabSet + InstanceView) and learner (V:816-834 and 1364-1428, about 85 lines, 4 stacks + TabSet + InstanceView). Course has 10 lines (V:2403-2414). Dashboard, staff and audit_log have none.
- The classes inside an instance view are thin wiring (`children = {...}` dicts and a few overrides). The bulk of the area code is the panels they list, and those already have their own modules by kind (`panels.py`, `data_table_panels.py`, `messages.py`). Directories would hold one 20-line file each.
- Learner has about 12 panel/stack classes, cohort about 10; both are listed by name in `children` dicts and so need to be imported by the instance view module, not nested under it.

A directory would only start to pay if a future instance view gained many nested stacks. Revisit then.

### Where actions, filters and quick views go

- **Actions: per area** in `actions.py`, with the genuinely shared bits in `common/actions.py` and `common/bulk_actions.py`. Per-area bulk actions go in `bulk_actions.py`, not `data_table_panels.py` as the idea suggests: learner's bulk actions are 417 lines, which would double the size of `data_table_panels.py` and mix panels with classes whose dotted path is persisted (section 0.1). Record the disagreement with the idea for the human.
- **Filters: per area** in `filters.py` (learner, staff, audit_log), with `ShowInactiveFilter`/`VisibleCourseFilter` in `common/filters.py`. They are used by only their own area's tables.
- **Quick views: per area `quick_view.py`**, but this is the lowest-value move (3 classes, 132 lines total, one shared helper `visible_registrations_with_progress`). Recommended as the last, optional step; `quick_views.py` can stay flat in the first pass.
- `forms.py`, `staff.py`, `learner_import.py`, `messaging.py`, `paths.py`, `events.py`, `user_display.py` stay flat: they are domain helpers shared across areas and have their own test files that already mirror them.

## 4. Tests

### 4.1 Inventory (`freedom_ls/educator_interface/tests/`, 54 Python files, 33150 lines)

| File | Lines | Mirrors | Fate after refactor |
|---|---|---|---|
| `test_views.py` | 8558 (413 tests) | `views.py` | split by area (below) |
| `test_actions.py` | 9444 (464 tests) | `actions.py` | split by area (below) |
| `test_reporting.py` | 1357 (57 tests) | `reporting.py` | split: dashboard / cohort report / learner courses / common report helpers |
| `invariants/test_organisation_isolation.py` | 1045 (46) | cross-cutting | stays (exempt) |
| `test_learner_section.py` | 895 (39) | none (in baseline); imports `views.LearnerDataTable` | -> `panels/learner/test_data_tables.py` |
| `invariants/test_permission_matrix.py` | 857 (16) | cross-cutting | stays |
| `test_quick_views.py` | 788 (42) | `quick_views.py` | stays flat in pass 1; later 3 files if quick views are split |
| `test_filters.py` | 764 (43) | `filters.py`; imports `views.CohortDataTable`, `StaffDataTable` | split by area filters |
| `test_staff.py` | 659 (32) | `staff.py` | stays (module unchanged) |
| `test_cohort_delete_action.py` | 576 (26) | none (baseline); imports `actions`, `views.CohortConfig` | -> `panels/cohort/test_actions.py` |
| `test_dashboard.py` | 543 (20) | none (baseline); imports `reporting.gathered_figures` | -> `panels/dashboard/test_panels.py` |
| `test_learner_import.py` | 496 (21) | `learner_import.py` | stays |
| `test_create_cohort_action.py` | 391 (17) | none (baseline); imports `views.CohortConfig, CreateCohortAction` | -> `panels/cohort/test_config.py` (or test_actions) |
| `test_denied_experience.py` | 385 (15) | none (baseline); imports `views.OrganisationSectionConfig` | -> `panels/common/test_request.py` |
| `test_organisation_switcher.py` | 325 (17) | none (baseline) | stays top-level with a shell test, or `test_views.py` residual |
| `test_course_visibility_and_interest.py` | 262 (8) | none (baseline); imports `views.CourseDataTable`, `CourseDetailsPanel` | -> `panels/course/test_data_tables.py` + `test_panels.py` |
| `invariants/test_config_authorisation.py` | 274 (9) | cross-cutting; imports `views` configs, `interface_walk` | stays |
| `test_sidebar.py` | 250 (13) | none (baseline) | stays top-level (shell) |
| `test_interface_urls.py` | 226 (12) | none (baseline); imports names from `views` | stays top-level (shell) |
| `test_forms.py` | 242 (18) | `forms.py` | stays |
| `test_messaging.py` | 206 (10) | `messaging.py` | stays |
| `interface_walk.py` | 195 | helper for invariants; imports `actions.EducatorBulkAction`, `views.interface_config` | stays; update imports |
| `test_document_title.py` | 95 (3) | none (baseline) | stays top-level (shell) |
| `test_notification_urls.py`, `test_user_display.py`, `migrations/test_0001_...py` | 44, 24, 63 | `notification_urls.py`, `user_display.py`; migration is cross-cutting | stay |
| `invariants/*` (other 5 files) | 34, 22, 16, ... | exempt directory (`mirroring_exemptions.txt:18`) | stay; `test_reason_mixin.py` imports `actions.ReasonMixin`, `test_system_checks.py` none |
| `playwright/` (24 files + `conftest.py`, `helpers.py`, 5254 lines) | | browser tests, exempt from mirroring by the checker (`find_violations` skips `tests/playwright/`) | stay in `playwright/`; only `test_learners_list_flow.py:18` imports `views.LearnerDataTable` (update) |

### 4.2 How `test_views.py` splits (line ranges, approximate; the file is 8558 lines)

| Area | Ranges | ~Lines |
|---|---|---|
| cohort (pages, list, completion, header, Learners tab, Courses tab, Settings tab) | 158-400 (mixed shell/cohort), 402-660, 823-1070, 1070-1690, 2472-2810 | ~1500 |
| learner instance (tabs, registrations, history, history export) | 1691-2470, 3801-4040 (cohort+learner history), 7169-7320 | ~1200 |
| learner messages / oversight | 4573-5320 (`TestLearnerMessagesTab` 4623, `TestOversight` 4954) | ~750 |
| learner import | 5499-7090 (every `import_world` test) | ~1600 |
| staff section | 2811-3740 | ~940 |
| audit_log (organisation log, filters, export) | 4044-4570, 7317-7680 | ~890 |
| course (details, outline, content preview) | 675-820, 7699-8558 | ~1000 |
| cross-cutting / shell (nav toggle, breadcrumb, bulk bars, bulk run result views, data-table message invariants) | 299-400, 5325-5435, 7090-7165 | ~300 |

The `educator_views.*` tuple at test_views.py:7089-7109 (parametrised over every table and both History panels) is cross-cutting (it walks tables from every area) and needs a home: `tests/panels/common/test_data_tables_messages.py` that imports from each area, or the residual `test_views.py`.

### 4.3 How `test_actions.py` splits (approximate; the file is 9444 lines)

| Area | Ranges | ~Lines |
|---|---|---|
| cohort actions (rename, state, delete, register, unregister, learner picker, add learners) | 164-980, 1682-1825, 2023-2100 | ~1050 |
| learner actions (name, state, remove/add/move membership, resend, register/unregister/re-register, add learner, empty-picker states) | 985-1680, 1827-2020, 2105-3150 | ~1950 |
| staff actions (add member lookups, roles, change cohorts, deactivate/reactivate member, search, plus the cohort-scoped remove/change role at 8560-9444) | 3157-5735, 8560-9444 | ~3450 |
| bulk learner | 6519-7680 | ~1160 |
| bulk cohort | 7683-8050 | ~370 |
| cross-cutting (audit entries written by actions, reason field, stale-picker 422s, bulk framework 8055-8530) | 5739-6515, 8055-8530 | ~1250 |

### 4.4 Target test tree (mirroring rule: `tests/<sub>/test_<name>.py` mirrors `<sub>/<name>.py`)

```
tests/
  __init__.py
  conftest.py                         # unchanged
  interface_walk.py                   # unchanged helper
  invariants/                         # unchanged (exempt; all invariants stay)
  migrations/                         # unchanged
  playwright/                         # unchanged (exempt by the checker)
  test_views.py                       # residual: shell (interface(), switcher, nav toggles) ~300 lines
  test_interface_urls.py test_sidebar.py test_document_title.py test_organisation_switcher.py   # shell; stay (baseline lines kept, or fold into test_views.py)
  test_forms.py test_staff.py test_learner_import.py test_messaging.py test_notification_urls.py test_user_display.py test_quick_views.py   # unchanged
  panels/
    __init__.py
    common/__init__.py  test_request.py (was test_denied_experience.py)  test_actions.py  test_bulk_actions.py  test_filters.py  test_tables.py ...
    dashboard/__init__.py  test_panels.py (was test_dashboard.py + part of test_reporting.py)
    cohort/__init__.py  test_config.py  test_data_tables.py  test_data_table_panels.py  test_panels.py  test_instance_view.py  test_actions.py  test_bulk_actions.py  test_report_panels.py
    learner/__init__.py  test_data_tables.py  test_panels.py  test_messages.py  test_actions.py  test_bulk_actions.py  test_import_views.py  test_filters.py
    course/__init__.py  test_data_tables.py  test_panels.py  test_content_preview.py
    staff/__init__.py  test_data_tables.py  test_actions.py  test_filters.py
    audit_log/__init__.py  test_data_tables.py  test_data_table_panels.py  test_filters.py
```

Rules to apply, from `Skill(fls-dev:testing)` and `claude_plugins/django-stack/resources/testing.md`:

- Every directory needs an empty `__init__.py` (several `test_actions.py`, `test_data_tables.py` share names across areas).
- A test file's name must match an existing module in the matching path (`conforms()` in `check_test_mirroring.py`). So a test file for a module that does not exist (e.g. `panels/cohort/test_instance_view.py` when the PR only creates `panels/cohort/config.py`) fails the hook. Test directories should be created in the same PR as the module they mirror.
- The 10 files in `mirroring_baseline.txt:36-46` that move drop out of the baseline in the same PR; the ones that stay (shell tests, `test_sidebar.py`, `test_interface_urls.py`, `test_document_title.py`, `test_organisation_switcher.py`) keep their lines. `test_views.py` shrinking to the shell still mirrors `views.py`.
- Cross-cutting tests (`invariants/`, `migrations/`, and `playwright/`) stay where they are; a new cross-cutting directory would need a line in `mirroring_exemptions.txt` with a reason. `tests/invariants/` is already exempt.
- Update `test_organisation/import_baseline.txt:46` and `import_contracts.toml:197` if `test_course_visibility_and_interest.py` moves.

## 5. Who references these modules by dotted path

### 5.1 Production code (outside `educator_interface/tests/`)

| Place | Reference | Count |
|---|---|---|
| `freedom_ls/educator_interface/urls.py:3` | `from . import views` and 9 `views.<name>` uses (lines 10, 13, 18, 23, 28, 33, 38, 43, 48, 57) | 1 import, 10 names |
| `config/urls.py:68`, `freedom_ls/base/tests/error_pages_urls.py:45` | `include("freedom_ls.educator_interface.urls")` (urls module unchanged) | 2, no change |
| `config/settings_base.py:135`, `apps.py:6`, `contrib/conformance/test_urls.py:74` | app label only | no change |
| `freedom_ls/educator_interface/templatetags/educator_tags.py:7-12` | `reporting.flag_badge, progress_status_badge`; `views.LearnerCourseSummary, learner_course_summaries, learner_status_badge` | 2 imports (4 names) |
| `freedom_ls/qa_helpers/management/commands/qa_create_course_cohort_registrations.py:50` | `views.CourseCohortRegistrationDataTable` | 1 |
| `freedom_ls/qa_helpers/management/commands/qa_create_direct_course_registrations.py:42` (docstring :6 also names `views.py`) | `views.CourseLearnerRegistrationDataTable` | 1 import + 1 docstring |
| `freedom_ls/reports/gather.py:371` | docstring: "The guard proven at educator_interface/views.py" | 1 docstring |
| inside the app | `actions.py` -> `events`, `filters`, `forms`, `learner_import`, `staff`, `user_display`, plus `views` (TYPE_CHECKING at 189, lazy at 1770); `reporting.py` -> `actions` (20), `events`, `quick_views` (26), `views` (TYPE_CHECKING at 71); `quick_views.py` -> `events`, `messaging`, `paths`, `staff`, `user_display`, `views` (TYPE_CHECKING at 40); `filters.py:41` -> `views` (TYPE_CHECKING); `tasks.py:11` -> `learner_import`; `views.py:77-165` -> actions (35 names), events, exceptions, filters (10 names), forms, learner_import (11 names), messaging, paths, quick_views, reporting, staff, tasks | |
| `freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py:5` | string `"freedom_ls.educator_interface.actions."` (historical data migration; leave) | 1 |
| `freedom_ls/base/notification_categories.py:53` | `url_builder="freedom_ls.educator_interface.notification_urls.bulk_run_table_url"` (module unchanged) | no change |
| **database** | `BulkActionRun.action_path` rows for the 11 registered bulk action classes | see section 0.1 |
| templates (`*.html`) | no dotted Python references | 0 |
| `docs/` | `docs/app_structure.md` lists the app only (generated; regenerate only if the app graph changes, which it should not) | 0 changes |
| `claude_plugins/fls-dev` | `resources/testing.md:26` (`from freedom_ls.educator_interface.views import learner_import`, an example); `skills/educator-interface/SKILL.md:41` (`educator_interface/filters.py`); `skills/domain-glossary/SKILL.md:173` (`educator_interface/messaging.py`, unchanged if `messaging.py` stays); `skills/alpine-js/SKILL.md` and `skills/playwright-tests/SKILL.md` name templates and `tests/playwright/conftest.py` only (no change) | 3 to edit if their targets move |
| `test_organisation/` | `mirroring_baseline.txt:36-46` (10 files), `mirroring_exemptions.txt:18` (invariants, stays), `import_baseline.txt:46`, `import_contracts.toml:197` | up to 3 files |
| other `spec_dd/` docs | many mentions of `educator_interface/views.py` in `spec_dd/3. done/` and a few in `1. next/` and `2. in progress/` (about 155 files, 402 hits); historical, do not edit | 0 changes |

### 5.2 Tests (`educator_interface/tests/`)

- 18 test files import from `views`/`actions` by dotted path: `test_views.py` (21 hits), `test_actions.py` (30), `test_filters.py` (2), `test_cohort_delete_action.py` (2), `test_course_visibility_and_interest.py` (2, one lazy import at line 260), `interface_walk.py` (2), `invariants/test_config_authorisation.py` (2, from `views` plus `interface_walk`), `invariants/test_organisation_isolation.py`, `invariants/test_reason_mixin.py`, `test_create_cohort_action.py`, `test_denied_experience.py`, `test_interface_urls.py`, `test_learner_section.py`, `test_quick_views.py`, `test_dashboard.py`, `test_reporting.py`, `migrations/test_0001_...py`, `playwright/test_learners_list_flow.py`.
- **`mock.patch`/`monkeypatch` string targets naming `freedom_ls.educator_interface.*`**: 29 in the two big files, each of which must be re-pointed at the module where the name is *looked up*, not where it is defined.
  - `test_actions.py`: 22 of the form `"freedom_ls.educator_interface.actions.<name>"` at lines 2494 (`move_between_cohorts`), 3388, 3786, 3804 (`assign_role`), 3591, 3709, 3729, 3755, 3952, 3994, 4137, 4749, 4809, 4971 (`grantable_roles`), 4357 (`current_role_entries`), 4394 (`cohorts_visible_to`), 4664, 5059 (`deactivate_role`), 6136 (`record_learner_entry`), 9202, 9366, 9424 (`grantable_roles_for`). When `actions.py` is split, each of these names will be imported by a different module (`staff/actions.py`, `learner/actions.py`, `cohort/actions.py`), so each string changes.
  - `test_views.py`: 7: lines 3610 and 3641 (`...actions.grantable_roles`), 4802 and 4878 (`...views.own_conversation_with`), 4856 and 4882 (`...views.send_message`), 5543 (`...views.MAX_UPLOAD_BYTES`); these become `panels.learner.messages` / `panels.learner.import_views` paths.
  - `monkeypatch.setattr(actions_module, ...)` style (attribute patches on the imported module object; `test_actions.py:33`) breaks silently if the module split leaves the attribute in a different module: needs a run, not just a grep.
  - Other string patches (`freedom_ls.learner_management.*`, `freedom_ls.webhooks.*`, `freedom_ls.panel_framework.*`, `...tests.test_messaging.ClosedPolicy`) do not change.
- `test_views.py:7089-7109` uses `educator_views.<TableName>` for 10 tables/panels; attribute access through the module object.

## 6. Candidate ways to slice into specs

Each spec = one reviewable PR. All of them need the same first step (scaffolding `panels/` + `common/`), because every area imports `OrganisationScopedRequest`, `OrganisationSectionConfig` and the table helpers.

**Cross-cutting decision to make in whichever option is chosen: how to handle the 11 persisted bulk action paths (section 0.1).** (a) a data migration `0002` mapping each old dotted path to its new one (reversible), in the same PR that moves each area's bulk actions; or (b) keep `educator_interface/actions.py` as a re-exporting shim of those 11 names for the migration period. Recommend (a) for "no leftover shim", plus a test in the style of `tests/migrations/test_0001_...py`.

### Option A: vertical slices by area, bottom-up (recommended)

| Spec | Content | Moves (approx) | Tests moved |
|---|---|---|---|
| A1 scaffolding + common | `panels/` + `common/` (request, tables, badges, ids, filters, `ReasonMixin`, bulk framework, report helpers); residual `views.py` re-imports from `common`; `OrganisationScopedRequest` TYPE_CHECKING hacks replaced; mirror dirs created | ~170 V + ~400 A + ~60 filters + ~60 R = ~700 lines | `test_denied_experience.py`, `test_filters` common part |
| A2 audit_log | `audit_log/` (tables, HistoryPanel, config, filters) | ~320 V + ~120 filters | audit slices of `test_views.py` (~890) and `test_filters.py` |
| A3 staff | `staff/` (config, table, 1365 lines of actions, filters) | ~150 V + ~1365 A + ~60 | ~3450 of `test_actions.py`, ~940 of `test_views.py` |
| A4 course | `course/` incl. content preview | ~555 V | ~1000 of `test_views.py`, `test_course_visibility_and_interest.py` |
| A5 dashboard | `dashboard/` (config + panel, `reporting.py` dashboard half) | ~6 V + ~230 R | `test_dashboard.py`, dashboard part of `test_reporting.py` |
| A6 learner + cohort | `learner/` and `cohort/` together (cycle: sections 2.3.1 and 2.3.2), incl. `reporting.py` remainder, bulk actions with the data migration, `learner/import_views.py`, `cohort/report_download.py` | ~1200 V + ~1900 A | ~1500 + ~1200 + ~750 + ~1600 of `test_views.py`; ~1050 + ~1950 + ~1530 of `test_actions.py`; `test_learner_section.py`, `test_cohort_delete_action.py`, `test_create_cohort_action.py` |
| A7 shell cleanup | delete the emptied `actions.py`/`quick_views.py`/`filters.py`/`reporting.py`, trim `views.py`, update `urls.py`, `educator_tags.py`, `qa_helpers`, docs/skills, baselines | small | residual |

Parallelism: A2, A3, A4, A5 are independent of each other (disjoint line ranges, disjoint test ranges) and can run in parallel after A1 merges. Collisions: all four edit the same import block of `views.py` (V:77-165) and the same two test files (`test_views.py`, `test_actions.py`), so they conflict textually on merge even when logically independent; keep each PR's edits to deleting its own ranges and adding one import line, so conflicts are mechanical. A6 (learner + cohort) is the largest (about 3100 production lines, ~7000 test lines) and cannot be safely split without the shared-table decision: split A6 into A6a `learner` (leaving `CohortDataTable` where it is, imported) and A6b `cohort` only if A1 or A6a first moves the two cross-subclass tables to the `data_tables.py` placement of section 2.3.1.

### Option B: by layer (actions first, then views, then tests)

| Spec | Content | Size |
|---|---|---|
| B1 | Split `actions.py` (3772 lines) into per-area `actions.py`/`bulk_actions.py`, plus the data migration | ~3770 prod lines + ~30 string patches |
| B2 | Split `views.py` (3376) and `reporting.py`, `filters.py`, `quick_views.py` into configs/tables/panels/instance views | ~4500 prod lines |
| B3 | Mirror the tests into `tests/panels/...` | ~28000 test lines |

B1 and B2 collide on the same imports (B2 imports B1's new names) so they are serial. B3 is one enormous PR (`test_views.py` + `test_actions.py` = 18000 lines moved), too big to review and conflicting with any other test change. Poor fit for "one PR, one outcome".

### Option C: one mechanical "move" spec per kind of file, using a compatibility shim

| Spec | Content |
|---|---|
| C1 | Create `panels/` with every class copied to its final home; old `views.py`/`actions.py` become `from .panels.x import *` shims; no test moves (tests keep patching the shim) |
| C2 | Move tests area by area and switch their imports/patch strings to the real modules |
| C3 | Delete shims; update `urls.py`, `educator_tags.py`, `qa_helpers`, docs, baselines |

C1 is a single 7000-line diff of moved code with no semantic change; reviewable by `git diff --color-moved` but heavy, and the shim makes the 29 string patches silently patch the wrong namespace (a patch on the shim does not affect the real module). A shim also leaves the persisted-path decision to C1, where the `__module__` of the 11 bulk actions changes at once. Collisions: C1 touches everything, so nothing else can run in parallel; C2's per-area PRs can run in parallel after C1.

### Option D: one PR (baseline, rejected)

About 7100 production lines and 28000 test lines moved in one diff. Not reviewable and would clash with any other work in `educator_interface/`. Listed only to make the cost of the others visible.

### Recommendation

**Option A, with A6 treated as the one risky step.** Reasons: each spec is an area a reviewer can hold in their head, tests move with the code they test (so the mirroring hook stays green PR by PR and the baseline file is edited a few lines at a time), the persisted-path migration is added in the PR that moves the bulk actions (so the migration and the move can be reviewed together and the migration test exercises the real class), and there is no shim at all except the transient re-import in `views.py`/`actions.py`. Suggested merge order: A1, then A2, A3, A4 and A5 in any order, then A6, then A7. If one PR must be smaller, split A6 into a learner PR and a cohort PR after moving the two cross-subclass tables first.

Decisions to put to the human before the specs are written:

1. The `course_staff` name: confirm `course/` and `staff/` as two areas.
2. Bulk actions in `bulk_actions.py` (recommended) vs `data_table_panels.py` (idea).
3. Persisted bulk action path: migration (recommended) vs re-export shim.
4. Add `data_tables.py` per area (required to break the learner/cohort cycle) beyond the three module kinds the idea lists.
5. Are quick views split now or left flat in `quick_views.py` for a later pass.
6. Learner import views (431 lines) go to `learner/import_views.py` vs their own `learner_import/` area.

status: ok
