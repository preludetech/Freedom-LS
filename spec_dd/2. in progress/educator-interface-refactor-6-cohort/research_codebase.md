# Research: codebase (educator-interface-refactor-6-cohort)

Verified against the worktree at HEAD `856f196d6` (spec 5 is merged). All paths are under `freedom_ls/educator_interface/` unless noted. The effort-level line ranges are stale: `views.py`, `actions.py` and `reporting.py` have shrunk a lot (spec 5 and earlier moved most of them), so the ranges below replace the idea's.

## 1. Symbols that move: current location and dependencies

### `views.py` (about 720 lines now; the idea's `V:` ranges are obsolete)

| Symbol | Current lines | Notes |
|---|---|---|
| `CohortDetailsPanel` | 141-154 | uses `cohort_counts`, `active_status_badge` (common.badges), `COHORT_CHANGED` |
| `CohortCourseRegistrationDataTable` | 157-184 | uses `_course_title_column`, `_registration_columns` (common.tables), `cohorts_visible_to`, `OrganisationScopedRequest`. Goes into the existing `panels/cohort/data_tables.py` (its `__all__` lists only `CohortDataTable` and `LearnerCohortDataTable`, so add it). |
| `CohortLearnersPanel` | 187-222 | uses `CohortLearnerDataTable` (panels.learner.data_tables), `AddExistingLearnersAction` and `AddLearnerToCohortAction` (flat `actions.py`, moving), `ImportLearnersAction`, `RemoveFromCohortAction`, `MoveToCohortAction` (panels.learner.actions) |
| `CohortCoursesPanel` | 225-240 | uses `CohortCourseRegistrationDataTable`, `RegisterCohortForCourseAction`, `DeactivateCohortRegistrationAction` |
| `CourseCompletion` (dataclass) | 243-260 | |
| `CohortCourseCompletionPanel` | 263-315 | template `educator_interface/panels/cohort_course_completion.html` |
| `CohortNamePanel` | 318-345 | uses `EditCohortAction`, `CohortForm` (flat `forms.py`, stays) |
| `CohortStaffPanel` | 348-384 | uses `AddStaffMemberToCohortAction`, `ChangeRoleAction`, `RemoveStaffFromCohortAction`, `roles_grantable_on` (panels.staff.actions), `cohort_educators`, `ASSIGN_COHORT_VIEWER` |
| `CohortStatusPanel` | 387-410 | uses `cohort_state_actions`, `DeleteEmptyCohortAction`, `cohort_not_empty_sentence`, `interface_path` (`paths.py`) |
| `CohortSettingsStack` | 413-423 | |
| `CohortOverviewStack` | 426-433 | uses `CohortNeedsAttentionPanel` (from `reporting.py`) |
| `CohortHistoryPanel` | 436-446 | uses `HistoryPanel` (panels.audit_log.data_table_panels), `TargetedAuditLogEntryTable` (panels.audit_log.data_tables) |
| `CohortTabSet` | 449-458 | uses `CohortReportStack` |
| `CohortInstanceView` | 461-485 | uses `inactive_badge`, `EditCohortAction`, `cohort_state_actions` |
| `CreateCohortAction` | 488-519 | uses `CohortForm`, `record_cohort_entry`, `interface_path`, `OrganisationScopedRequest` |
| `CohortConfig` | 522-549 | uses `CohortDataTable`, `CohortInstanceView`, `CohortQuickView`, `bulk_actions_for_table`, `OrganisationScopeDenied` (exceptions.py), `OrganisationSectionConfig` |
| `_scoped_cohort` | 615-620 | calls `_attach_organisation` (views.py 601) and `CohortConfig.get_instance_view` |
| `cohort_report_download` | 623-635 | uses `DOWNLOAD_COHORT_REPORT` (reporting.py), `GeneratedReport`, `report_file_response`, `can` |

What stays in `views.py`: `interface_config` (552-558: `[DashboardConfig, CohortConfig, LearnerConfig, CourseConfig]` and `[StaffConfig, AuditLogConfig]`), `interface_root`, `_resolve_organisation`, `_attach_organisation`, `scope_request`, `standalone_page_context`, `interface`, and the `# TODO` comment block at lines 130-139. That TODO block must not be deleted. It is not cohort-specific, so it stays in `views.py` for spec 7 to deal with.

`views.py` lines 23-32 import the cohort actions from flat `actions`. Lines 80-87 import `CohortQuickView` and the reporting names. After the move, `views.py` imports `CohortConfig` from `panels.cohort.config`. Most of its other imports then become dead and must be trimmed (spec 7 owns the full trim, but the cohort-only imports this spec orphans have to go in this PR or ruff will fail).

