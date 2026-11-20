# Research: what the codebase gives this spec to touch, reuse or conflict with

Checked against the tree at `e2b5e7cbb` (branch `educator-interface-refactor-2-dashboard-and-audit-log`). All paths are under `freedom_ls/educator_interface/` unless stated. Line numbers are current, not main's. The idea's ranges are stale: `views.py` is now ~2,900 lines, `tests/test_views.py` is ~9,600 lines.

## Headline findings

1. `_attach_target_users` does not exist. The function is **`_attach_people`** (`views.py:772`). The idea's name is wrong.
2. `AuditPeriodFilter` is gone. The framework's `PeriodFilter` (`panel_framework/filters.py`) is built inline in `AuditLogEntryTable.get_filters` (`views.py:881-892`). Only **`AuditActorFilter` (`filters.py:159`) and `AuditActionFilter` (`filters.py:195`)** remain as audit filters. The audit `filters.py` is therefore two classes.
3. `reporting.py` no longer holds `LazyBodyPanel`/`render_region`. They come from `freedom_ls.panel_framework.lazy_panels` (`LOADED_PARAM` at :17, `render_region` :20, `LazyBodyPanel` :30), and `reporting.py:49-53` already imports them from there.
4. The shared fixtures and helpers in `test_views.py` are used by both the moving audit tests and the staying learner and cohort History tests. They need a shared home (see 4.3).
5. Nothing outside the dashboard imports the dashboard names. Nothing outside the audit area imports the audit names, except `LearnerHistoryPanel`, `CohortHistoryPanel` (views.py) and `test_filters.py`/`test_views.py`.

## 1. Dashboard

### 1.1 Where each name lives now (`reporting.py`, all module-level)

| Name | Line |
|---|---|
| `InlineFigures` (frozen dataclass) | 272-277 |
| `CohortFlags` | 280-286 |
| `FlaggedLearnerRow` | 289-297 |
| `CohortProgressRow` | 300-305 |
| `ExcludedCohort` (has `.message`, uses `over_limit_message` and `reports_config.REPORTS_MAX_LEARNERS`) | 308-319 |
| `GatheredFigures` | 322-332 |
| `type CohortGather = tuple[Cohort, CohortProgressData]` | 335 |
| `visible_active_cohorts(request: OrganisationScopedRequest)` | 338-357 |
| `inline_figures` | 360-364 |
| `_gather_visible` | 367-382 |
| `_average_progress` | 385-395 |
| `_flagged_learner_rows` | 398-425 |
| `_cohort_rows` | 428-446 |
| `gathered_figures` | 449-462 |
| `DashboardPanel(LazyBodyPanel)` | 465-505 |
| `LearnerCoursesPanel(Panel)` (stays; starts right after) | 508 |

The whole block is the contiguous `reporting.py:272-505`, ending just before `LearnerCoursesPanel`. It follows `CohortReportStack` (263-269).

`DashboardConfig(OrganisationSectionConfig, BaseViewConfig)` is at `views.py:2482-2486` (`url_name="dashboard"`, `menu_label="Dashboard"`, `icon="home"`, `panel = DashboardPanel`). It sits between `CourseConfig` and `StaffDataTable`.

### 1.2 Who uses these names outside the block

A repo-wide grep (excluding `spec_dd`) found these uses of the dashboard names:

- `views.py:175` imports `DashboardPanel`. `views.py:2486` uses it. `views.py:2728` lists `DashboardConfig` in `interface_config`.
- `tests/test_dashboard.py:27` imports `gathered_figures`.
- Nothing else imports `InlineFigures`, `CohortFlags`, `FlaggedLearnerRow`, `CohortProgressRow`, `ExcludedCohort`, `GatheredFigures`, `CohortGather`, `visible_active_cohorts`, `inline_figures` or `_gather_visible`.
- Same-named hits that are NOT these: `actions.py:1796` and `:1847` (`_cohort_rows`, a method on an action class), `tests/test_filters.py:57` (`_cohort_rows`, a test helper), `panel_framework/tests/test_panels.py:777` and `panel_framework/tests/test_views.py:645` (local test `DashboardConfig`/`_CrumbDashboardConfig`, unrelated).
- No cohort report class, `LearnerCoursesPanel`, template, templatetag or qa_helper uses a dashboard name. The cohort report panels (`CohortNeedsAttentionPanel` :178, `CohortReportBodyPanel` :233, `CohortReportStack` :263) do not use the dashboard dataclasses.
- Dashboard code does NOT use any helper that stays in `reporting.py`. It uses nothing defined above line 272 (`REPORT_POLL_SECONDS`, `DownloadRow`, `_pdf_url`, `REFRESH_PARAM`, `QuizConfusionCard` etc.). No dependency on a stay-behind symbol, so no import back into `reporting.py`.

### 1.3 What the dashboard block imports (the new `panels/dashboard/panels.py` needs)