### `actions.py` (665 lines; every remaining symbol is cohort)

The whole module is the cohort area now, so `actions.py` is emptied and could be deleted. Spec 7 owns deleting emptied flat modules, so leave an empty or docstring-only file only if the spec says so. `test_reason_mixin.py` imports it (see section 5).

| Symbol | Lines |
|---|---|
| `cohort_not_empty_sentence` | 92-119 |
| `RequiresActiveCohortMixin` | 122-150 |
| `EditCohortAction` | 153-185 |
| `CohortStateAction` | 188-219 |
| `DeactivateCohortAction` | 222-242 |
| `ReactivateCohortAction` | 245-263 |
| `DeleteEmptyCohortAction` | 266-304 |
| `RegisterCohortForCourseAction` | 307-336 |
| `KEEPING_NAMES_SHOWN` | 339 |
| `DeactivateCohortRegistrationAction` | 342-397 |
| `AddExistingLearnersAction` | 400-449 |
| `AddLearnerToCohortAction` | 452-462 |
| `cohort_state_actions` | 465-467 |
| `CohortBulkAction` | 470-490 |
| `CohortCourseBulkAction` | 493-534 |
| `RegisterCohortForCourseBulkAction` (registered) | 537-556 |
| `DeactivateCohortRegistrationBulkAction` (registered) | 559-597 |
| `CohortStateBulkAction` | 600-609 |
| `DeactivateCohortsBulkAction` (registered) | 612-639 |
| `ReactivateCohortsBulkAction` (registered) | 642-664 |

`inactive_cohort_response` is not in `actions.py` any more. Spec 5 moved it to `panels/common/actions.py:85`, and `panels/learner/actions.py` imports it from there. The idea lists it under `panels/cohort/actions.py`, which is wrong now: it stays in `panels/common/actions.py`, and `actions.py` already imports it from there.

Dependencies of `actions.py`:
- `panels.common.actions`: `EducatorReasonMixin`, `_empty_message`, `_register_title`, `inactive_cohort_response`.
- `panels.common.bulk_actions`: `CoursePickerMixin`, `EducatorBulkAction`.
- `panels.common.request.OrganisationScopedRequest`.
- `panels.learner.actions`: `AddLearnerAction`, `_membership_changed_response`.
- Flat `forms.py`: `CohortCourseRegistrationForm`, `LearnerPickerForm`.
- Framework: `panel_framework.actions`, `panel_framework.bulk_actions` (`BulkOutcome`, `register_bulk_action`), `panel_framework.context`.
- Domain: `learner_management.{capabilities,learner_actions,models,queries,utils}`, `role_based_permissions.utils.delete_role_rows_for`.

### `reporting.py` (245 lines; entirely cohort now)

`LearnerCoursesPanel` and the dashboard half are already gone, so the whole module moves to `panels/cohort/report_panels.py`.

| Symbol | Lines |
|---|---|
| `REPORT_POLL_SECONDS` | 55 |
| `DOWNLOAD_COHORT_REPORT` | 56 |
| `DOWNLOADS_LISTED` | 59 |
| `DownloadRow` | 62-68 |
| `GenerateReportAction` | 71-88 |
| `CohortReportDownloadsPanel` | 91-141 |
| `_pdf_url` | 144-150 |
| `CohortNeedsAttentionPanel` | 153-170 |
| `REFRESH_PARAM` | 173 |
| `QuizConfusionCard` | 176-182 |
| `_quiz_confusions` | 185-205 |
| `CohortReportBodyPanel` | 208-235 |
| `CohortReportStack` | 238-244 |

Dependencies:
- `avatars.learner_avatars` (flat `avatars.py`, stays).
- `events.COHORT_CHANGED`.
- `panels.common.report.report_over_limit_message` (already in `panels/common/report.py`, along with `PROGRESS_STATUS_TONES`, `progress_status_badge` and `flag_badge`).
- `panels.common.request.OrganisationScopedRequest`.
- `panel_framework.lazy_panels` (`LOADED_PARAM`, `LazyBodyPanel`, `render_region`).
- `reports.*`.

`DownloadRow`, `REPORT_POLL_SECONDS`, `DOWNLOADS_LISTED` and `REFRESH_PARAM` are module constants and helpers the idea does not list. They are cohort-only, so they travel with the module. Its `reverse("educator_interface:cohort_report_download")` uses a URL name, which does not change.

`DOWNLOAD_COHORT_REPORT` is imported by `views.py` (cohort_report_download). `tests/invariants/test_permission_matrix.py` redefines its own copy as a string at line 127 and does not import it.

### `quick_views.py` (46 lines; `CohortQuickView` only)

`CohortQuickView` is at lines 28-45. It imports `COHORT_CHANGED`, `active_status_badge` (common.badges), `OrganisationScopedRequest` (common.request) and `cohort_learner_count`.

`visible_registrations_with_progress` is gone from this file. Spec 5 moved it to `panels/learner/quick_view.py` (see the spec 5 upgrade notes). The idea's "stays where it is and is imported" does not apply, because `CohortQuickView` does not use it. The module is emptied by the move.

## 2. What already exists

`panels/cohort/`:
- `__init__.py` (empty) and `data_tables.py`.
- `data_tables.py` holds `CohortDataTable` and `LearnerCohortDataTable`, with `__all__ = ["CohortDataTable", "LearnerCohortDataTable"]`. This spec adds `CohortCourseRegistrationDataTable` there.
- Its imports already include `CohortCourseRegistration`, `OrganisationScopedRequest` and `panels.common.tables._active_status_column` and `_interface_link`. `CohortCourseRegistrationDataTable` additionally needs `_course_title_column` and `_registration_columns` from `panels.common.tables`.

`panels/common/`:
- `__init__.py`, `actions.py`, `badges.py`, `bulk_actions.py`, `filters.py`, `ids.py`, `report.py`, `request.py`, `tables.py`.
- `common/actions.py` has `EducatorReasonMixin`, `_empty_message`, `_picker_title`, `_register_title`, `inactive_cohort_response`, `_uuid_from` and `_action_params`.
- `common/badges.py` has `active_status_badge`, `inactive_badge`, `learner_status_badge` and `_LEARNER_STATUS_TONES`.
- `common/bulk_actions.py` has `EducatorBulkAction` (line 34) and `CoursePickerMixin` (line 71).
- `common/report.py` has `PROGRESS_STATUS_TONES`, `progress_status_badge`, `flag_badge` and `report_over_limit_message`.
- `common/request.py` has `LAST_ORGANISATION_SESSION_KEY`, `OrganisationScopedRequest` and `OrganisationSectionConfig`.

The other panel packages exist: `audit_log`, `course`, `dashboard`, `learner` and `staff`, each with `config.py` and friends. `panels/learner/` has `actions`, `bulk_actions`, `config`, `data_table_panels`, `data_tables`, `filters`, `import_views`, `instance_view`, `messages`, `panels` and `quick_view`.

Convention from the finished packages:
- The config class is in `panels/<area>/config.py`.
- The file is `instance_view.py`, a single file.
- `data_table_panels.py` holds the `DataTablePanel` subclasses.
- `panels.py` holds the other panels.
- `quick_view.py` is singular.
- The tests mirror this in `tests/panels/<area>/test_<module>.py`.
- `learner/import_views.py` is the precedent for a view function that lives outside `views.py` and imports `_attach_organisation` and `scope_request` from `freedom_ls.educator_interface.views`. `views.py` does not import `import_views`, so there is no cycle. `urls.py` imports `import_views` directly. `panels/cohort/report_download.py` can follow the same pattern.

Tests that exist for cohort: `tests/panels/cohort/__init__.py` and `tests/panels/cohort/test_data_tables.py` (the cohort table tests from spec 5; it has a `_site_context` autouse-style fixture usage via `pytest.mark.usefixtures("_site_context")`).

## 3. `_scoped_cohort` callers

`_scoped_cohort` is defined at `views.py:615`. Its only caller is `cohort_report_download` (`views.py:627`). Nothing else in the repo references it (grep over `freedom_ls/`, docs, plugins: no other hits). It moves with `cohort_report_download` into `panels/cohort/report_download.py`.

It depends on `_attach_organisation` (stays in `views.py`; `_attach_organisation` is also used by `interface_root`, `scope_request` and `learner/import_views.py`), so `report_download.py` imports `_attach_organisation` from `freedom_ls.educator_interface.views`, as `import_views.py` does. It also imports `CohortConfig` from `panels.cohort.config`. `views.py` imports `panels.cohort.config` (for `interface_config`), and `config.py` does not import `report_download.py` or `views.py`, so there is no cycle.

## 4. Migrations