From the `reporting.py` header (1-77): `dataclasses`, `statistics`, `defaultdict`, `datetime`, `cached_property`, `cast`, `UUID`; `Count`, `Prefetch`, `QuerySet`; `learner_avatars` (`educator_interface.avatars`); `OrganisationScopedRequest` (`panels.common.request`); `can` (`learner_management.capabilities`); `Cohort`, `CohortCourseRegistration`, `CohortMembership`; `cohort_learner_count`, `cohorts_visible_to` (`learner_management.queries`); `LazyBodyPanel` (`panel_framework.lazy_panels`); `reports_config`; `ATTENTION_LIST_MAX`, `AtRiskFlag`, `CohortProgressData`, `over_limit_message` (`reports.report_data`); `cached_cohort_progress_many` (`reports.screen_cache`).

Note `DashboardPanel` reads `OrganisationScopedRequest` as a string cast (`reporting.py:479, 483`) and as a real annotation in `visible_active_cohorts` (:338).

### 1.4 What becomes unused in `reporting.py` after the cut (ruff will flag)

From the header, only the dashboard block uses: `statistics`, `datetime`, `cached_property`, `Count`, `Prefetch`, `QuerySet`, `can`, `CohortCourseRegistration`, `CohortMembership`, `cohort_learner_count`, `cohorts_visible_to`, `reports_config`, `ATTENTION_LIST_MAX`, `AtRiskFlag`, `CohortProgressData`, `over_limit_message`, `cached_cohort_progress_many`. (From grep of single occurrences; verify with ruff.) These stay in use in `reporting.py`: `dataclasses` (87, 201), `defaultdict` and `UUID` (212), `learner_avatars` (192, 249, 502 - the 502 one moves), `OrganisationScopedRequest` (string casts at 141, 526; the real import at :30 stays), `LOADED_PARAM`, `render_region`, `Cohort`, `Learner`.

### 1.5 `views.py` side

- Import to change: `views.py:171-177` (`DashboardPanel` out of the `reporting` import block; `DOWNLOAD_COHORT_REPORT`, `CohortNeedsAttentionPanel`, `CohortReportStack`, `LearnerCoursesPanel` stay).
- Add `from ...panels.dashboard.config import DashboardConfig` and use it in `interface_config` (:2728). `DashboardConfig` leaves `views.py:2482-2487`.
- `BaseViewConfig` (`views.py:245`) is used only by `DashboardConfig` per the grep, so that import goes unused after the move (check).

## 2. Audit log

### 2.1 Current locations (`views.py` unless stated)