- Highest existing: `migrations/0002_move_learner_bulk_runs.py`. The next number is `0003`, for example `0003_move_cohort_bulk_runs.py`. The only other file is `0001_rename_unregister_bulk_runs.py`.
- Spec 5's `0002` has these parts:
  - `_OLD = "freedom_ls.educator_interface.actions."` and `_NEW = "freedom_ls.educator_interface.panels.learner.bulk_actions."`.
  - `MOVES` is a list of `(old, new)` built by a comprehension over class names.
  - `_repoint(apps, pairs)` fetches `apps.get_model("freedom_ls_panel_framework", "BulkActionRun")` and runs `.objects.filter(action_path=old).update(action_path=new)` per pair. The filter matches whole paths only, and the historical manager has no site filter, so every site's runs are repointed.
  - `forwards` calls `_repoint(apps, MOVES)`. `backwards` calls `_repoint(apps, [(new, old) for old, new in MOVES])`.
  - `Migration.dependencies = [("freedom_ls_educator_interface", "0001_rename_unregister_bulk_runs")]` and `operations = [migrations.RunPython(forwards, backwards)]`.
  - The `0003` migration's dependency would be `("freedom_ls_educator_interface", "0002_move_learner_bulk_runs")`.
- App label is `freedom_ls_educator_interface`. The runs live in app `freedom_ls_panel_framework`, model `BulkActionRun` (historical state `0001_initial`).
- Test: `tests/migrations/test_0002_move_learner_bulk_runs.py` (206 lines).
  - Constants: `APP`, `RUNS`, `BEFORE = [(APP, "0001...")]`, `AFTER = [(APP, "0002...")]`, `OLD`, `NEW` and a `LEARNER_ACTIONS` list of `(class, action_name)`.
  - Fixture `migrated_back_to_the_leaf` (yield, then `executor.migrate(leaf_nodes())`).
  - Helpers `_historical_model`, `_migrate(target)`, `_make_run(model, site, user, path, name)` and `_stored(model, pk)`.
  - Every test is `@pytest.mark.django_db(transaction=True)` and takes `mock_site_context`.
  - Test groups: parametrized forward path per class; action_name preserved; reverse restores the old path; "another action left alone" (paths include `...actions.DeactivateCohortsBulkAction` and `...actions.NoSuchBulkAction`); "already on a new path left alone"; and a non-DB `test_each_new_path_imports_a_recorded_bulk_action` using `import_string` and `issubclass(..., RecordedBulkAction)`.
  - For `0003`: `BEFORE` is `0002`, `AFTER` is `0003`.
- Existing assertion that will need editing: `test_0002_move_learner_bulk_runs.py:163` uses `freedom_ls.educator_interface.actions.DeactivateCohortsBulkAction` as the "other action left alone" fixture. This stays valid for `0002` (the migration at its own number does not touch it), but `0002`'s test runs against the leaf schema after `migrated_back_to_the_leaf`, and the path is still just a string, so no edit is needed. `test_0001_rename_unregister_bulk_runs.py` and `0001` mention `...actions.DeactivateCohortRegistrationBulkAction`, which is a cohort class, and that is also a string only. Do not edit either test.
- Registered cohort bulk action classes today (`@register_bulk_action` in flat `actions.py`; the dotted path is `freedom_ls.educator_interface.actions.<Class>`):

| Class | Line | `action_name` | `table_key` |
|---|---|---|---|
| `RegisterCohortForCourseBulkAction` | 538 | `register` | `cohorts` |
| `DeactivateCohortRegistrationBulkAction` | 560 | `deactivate_cohort_registration` | `cohorts` |
| `DeactivateCohortsBulkAction` | 613 | `deactivate` | `cohorts` |
| `ReactivateCohortsBulkAction` | 643 | `reactivate` | `cohorts` |

  The unregistered bases `CohortBulkAction`, `CohortCourseBulkAction` and `CohortStateBulkAction` are never stored. The new path prefix is `freedom_ls.educator_interface.panels.cohort.bulk_actions.`.
- Upgrade notes: spec 5's `upgrade_notes.md` has the front matter `requires_migrations: true`, `requires_template_review: false`, `changed_template_paths: []`, `requires_settings_change: false`, and so on. It has a `## Breaking changes` section that lists moves as "From X to Y: names", a `### Stored bulk action paths` subsection, and `## Manual steps`. Spec 6's notes follow the same pattern. A note about stale `mock.patch` targets is in its manual steps.

## 5. Every reference to a moving name (non-spec_dd)

Imports from the flat modules:
- `views.py:23-32`: `AddExistingLearnersAction`, `AddLearnerToCohortAction`, `DeactivateCohortRegistrationAction`, `DeleteEmptyCohortAction`, `EditCohortAction`, `RegisterCohortForCourseAction`, `cohort_not_empty_sentence`, `cohort_state_actions` from `actions`. All are only used by cohort code that moves.
- `views.py:80-82`: `CohortQuickView` from `quick_views`.
- `views.py:83-87`: `DOWNLOAD_COHORT_REPORT`, `CohortNeedsAttentionPanel`, `CohortReportStack` from `reporting`.
- `urls.py:5` (`from . import views`) and `urls.py:13-17`: `views.cohort_report_download`, name `cohort_report_download`. The spec only changes this one line (import and reference); `urls.py:3` imports `import_views` from `panels.learner`.
- `tests/interface_walk.py:21`: only `interface_config` from `views` (stays). It does not import `CohortConfig`, so it needs no change unless `views.py` stops exporting `interface_config` (it does not).
- `tests/invariants/test_organisation_isolation.py:37`: `from freedom_ls.educator_interface.views import CohortCourseRegistrationDataTable`; used at line 612 (a parametrized list). Repoint to `panels.cohort.data_tables`.
- `tests/invariants/test_reason_mixin.py:13`: `from freedom_ls.educator_interface import actions`; `_reason_actions()` iterates `(actions, learner_module, staff_actions)` and asserts `len(found) == 9`. After the move, `actions` becomes `panels.cohort.actions` (the `EducatorReasonMixin` users there are `DeactivateCohortAction`, `DeleteEmptyCohortAction` and `DeactivateCohortRegistrationAction`). The count must stay 9. `inspect.getmembers` also picks up classes imported into the module, so the count depends on what `panels/cohort/actions.py` imports at top level. Run the test; do not trust grep.
- `tests/panels/staff/test_actions.py:40`: `from freedom_ls.educator_interface.views import CohortConfig` (used at 2678).
- `tests/panels/learner/test_bulk_actions.py:22,497`: `from freedom_ls.educator_interface import actions as actions_module` with `mocker.spy(actions_module, "can")` at line 497. This is the silent-break case. The spy targets `can` looked up in the flat `actions` module, for a learner bulk-deactivate run. It currently spies on the wrong module (learner bulk actions do not live in flat `actions`), so it is likely already vacuous, since `can.call_count <= 2` passes trivially. After the move the import `actions as actions_module` fails outright because `actions.py` is gone or empty. The spec has to decide: repoint to `panels.learner.bulk_actions` (where learner `can` calls happen, if any) or `panels.common.bulk_actions`, and check the test still bites. This is a spec-5 leftover that this PR cannot leave broken.
- `tests/test_actions.py:28-34`: `CohortCourseBulkAction`, `DeactivateCohortRegistrationBulkAction`, `RegisterCohortForCourseBulkAction`, `RequiresActiveCohortMixin`, `cohort_not_empty_sentence` from `actions`; `:85` `CohortConfig` from `views` (used at 2836).
- `tests/test_cohort_delete_action.py:35-38` (`DeleteEmptyCohortAction`, `cohort_not_empty_sentence`) and `:39` (`CohortConfig`, used at 395).
- `tests/test_create_cohort_action.py:34`: `CohortConfig, CreateCohortAction` from `views` (`CohortConfig` at 51, `CreateCohortAction` at 64, 78, 110, 127, 146, 165).
- `tests/test_views.py:30`: `from freedom_ls.educator_interface import views as educator_views`, used at 2015 (`educator_views.CohortCourseRegistrationDataTable`) and 2030 (`educator_views.CohortHistoryPanel`). Both repoint to the new modules.
- `tests/test_reporting.py:806` and `:1390`: `mocker.patch("freedom_ls.educator_interface.reporting.learner_avatars", ...)`. Repoint to `freedom_ls.educator_interface.panels.cohort.report_panels.learner_avatars`.
- `tests/test_quick_views.py`, `tests/test_reporting.py` and `tests/test_views.py` otherwise import only from `tests.helpers`, `panels.cohort.data_tables` and `panels.*`, and reach the code over HTTP.
- `panels/staff/actions.py:289`: lazy `from freedom_ls.educator_interface.views import interface_config`. Unaffected (stays).
- `panels/learner/import_views.py:62-66`: `_attach_organisation`, `scope_request`, `standalone_page_context` from `views`. Unaffected.
- `panels/learner/data_table_panels.py:20`: imports `panels.cohort.data_tables`. Unaffected (the file stays).
- Docs and other places: no references to `educator_interface.{views,actions,reporting,quick_views}` as dotted paths in plugins, docs or templates (grep over non-`.py` files found none). One stale docstring in `freedom_ls/qa_helpers/management/commands/qa_create_learner_registrations_panel.py:4` mentions `freedom_ls/educator_interface/views.py` for `LearnerRegistrationsPanel`; that is a learner leftover. It is not a cohort name, so leave it for spec 7. `freedom_ls/reports/gather.py:371` mentions "educator_interface/views.py" in prose only. `claude_plugins/fls-dev/skills/alpine-js/SKILL.md:51` lists template `educator_interface/panels/cohort_report_downloads.html`; the template path does not change.
- There is no `test_filters.py` in the flat `tests/` any more (spec 5 moved it to `tests/panels/learner/test_filters.py`). The idea's mention of `test_filters.py` is stale: no `CohortConfig`-style name is referenced in any `test_filters.py`.
- Templatetags (`templatetags/educator_tags.py`): no imports of moving names.
- `tests/invariants/test_panel_template_rules.py:21`: `EDUCATOR_PYTHON_FILES = sorted(EDUCATOR_ROOT.glob("*.py"))` scans only flat top-level files for hand-set modal triggers. Moving code into `panels/` takes it out of this scan. This was already true for the earlier specs, so it is a known gap rather than something this spec introduces; worth a note to spec 7.
- `tests/invariants/test_course_shares.py:43` imports `_export_csv` from `tests.test_views`, so `_export_csv` (test_views.py:1328) must stay in `test_views.py` or be moved and repointed together.
- `tests/invariants/test_bulk_run_scoping.py:65` uses `PACKAGE_ROOT.rglob("*.py")`, so it covers the new paths automatically.
- Mock strings elsewhere: a search for `patch`, `spy` and `setattr` with `freedom_ls.educator_interface...` strings found only the two `reporting.learner_avatars` strings. Other cohort tests patch `freedom_ls.learner_management...` names, which are not moving.