| Name | Line |
|---|---|
| `_PERSON_TARGETS` | 764-769 (comment at 764) |
| `_attach_people` (the idea's `_attach_target_users`) | 772-816 |
| `_export_when`, `_export_who`, `_export_run_id` | 819-829 |
| `AuditLogEntryTable(DataTable)` | 832-941 |
| `TargetedAuditLogEntryTable(AuditLogEntryTable)` | 944-959 |
| `_record_export` | 962-994 |
| `HistoryPanel(DataTablePanel)` | 997-1039 |
| `LearnerHistoryPanel(HistoryPanel)` (STAYS) | 1042-1060 |
| `CohortHistoryPanel(HistoryPanel)` (STAYS) | 1695-1700+ (`data_table = TargetedAuditLogEntryTable` at 1697) |
| `OrganisationAuditLogTable(TargetedAuditLogEntryTable)` | 2641-2688 |
| `AuditLogConfig(OrganisationSectionConfig, ListViewConfig)` | 2691-2722 |
| `interface_config` (names both configs at 2728, 2730) | 2725-2731 |

The first block (764-1039) is contiguous and contains no other class. `OrganisationAuditLogTable` and `AuditLogConfig` are one contiguous run (2641-2722) after `StaffConfig`.

`views.py` lines 1360 and 1716 register `LearnerHistoryPanel` and `CohortHistoryPanel` as `"history"` tab children. Those lines are not moved.

### 2.2 Dependencies between the pieces (what the new modules import from each other)

- `data_tables.py` is self-contained apart from `panels.common.request.OrganisationScopedRequest` and the filters module: `AuditLogEntryTable.get_filters` (`views.py:877-893`) uses `AuditActorFilter`, `AuditActionFilter`, and the framework `PeriodFilter`. So `data_tables.py` imports `panels/audit_log/filters.py` (within-area, fine).
- `HistoryPanel` needs `AuditLogEntryTable` (:1001) and `_record_export` (:1032): `data_table_panels.py` imports a private name from `data_tables.py`.
- `AuditLogConfig` needs `AuditLogEntryTable.get_queryset` (:2707), `OrganisationAuditLogTable` (:2696) and `_record_export` (:2715): `config.py` imports the private `_record_export` from `data_tables.py`.
- `OrganisationAuditLogTable` uses `_attach_people`, `AuditLogEntryTable`, `TargetedAuditLogEntryTable`, `SUMMARY_ACTIONS`, `RUN_ROWS_KEPT`, `Window`, `RowNumber`, `F`, `Q`, `Count`, `UUID`, `TableQuery`, `Page`, `Sequence`.
- External imports the moved block needs: `ContentType`, `User`, `Learner`, `StaffMember`, `AuditLogEntry`, `SUMMARY_ACTIONS`, `RUN_ROWS_KEPT`, `record_entry`, `subject_key`, `user_picture_urls` (`educator_interface.avatars`), `timezone`, `cast`, `Model`, `QuerySet`, `HttpRequest`, `DataTable`, `DataTablePanel`, `Column`, `ExportColumn`, `TableQuery`, `PeriodFilter`, `TableFilter`, `OrganisationScopedRequest`, `OrganisationSectionConfig`, `ListViewConfig`.

### 2.3 Who uses each audit name

Grep over the whole repo (excluding `spec_dd`):

- `AuditLogConfig`: `views.py:2691`, `:2730` only.
- `_PERSON_TARGETS`, `_attach_people`, `_export_*`, `_record_export`: only `views.py` (inside the moved block).
- `AuditLogEntryTable`: `views.py` (832, 873, 951, 1001, 2648, 2661, 2707), and **`tests/test_filters.py:34, 676`** (imports it from `views` and uses it in the `when`-parameter test).
- `TargetedAuditLogEntryTable`: `views.py:944, 1697, 2641`. `CohortHistoryPanel` uses it at 1697.
- `HistoryPanel`: `views.py:997, 1042, 1695`. The test tuple at `tests/test_views.py:7489` names the two subclasses, not the base.
- `OrganisationAuditLogTable`: `views.py:2641, 2696`, and **`tests/test_views.py:7478`** (`educator_views.OrganisationAuditLogTable` in `EDUCATOR_TABLES`).
- `AuditActorFilter`, `AuditActionFilter`: defined `filters.py:159, 195`. Used by `views.py:119-120` (imports) and `:879-880`, and by `tests/test_filters.py:19-20` and about 15 call sites at 533-647.
- Docs: `claude_plugins/fls-dev/skills/educator-interface/SKILL.md:40-41` names `AuditActorFilter` and `AuditActionFilter` in `freedom_ls/educator_interface/filters.py`.
- No other app (`qa_helpers`, `learner_interface`, `audit_log`, ...) imports any of them. No template names a Python module path. The audit templates (`partials/audit_log_card.html`, `audit_log_card_targeted.html`, `audit_row_detail.html`, `data-table-cells/audit_who.html`, `audit_what.html`, `audit_target.html`) are referenced by template path only (`views.py:839, 846, 924, 933, 947, 954`) and do not move.

### 2.4 What stays in `filters.py` after the audit filters leave

`LearnerStatusFilter` :41, `LearnerCohortFilter` :63, `LearnerCourseFilter` :90, `may_see_staff_roles` :100, `StaffRoleFilter` :113. Spec 3 (staff) takes the last two; spec 5 (learner) takes the learner filters. `Q`, `TableFilter`, `AuditLogEntry`, `audit_actions`, `audit_actions_by_group` (header lines 9, 13, 14, 36) are used only by the two audit classes and become unused. `User` (`:12`) stays used by `StaffRoleFilter`. `actions.py:48` imports `may_see_staff_roles` from `filters.py`; not touched by this spec.

### 2.5 `views.py` imports that probably go unused after both moves (verify with ruff)

`ContentType` (:14), `SUMMARY_ACTIONS` (:50), `AuditLogEntry` (:51), `RUN_ROWS_KEPT`, `subject_key` (:52; `record_entry` stays: used at :1236), `user_picture_urls` (:110), `Window` and `RowNumber` (:29, :32), `PeriodFilter` (:226), `ExportColumn`? (NOT unused: used at 546-565), `AuditActionFilter`, `AuditActorFilter` (:119-120), `BaseViewConfig` (:245), `DashboardPanel` (:175). `Page`, `TableQuery`, `TableFilter`, `DataTablePanel` stay used elsewhere (364, 377, 610, 1895...). `Q`, `F`, `Count`, `UUID`, `Sequence`, `StaffMember`, `User` are probably used elsewhere in `views.py`; verify.

## 3. References to repoint (consolidated)

Production:
- `views.py:118-126` filters import block: drop `AuditActionFilter`, `AuditActorFilter`.
- `views.py:171-177` reporting import block: drop `DashboardPanel`.
- `views.py`: add imports of `DashboardConfig`, `AuditLogConfig` (config modules), `HistoryPanel` and `TargetedAuditLogEntryTable` (for `LearnerHistoryPanel` :1042 and `CohortHistoryPanel` :1695-1697).
- `interface_config` (`views.py:2725-2731`) keeps naming the two configs through the new imports.
- `reporting.py`: remove 272-505 and the now-unused imports (1.4).
- `filters.py`: remove 159-213 and the unused imports (2.4).
- `educator_interface/templatetags/educator_tags.py:21-24` imports `LearnerCourseSummary`, `learner_course_summaries` from `views`: not a moved name, no change.
- `urls.py`: no change (no imports of moved names).
- `qa_helpers`: no moved name. Only `CourseCohortRegistrationDataTable` and `CourseLearnerRegistrationDataTable` (spec 4's).
- Alpha-order/ruff isort: new `panels.audit_log...` and `panels.dashboard...` imports go among the existing `educator_interface.panels.common...` imports in the `views.py` block (`views.py:148-164`).

Tests:
- `tests/test_dashboard.py:27`: `from freedom_ls.educator_interface.reporting import gathered_figures` becomes `...panels.dashboard.panels`.
- `tests/test_dashboard.py:606-609`: `monkeypatch.setattr("freedom_ls.educator_interface.reporting.learner_avatars", ...)` must become `"freedom_ls.educator_interface.panels.dashboard.panels.learner_avatars"`. `learner_avatars` must therefore be imported at module level in `panels/dashboard/panels.py` (name looked up where `DashboardPanel.get_loaded_context` uses it). A wrong string would fail silently? No: `setattr` on a string path raises if the attribute is absent, but would wrongly succeed if the old module still imports `learner_avatars`, which it does (`reporting.py:21`, used by the cohort panels at :192 and :249). Then the patch applies to the wrong module and the dashboard test still shows a picture. This is the silent-failure trap the idea warns about.
- `tests/test_reporting.py:814` and `:1571` patch `freedom_ls.educator_interface.reporting.learner_avatars`. These are cohort-report tests (not the dashboard), so they stay.
- `tests/test_reporting.py:1483-1493` `_NEW_REPORTING_FILES` lists `reporting.py` plus `templates/educator_interface/panels/dashboard.html` and `dashboard_region.html` (:1485-1486), read as text by `test_reporting_surfaces_never_read_the_stored_progress_percentage` (:1496-1502). After the move `reporting.py` no longer holds the dashboard code. The new `panels/dashboard/panels.py` is not in the list, so the "never read the stored progress percentage" guard stops covering `DashboardPanel`. This test is a dashboard touchpoint inside `test_reporting.py` (the only one: the two grep hits for "dashboard" are these two template names). Decide: add `panels/dashboard/panels.py` to the list (the path is relative to `educator_interface/`), or leave the list and accept the lost coverage.
- `tests/test_filters.py:18-25` and `:33-37`: `AuditActionFilter`, `AuditActorFilter` and `AuditLogEntryTable` imports (the audit tests move, so these imports go with them).
- `tests/test_views.py:65` `from ... import views as educator_views`, then `educator_views.OrganisationAuditLogTable` at **7478** in `EDUCATOR_TABLES` (10 entries, 7468-7479). That tuple is parametrised by three tests (7482, 7496, 7501) and is not audit-only. The entry must be repointed to the new module, not moved. `educator_views.LearnerHistoryPanel` and `educator_views.CohortHistoryPanel` at **7489** stay on `views`; `HistoryPanel` is not named.
- No `mock.patch` string in `test_views.py` names a moved class (the five `educator_interface.views.*` strings at 5000, 5054, 5076, 5080, 5773 patch `own_conversation_with`, `send_message`, `MAX_UPLOAD_BYTES`: not moved).
- `tests/test_views.py:85-89` imports `CohortDataTable`, `CourseDataTable`, `learner_status_badge` from `views`: not moved.
- `tests/interface_walk.py:21` and `tests/invariants/test_config_authorisation.py` use `interface_config` only; no change.
- `tests/invariants/test_answer_key_flag.py:22` asserts `show_answer_key` appears only in `educator_interface/views.py`: unaffected (the moved code does not mention it).
- `tests/invariants/test_bulk_run_scoping.py` walks every production `.py` for unscoped `BulkActionRun` reads: the new modules are scanned and carry none.

Docs and baselines:
- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md:40-41` names the audit filters at `freedom_ls/educator_interface/filters.py`. The idea leaves doc updates to spec 7, but this sentence becomes false the moment the filters move. Decide whether this spec fixes that one sentence (the project rule is that docs are the source of truth).
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md:257` points to `educator_interface/views.py` as an example with `compact = True`: not a moved name.
- `claude_plugins/fls-dev/resources/testing.md:26` names `views.learner_import`: not moved.
- `test_organisation/mirroring_baseline.txt:40`: delete the line `freedom_ls/educator_interface/tests/test_dashboard.py` (under `# educator_interface`). The file is hand-edited and a stale line fails the check (`check_test_mirroring.py`, "stale"). Other educator lines (37-45) stay: those files belong to siblings or the shell.
- `test_organisation/import_baseline.txt` and `import_contracts.toml`: no dashboard or audit test file is baselined; the educator contract (`import_contracts.toml:189-200`) covers `freedom_ls.educator_interface.tests` as a whole package, so new subpackages `tests/panels/dashboard` and `tests/panels/audit_log` are covered by it automatically. Imports like `freedom_ls.reports.tests.helpers` and `freedom_ls.learner_progress.tests.helpers` (`test_dashboard.py:34, 38`) are already accepted today and are unchanged by the move.
- `test_organisation/mirroring_exemptions.txt`: no entry for these files.

## 4. Tests

### 4.1 `tests/test_dashboard.py` (638 lines, whole file moves to `tests/panels/dashboard/test_panels.py`)

Module header: autouse fixture `_empty_cache` (43-47), fixtures `educator` (50-55), `scoped_organisation` (122-133), `shared_learner` (232-247 region); helpers `_dashboard_url` 58, `_load_region` 65, `_tiles` 77, `_members` 86, `_finish_topic` 96, `_course_with_topic` 104, `_registered_cohort` 110, `_grant` 117, `_loaded_query_count` 373, `_flagged_learner` 547, `_dashboard_pictures` 557.

Tests (first line): `test_the_page_renders_the_four_tile_labels_and_two_skeleton_tiles` 137; `test_the_cohorts_tile_link_is_named_by_what_it_counts` 159; `test_the_loaded_fetch_fills_the_two_lazy_tiles` 175; `test_every_figure_covers_only_the_cohorts_the_role_can_see` 199; `test_the_attention_tile_counts_every_flagged_learner_beyond_the_list_cap` 215; `test_a_learner_in_two_cohorts_counts_once_at_the_mean_of_their_completions` 250; `test_attention_rows_order_by_lowest_completion_then_sort_key` 264; `test_cohort_rows_order_by_lowest_mean_then_name_with_an_empty_cohort_last` 286; `test_the_cohort_progress_list_shows_no_list_markers` 316; `test_an_over_limit_cohort_is_counted_inline_and_named_in_a_notice` 335; `test_no_figures_date_is_shown_when_every_cohort_is_over_the_limit` 357; `test_a_warm_load_costs_the_same_queries_however_many_cohorts_there_are` 380; `test_an_organisation_admin_with_no_cohorts_is_invited_to_make_one` 398; `test_a_cohort_role_with_no_active_cohort_is_told_none_are_assigned` 412; `test_an_empty_cohort_loads_with_a_dash_for_average_progress` 426; `test_members_of_a_cohort_registered_for_no_course_are_not_flagged` 441; `test_an_attention_row_has_one_learner_link_and_a_named_quick_view_trigger` 456; `test_an_attention_row_names_each_flagged_cohorts_active_courses_without_an_icon` 481; `test_an_attention_rows_cohort_list_shows_no_list_markers` 517; `test_the_bare_root_redirects_to_the_dashboard` 533; `test_a_flagged_learner_with_a_picture_shows_it_on_the_dashboard` 565; `test_a_flagged_learner_without_a_picture_shows_initials_alone_on_the_dashboard` 581; `test_a_dashboard_row_whose_learner_cannot_be_resolved_shows_initials` 595; `test_more_flagged_learners_with_pictures_cost_no_more_queries_on_the_dashboard` 619.

Notes:
- All of these go through HTTP (the URL fixture), not by calling `DashboardPanel` directly. Only `gathered_figures` is imported and called directly (255, 275, 304).
- **No test targets `DashboardConfig` directly.** `tests/panels/dashboard/test_config.py` would be empty, so per the idea ("a test file is created only alongside the module it mirrors", and the mirroring checker needs a real module) it is not created unless a test is deliberately assigned to it.
- `test_the_bare_root_redirects_to_the_dashboard` (533-544) exercises `interface_root` in `views.py` (shell), not the dashboard panel. Its natural home is the shell test `tests/test_interface_urls.py` (which also asserts the dashboard redirects at 84, 99, 115, 125), not `panels/dashboard/test_panels.py`. Decide.
- `test_dashboard.py` is baselined in `mirroring_baseline.txt:40` (there is no `dashboard.py` module). After the move it mirrors `panels/dashboard/panels.py` and passes.
- `conftest.py` (`tests/conftest.py`) has only `panel_request` (15-32) and `_site_context` (35-40). Fixtures `logged_in_client` (`freedom_ls/conftest.py:259`), `staff_client` (:271), `mock_site_context` (:252), `site_aware_request` (:312) are project-level and reachable from any directory. The dashboard file's own fixtures (`_empty_cache`, `educator`, `scoped_organisation`, `shared_learner`) are file-local and move with it.
- Dashboard tests need no `tests/panels/dashboard/conftest.py`.

### 4.2 `tests/test_reporting.py`

Only dashboard content: the `_NEW_REPORTING_FILES` list entries at 1485-1486 (see section 3). No test of `DashboardPanel`, `gathered_figures` or any figure dataclass. So nothing moves to `test_panels.py` from here, and the idea's open question is answered: none.

### 4.3 `tests/test_views.py` audit slices

The file's top-level helpers are shared across the whole module (`_get_document` 160, `_interface_url` 153, `_learner_page` 1724, `_region_text` 1731, `QUERY_BUDGET` 145). The audit slices use a cluster of helpers that is also used by learner and cohort History tests that stay behind:

| Helper | Defined | Used by (staying) |
|---|---|---|
| `_history_entry` | 2030 | learner History 2071-2562, 4445-ish, 9250 |
| `_visible_text` | 2042 | learner History, `_audit_row_cells` (4486) |
| `_entry_rows` | 2050 | `_history_rows` 2066 and `_audit_log_rows` 4183 |
| `_row_details` | 2058 | learner History 2092-2113, audit 4286 |
| `_history_rows` | 2066 | learner and cohort History (3953, 3979-3981, 4053, 4075, 4174, 7759) |
| `_export_audit_csv` | 2364 | learner history export 2386-2561, cohort history export 7725-7753 |
| `_audit_log_url` | 4179 | learner `test_an_export_entry_shows_on_the_audit_log_and_not_on_the_learner_history` (2536), cohort history export (7757) |
| `_audit_log_rows` | 4183 | same two tests |
| `_record_run` | 4389 | `test_a_bulk_runs_entry_shows_on_the_learners_history_tab` (4441) |
| `_cohort_entry`, `_cohort_history_url` | 7682, 7694 | cohort history export tests 7714-7777, 7929-7960 |
| `_audit_log_export` | 7700 | audit only (7805-7997) |
| `_audit_log_document`, `_audit_row_cells`, `_avatar_slot` | 4506, 4486, 4497 | audit only (4513-4701, 7795) |

There is no conftest-level or `helpers.py` home for these. `tests/helpers.py` (shared helpers) already holds `get_interface_page`, `organisation_admin_viewer`, `page_after_adding_rows`, `profile_picture_sources`, `course_per_reach_row`, `COURSE_REACH_ROWS`, `_any_request`, `_educator_request`. The spec must decide where the shared History/audit helper cluster goes. `tests/helpers.py` or a new `tests/panels/audit_log/helpers.py` are the options. A learner or cohort spec importing from another area's test dir would cross areas.

Candidate audit tests that move (current lines, by module they exercise):

**Organisation Audit log page and config (`AuditLogConfig`, `OrganisationAuditLogTable`):**
- 4188 `test_the_audit_log_shows_when_as_day_month_year_and_24_hour_time`; 4202 `..._lists_only_the_request_organisations_entries`; 4216 `test_a_site_admin_sees_each_organisations_own_entries`; 4232 `test_an_admin_of_another_organisation_gets_a_404_on_the_audit_log`; 4247 `test_a_cohort_admin_gets_a_404_on_the_audit_log_and_no_menu_entry`; 4271 target column; 4290 toggle named by label; 4308 empty state; 4318 escapes; 4332 filters narrow by who/what/when; 4360 tampered filter; 4374 filtered empty state; 4414 bulk run is one row listing fifty entries; 4452 same run id in another org; 4472 three runs query budget; 4513 system actor icon; 4528 deleted actor; 4548 person target avatar colour; 4590 learners list vs audit log avatar colours (cross-area: reads the learners list too); 4625 deleted learner target; 4650 cohort target plain text; 4666 chip initials from email; 4684 label with markup escaped; 4701 three runs of learner entries query budget. Range 4179-4722.
- 7645-7679 `test_the_audit_log_what_filter_is_a_grouped_checklist_with_one_apply` (the `AuditActionFilter` rendered through the page).
- 9083-9240 audit-log picture tests (6 tests, via `get_interface_page`) and 9260-9285 `_add_audit_entries_with_pictures` plus `test_more_audit_entries_with_pictures_cost_no_more_queries`.
- Config-level: 4232, 4247 and 7929 `test_a_cohort_role_gets_a_404_on_the_exports_it_may_not_read` (covers cohort history export too).

**Audit export (`AuditLogConfig.get_export_*`, `before_export`, `_record_export`):** 7791 toolbar offers CSV; 7805 who filter; 7819 what filter; 7836 when filter; 7853 named for the org; 7865 summary plus per-object entries; 7879 what filter drops summary; 7894 leaves out another org; 7907 leaves out another site; 7929 role 404; 7967 records scope and filters; 7990 omits its own entry.

**`HistoryPanel` / History tab tests (mixed ownership):** the learner History tests 2017-2570 (`_history_entry`, `_learner_page`) and cohort History tests 3945-4178 and 7682-7790 and 7949-7966 drive `HistoryPanel` through `LearnerHistoryPanel` or `CohortHistoryPanel`. By the idea ("`LearnerHistoryPanel` and `CohortHistoryPanel` are not moved... belong to the learner and cohort areas") these belong to specs 5 and 6, not to `test_data_table_panels.py`. The only test touching `HistoryPanel`'s shared contract is `test_a_history_panel_says_what_will_be_recorded` (7488-7493), which parametrises the two subclasses. No test of `HistoryPanel` as such exists today, so `tests/panels/audit_log/test_data_table_panels.py` has nothing to hold unless the spec assigns tests. Flag it.
- Also related: 3614 `test_the_cohort_history_panel_refreshes_on_member_changes` (cohort area).

The idea's "about 4044-4570 and 7317-7680" no longer matches: the audit slice is now 4179-4722, 7645-7679, 7791-8003, and 9083-9285. 4044-4178 is cohort History (card summaries). Move by name, not range.

`test_the_first_use_message_is_a_sentence` and its two siblings (7482-7523) parametrise `EDUCATOR_TABLES` and stay in `test_views.py` (only the list entry is repointed).

### 4.4 `tests/test_filters.py` (audit slice)

The idea's "from `audit_request` at ~557 to the end of the file" is stale; the file now ends with `test_learner_course_filter_offers_a_course_only_when_it_reaches_the_organisation` (686).
- Fixture `audit_request` 509-515 and helper `_entry_pks` 518-520.
- Tests: 524 `test_actor_choices_are_system_then_this_organisations_actors_by_name`; 543 `test_an_actor_filter_value_outside_this_organisation_is_dropped`; 557 `test_the_actor_filter_selects_one_value_at_a_time`; 562 `test_two_actor_values_in_the_query_string_keep_only_the_first`; 575 `test_system_matches_entries_with_no_actor_and_no_stored_name`; 586 `test_a_user_value_matches_only_that_actors_entries`; 597 `test_the_action_filter_narrows_by_code`; 606 `test_the_action_choices_are_the_registered_actions_with_labels`; 618 `test_the_action_choices_include_a_downstream_extra_action`; 628 `test_the_action_choices_are_the_grouped_under_the_fixed_headings_in_order` (name at 627-648 area; ends at `AuditActionFilter.widget == "grouped_checklist"` 647).
- 669-683 `test_the_audit_log_filters_on_the_when_parameter` exercises `AuditLogEntryTable.parse_query/filter_queryset` with the `PeriodFilter` (not an audit filter class). It belongs to `tests/panels/audit_log/test_data_tables.py`, not `test_filters.py`.
- Interleaved non-audit test that must NOT move: 651 `test_the_cohort_table_widens_to_inactive_cohorts_on_the_inactive_parameter` (between 647 and 669).
- `pytestmark = pytest.mark.usefixtures("_site_context")` (:51) applies file-wide; the new `tests/panels/audit_log/test_filters.py` needs the same (`_site_context` is in `tests/conftest.py:35`, reachable from subdirs).
- Imports that become unused in `test_filters.py` after the move: `AuditLogEntryFactory`, `AuditLogEntry`, `AuditActionFilter`, `AuditActorFilter`, `AuditLogEntryTable` (:33-37), `time_machine`, `UTC`/`datetime`/`timedelta`/`QueryDict`? (`QueryDict` still used at 658), `UserFactory` (used elsewhere? 14; verify), `TableFilter` (:48; used by `audit` only? verify).
- Spec 3 (staff) also cuts `test_filters.py` (its `StaffRoleFilter` tests 288-505 and `staff_request` fixture 299). Mechanical conflict on the import block (:18-25) and `pytestmark`.

### 4.5 Shell-level tests

- `tests/test_sidebar.py:73, 78` assert menu labels "Dashboard" and "Audit log". `tests/test_interface_urls.py:84, 99, 115, 125` assert the URL path string `"dashboard"` in redirects. Neither imports `DashboardConfig`/`AuditLogConfig` by name. They stay, and only break if the config URL names or labels change (they don't). `tests/invariants/test_config_authorisation.py` and `tests/interface_walk.py` walk `interface_config`, so they exercise both configs by enumeration with no per-name reference. `tests/invariants/test_permission_matrix.py:86, 178, 470` names the `view_auditlogentry` capability only.
- `tests/playwright/test_audit_log_flow.py` and `tests/playwright/test_dashboard_attention_layout.py` stay where they are (playwright is skipped by the mirroring checker, `check_test_mirroring.py:96-97`).

## 5. Current state of `panels/` and `tests/panels/` (spec 1's output)

- `panels/__init__.py` is empty. `panels/common/` holds `__init__.py` (empty or near-empty), `actions.py`, `badges.py`, `bulk_actions.py`, `filters.py` (`VisibleCourseFilter`), `ids.py` (`uuid_or_404`), `report.py` (`flag_badge`, `progress_status_badge`, `report_over_limit_message`), `request.py` (`OrganisationScopedRequest` :34, `OrganisationSectionConfig` :59, `LAST_ORGANISATION_SESSION_KEY`), `tables.py` (`_active_status_column`, `_interface_link`, `_learner_column`, `_registration_columns`). There is no `panels/audit_log/` or `panels/dashboard/` yet.
- `tests/panels/__init__.py` and `tests/panels/common/__init__.py` plus `test_bulk_actions.py`, `test_request.py`, `test_badges.py`, `test_filters.py`, `test_report.py`. Convention: `tests/panels/<area>/test_<module>.py` mirrors `panels/<area>/<module>.py`. Each directory has an `__init__.py`.
- No README, docs or fls-dev text describes the layout (grep for `tests/panels` and `panels/common` in `docs/`, `claude_plugins/`, `pyproject.toml`, `test_organisation/` returned nothing). The layout rules live only in `spec_dd/1. next/roadmap.md:87-89`.
- Dashboard code needs from common: `OrganisationScopedRequest` (`panels.common.request`) and nothing else. Audit code needs: `OrganisationScopedRequest`, `OrganisationSectionConfig`. Neither imports `panels/common/tables`, `filters`, `badges` or `report`.
- Mirroring checker (`claude_plugins/django-stack/scripts/check_test_mirroring.py`): a collected test file (`test_*.py`, `*_tests.py`, `tests.py`) under `<app>/tests/` conforms if `<app>/<sub...>/<name>.py` or `<app>/<sub...>/<name>/__init__.py` exists, where `sub` is the path between `tests/` and the file (lines 64-84). `tests/panels/dashboard/test_panels.py` requires `panels/dashboard/panels.py`, and `tests/panels/audit_log/test_data_tables.py` requires `panels/audit_log/data_tables.py`, and so on, one by one. Playwright tests are skipped (:96-97). A baseline line that names a conforming or absent file is "stale" and fails (`THREE_WAYS_OUT` message :38-42). Because `test_dashboard.py` currently violates (no `dashboard.py`), it is baselined; once moved the line must go in the same commit.
- Corollary: `tests/test_filters.py` mirrors `filters.py`, `tests/test_reporting.py` mirrors `reporting.py` and `tests/test_views.py` mirrors `views.py`, all of which stay, so none of those three needs a baseline line.
- `test_dashboard.py` is imported by nothing (no cross imports from other test files).

## 6. Collisions with parallel and other specs

Specs 3 (staff) and 4 (course) are only ideas in `spec_dd/1. next/` (no worktree yet in `2. in progress/`). Nothing is in progress for them. Their ideas say:

- Spec 3 (`.../educator-interface-refactor-3-staff/idea.md`): moves `StaffConfig` (`views.py` 2534-2591 on main), `StaffDataTable`, staff actions, `StaffRoleFilter` and `may_see_staff_roles` (`filters.py`), `StaffQuickView`, and the staff slice of `test_views.py` (main's 2811-3740) and `test_filters.py`'s staff tests. It repoints "`interface_config` in the shell `views.py` imports `StaffConfig` from its new module".
- Spec 4 (`.../educator-interface-refactor-4-course/idea.md`): moves `CourseConfig` (`views.py` 2416-2435 on main) and the course slices of `test_views.py` and the two `qa_helpers` commands.

Collisions with this spec (all mechanical, same files):
- `views.py` import block (118-126 filters, 171-177 reporting, 148-164 panels.common) and the `interface_config` list at 2725-2731 (one line each for `DashboardConfig`, `StaffConfig`, `AuditLogConfig`, `CourseConfig`; the list at 2728 and 2730 is edited by all three specs).
- `views.py` adjacent regions: `DashboardConfig` (2482) sits right above `StaffDataTable` (2489), and `CourseConfig` ends just above `DashboardConfig`; `OrganisationAuditLogTable` begins immediately after `StaffConfig`. Cutting neighbouring ranges makes adjacent-hunk conflicts likely when spec 3 or 4 rebases.
- `filters.py`: spec 3 cuts 100-157 and this spec cuts 159-213; adjacent hunks and the import block (lines 9-37).
- `tests/test_filters.py`: spec 3's staff tests (288-505) are adjacent to this spec's audit tests (509-648); the import block and `pytestmark` also collide.
- `tests/test_views.py`: import block (:65-89, :85-89), and the shared helpers listed in 4.3. A helper `_staff_document` or `_grant` region is spec 3's.
- `educator-interface-refactor-5-learner` (`.../5-learner/idea.md`) is blocked on this spec and re-imports `HistoryPanel`/`TargetedAuditLogEntryTable` from the new modules; the shared helper cluster in 4.3 is also its input, since learner History tests move in spec 5. `-6-cohort` the same for cohort History tests. A stable shared-helper location matters to both.

Other in-progress specs (`spec_dd/2. in progress/`): `extract_panels_framework-4-template-contract` mentions `educator_interface` only to say it does not change (idea.md:76, 85); `learner-profile-use-panels-framework-2-editable-list-panel`, `-3-account-page` (mentions educator_interface in a research file only), `misure-of-admonitions` and `sacaa-compliance-1-served-paper-record` do not touch `views.py`, `reporting.py`, `filters.py`, `test_dashboard.py`, `test_views.py` or `test_filters.py` per grep. The roadmap notes (:85) also warn that `deadlines-6-educator-management`, `deadlines-7-educator-at-risk`, `corporate-job-course-recommendations-4-educator-interface-screens` and `audit-log-coverage-gaps` should land after the effort or rebase onto it. `audit-log-coverage-gaps` in particular will touch the audit tables.
- `extract_panels_framework-5-package-and-install` will change the `freedom_ls.panel_framework` import prefix; every new module's `panel_framework` imports then change. That is future and out of scope here.

## 7. Database and registration facts to confirm in the spec

- None of the moved classes is decorated with `@register_bulk_action`. The only registered classes in `educator_interface` live in `actions.py` and are not touched. No `BulkActionRun.action_path` change, no migration (matches the idea).
- Class paths do appear in two other places that are worth checking when writing the spec: Django template tags and panel `children` registries refer to classes by object, not by dotted-path string, so no string path changes. The only dotted-path strings found are the monkeypatch strings in section 3.

status: ok