## 6. Cohort slices of the shared test files

Flat tests dir: `tests/`. The idea's ranges (4.2, 4.3) are before spec 5. Approximate current content follows. Lines are `def`/`class` starts.

### `tests/test_views.py` (about 2,360 lines)

Cohort-owned (move):
- Cohort page shell and tabs: 119-231 (the tabs, the learners tab count and URL, page actions in the header).
- Cohort section tests: 329-504 (`_cohort_url` helper, Learners page param, Settings tab, header). `_cohort_url` is a helper also used elsewhere; check before moving.
- Completion panel: 465-506 (`_cohort_page`, `_add_cohort_progress`, `_completion_card`, `completion_scenario` fixture) and tests 575-657.
- Header refresh and overview: 506-709.
- Settings tab staff: 710-990 (`_settings_url`, `_staff_section`, `_staff_on`, `_staff_triggers`, `_register_triggers`).
- Courses tab: 992-1131 (`_deactivate_triggers` at 1066).
- Cohort history access: 1134-1235 (including `_cohort_history_access`).
- Learners tab on a cohort page: 1237-1327 and 1437-1578 (Remove/Move triggers, export, inactive cohort states). The export block `_export_csv` at 1328-1435 is also used by `invariants/test_course_shares.py`.
- Cohort role holders: 1580-1627.
- History tab: 1630-1798.
- Cohorts bulk bar: 1986-2020.
- History panel and no-results messages (parametrized over a mix of learner and cohort tables, at 2015-2065). These are mixed and must stay or be split.
- Cohort history export: 2067-2210 (`_cohort_entry`, `_cohort_history_url`).
- Avatar and query-count tests: 2213-2292 (`_learners_table`, `_registrations_table`, `_cohort_settings`; mixed).
- Shared course owner tests: 2294-2360 (cohort lists and completion, plus learner).

Not cohort (stay): 237-327 (instance page chrome, navigation toggle and section rules), 1800-1960 (messages routes, bulk run polling via `BulkActionRun`, `run_world` fixture), the learners bar 1956-1985, and most of 2015-2065.

The slices to split are mixed with page-chrome and learner tests, so the spec's plan must list each by name. Split targets: `test_data_tables.py` (extend the existing file), `test_data_table_panels.py`, `test_panels.py`, `test_instance_view.py`, `test_report_download.py` (probably empty; no cohort download test lives here; see test_reporting `TestCohortReportDownload`).

### `tests/test_actions.py` (about 2,960 lines)

Cohort-owned (move to `tests/panels/cohort/test_actions.py`):
- 124-217: rename (422, inline form, 204).
- 232-527: deactivate and reactivate dialogs, the active-cohort mixin, `cohort_not_empty_sentence` (438-495), and 497-546 (inactive guards, `_all_subclasses`, and `test_every_action_guarded_by_an_active_cohort_names_what_it_blocks`, which uses `RequiresActiveCohortMixin`).
- 547-668: rename-on-inactive and register dialogs.
- 671-967: unregister (deactivate cohort registration) fragments and posts. Helpers `_unregister_post_url`, `_unregister_url`, `_member`, `_registered_cohort`.
- 969-1015: the Remove-from-cohort-page tests (learner action; uses cohort page URL, mixed, probably stay with learner).
- 1015-1307: add-existing-learner picker, add-learner on a cohort tab, move, and stale picker posts. Mixed; the learner-picker ones use `AddExistingLearnersAction` and `AddLearnerToCohortAction`, which move.
- 1309-1654: audit entry tests, mixed (cohort rename/state at 1526-1650, learner ones stay).
- 1724-1795: `_RolledBackError` and the failure-after-write request helpers (`_rename_cohort_request`, `_deactivate_cohort_request`, `_create_cohort_request`); mixed.
- 1795-1830 and 1849-1925: reason dialogs (`_reason_deactivate_cohort` and `_reason_unregister_cohort` are cohort; others learner or staff).

Cohort bulk (to `tests/panels/cohort/test_bulk_actions.py`):
- 2090-2443: `_cohorts_bulk_post`, `_cohorts_bulk_confirm`, `_bulk_cohort`, and the `test_bulk_cohort_*` and `test_cohort_state_action_*` tests, including register and unregister.
- 2896-2960: `test_a_bulk_register_picker_resolves_a_course_only_when_it_is_registerable` and the cohort register-dialog check.
- Dialog tests at 2733-2765 (inactive and already-active cohort refusals) are cohort; 2561-2680 (`_single_row_dialog*`) is a mixed parametrization.

Also in `test_actions.py`: 1986-2090 (bulk threshold tests, learner), 2445-2560 (retired slugs, `test_every_bulk_action_has_an_expected_weight_and_loading_text` at 2522, `test_bulk_action_trigger_confirm_variant_and_loading_text` at 2529, mixed over all `BULK_ACTIONS`), 2829-2895 (`_superuser_get_ctx`, `test_the_add_learner_dialog_reads_its_preset_cohort_once`, `test_a_membership_dialog_on_a_cohort_page_reads_its_learner_once`, cohort-page dialogs). Those parametrized and mixed tests need a per-test decision.

### `tests/test_reporting.py` (about 1,420 lines)

All cohort. Move to `tests/panels/cohort/test_report_panels.py`, except `TestCohortReportDownload` (508-590), which tests the `cohort_report_download` view and goes to `test_report_download.py`.
- Helpers and fixtures: 69-171 (`_visible_text`, autouse `_site_context`, `_downloads_url`, `_pdf_url`, `_region_id`, `_downloads_panel`, `_refresh`, `_generate`, `_course_with_topic`, `_ready_report`).
- 173: the over-limit test.
- `TestReportTab` 181-507.
- `TestNeedsAttentionCard` 620-735.
- `TestNeedsAttentionPictures` 767-892.
- `TestCohortReportBody` 1005-1316.
- 1317: `test_reporting_surfaces_never_read_the_stored_progress_percentage` (reads template files by path at 1307-1308; check the paths still match after the move, since they do not change).
- 1327: the nameless-learner attention test.
- `TestCohortReportBodyPictures` 1352.
- `mocker.patch(...reporting.learner_avatars)` at 806 and 1390.
- Imports `freedom_ls.reports.tests.test_views` at line 63 (another app's test helpers).

### `tests/test_quick_views.py` (about 170 lines)

Cohort slice: `TestCohortQuickView` (32-134). It moves to `tests/panels/cohort/test_quick_view.py`, and its autouse `_site_context` fixture (26-30) is needed by both. The rest stays: `test_a_course_quick_view_404s_since_courses_declare_none` (135) is a course test, and `test_the_cohorts_list_renders_the_quick_view_trigger_attributes` (147) is a cohort one, so it moves with `TestCohortQuickView`. Note: the learner quick-view tests already moved to `tests/panels/learner/test_quick_view.py`.

### Whole-file moves

- `tests/test_cohort_delete_action.py` (about 600 lines) goes to `tests/panels/cohort/test_actions.py`. It has the fixture `cohort_with_granted_progress` (line 60) and helper `_panel_url` (77). Merge it with the cohort slice of `test_actions.py` into one file, or the idea's file mapping would collide. The spec has to say which.
- `tests/test_create_cohort_action.py` (about 170 lines) goes to `tests/panels/cohort/test_config.py`. It imports `CohortConfig` and `CreateCohortAction` and has a `_ctx` helper using `config=CohortConfig` (line 51).

Playwright tests (`tests/playwright/test_cohort_*.py`, `test_create_cohort_add_and_add_another.py`, `test_register_deactivate.py`, etc.) are not in scope, since they reach everything over the browser, and none import a moving name.

## 7. Mirroring baseline

The file is `test_organisation/mirroring_baseline.txt` at the repo root (not under `freedom_ls/`). The `# educator_interface` block is now lines 36-42, with six entries. It was 10 on main and spec 5 removed four:

```
# educator_interface
freedom_ls/educator_interface/tests/test_cohort_delete_action.py
freedom_ls/educator_interface/tests/test_create_cohort_action.py
freedom_ls/educator_interface/tests/test_document_title.py
freedom_ls/educator_interface/tests/test_interface_urls.py
freedom_ls/educator_interface/tests/test_organisation_switcher.py
freedom_ls/educator_interface/tests/test_sidebar.py
```

Moving `test_cohort_delete_action.py` and `test_create_cohort_action.py` removes the first two lines (a stale line fails the checker). The other four stay (`test_document_title`, `test_interface_urls`, `test_organisation_switcher`, `test_sidebar` are not cohort area). The idea's "10 files, lines 36-46" is out of date. `test_views.py`, `test_actions.py`, `test_reporting.py` and `test_quick_views.py` are not in the baseline (they apparently mirror an existing module name), but once `views.py` or `actions.py` is emptied, whether a test file named `test_actions.py` in the flat `tests/` still "mirrors" something is a question for the Mirroring checker. Check the rule in `test_organisation` before deleting any flat module (the cohort PR empties `actions.py`, `reporting.py` and `quick_views.py`). Spec 7 deletes the modules, but this PR deletes the tests' content and may leave empty or orphaned test files. Run the checker.

## 8. Import-cycle risk

- `panels/cohort/*` imports `panels/learner/*` (`CohortLearnerDataTable`, `ImportLearnersAction`, `RemoveFromCohortAction`, `MoveToCohortAction`, `AddLearnerAction`, `_membership_changed_response`), `panels/staff/actions` and `panels/audit_log/*`. The reverse edge is only `panels/learner/data_table_panels.py:20` -> `panels/cohort/data_tables.py` (`CohortDataTable` and `LearnerCohortDataTable`). `data_tables.py` imports only `common.*`, `learner_management` and `panel_framework`, so it is a leaf. Adding `CohortCourseRegistrationDataTable` (needs only `common.tables`) keeps it a leaf. No cycle.
- `panels/learner/actions.py` imports `inactive_cohort_response` from `panels.common.actions`. It imports no cohort code from the flat `actions.py`, so it is clean.
- No flat module outside the cohort set imports a moving name except `views.py` (the cohort entries) and `urls.py`. `forms.py`, `staff.py`, `learner_import.py`, `messaging.py`, `tasks.py` and `avatars.py` were checked: none import `actions`, `reporting`, `quick_views` or `views` cohort names. `panels/staff/actions.py:289` imports `views.interface_config` lazily inside a function (a cycle guard that already exists); leave it.
- `views.py` -> `panels.cohort.config` -> `instance_view` -> `panels/*`: none of those import `views`, with one exception to check. `report_download.py` imports `views._attach_organisation`, which is only safe because `views.py` does not import `report_download` (`urls.py` does). Keep it that way. `panels/cohort/config.py` must not import `report_download`.
- `CohortConfig` and `CohortInstanceView` need `CohortQuickView`, `CohortTabSet`, `CohortReportStack` and `CohortNeedsAttentionPanel`: these form a tree (`config` -> `instance_view` -> `panels`, `data_table_panels`, `report_panels`, `actions` -> `panels/learner/actions`). `config` also imports `data_tables`. No loop exists inside the cohort tree.
- `panels/cohort/panels.py` must import `CohortNeedsAttentionPanel` from `report_panels`, not from `instance_view`, which keeps `CohortOverviewStack` placement (the idea puts `CohortOverviewStack` in `instance_view.py`, so it imports from `panels.py` and `report_panels.py`).

## Other findings worth carrying into the spec

- The idea says the cohort slices come to roughly 1,500 lines of `test_views.py`, 1,050 plus 370 lines of `test_actions.py`. Those are stale after spec 5. Current cohort slices are somewhat smaller in `test_actions.py` and about the same in `test_views.py`. Use names, not numbers.
- `CohortHistoryPanel` is at `views.py:436`, not "V:1732" and not in the group with `CohortCoursesPanel`. In the idea it goes to `data_table_panels.py`. It is a `HistoryPanel` subclass using `TargetedAuditLogEntryTable`; `HistoryPanel` is in `panels/audit_log/data_table_panels.py`.
- `CohortStaffPanel` is a plain `Panel` (not a data-table panel), so it goes to `panels.py`, as the idea says.
- Templates: panels reference `educator_interface/panels/cohort_*.html` and `educator_interface/modal/*.html`. Template paths do not change.
- The `# TODO` block in `views.py:130-139` and any `@claude` or TODO comments in moved code must be preserved. None were found inside the cohort symbols.
- `interface_config` in `views.py:552` references `CohortConfig` by name, so it only needs its import line changed.
- `DOWNLOAD_COHORT_REPORT` is also redefined as a string in `tests/invariants/test_permission_matrix.py:127`. It is not an import, so nothing to repoint.

status: ok
