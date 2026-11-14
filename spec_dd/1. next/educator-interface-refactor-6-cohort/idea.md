# Educator interface refactor: the cohort area

Spec 6 of 7 in the Educator interface code layout effort. Read the "Educator interface code layout" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Move the rest of the cohort area out of the flat `freedom_ls/educator_interface/` modules into `freedom_ls/educator_interface/panels/cohort/`. This is a pure move. No behaviour, UI, URL, URL name or template path changes.

It moves:
- `config.py`: `CohortConfig` and `CreateCohortAction`.
- `data_tables.py`: the cohort data tables that `educator-interface-refactor-5-learner` has not already moved.
- `data_table_panels.py`, `panels.py`, `report_panels.py`, `instance_view.py`, `actions.py`, `bulk_actions.py`, `report_download.py` and `quick_view.py`.
- The cohort half of `reporting.py`.

It adds one new data migration that rewrites `BulkActionRun.action_path` for the cohort bulk actions. It moves the cohort tests to `tests/panels/cohort/`. It repoints every import and `mock.patch` string for what it moves.

## Why

`views.py` (3376 lines on main) and `actions.py` (3772 lines) are too big to read. The cohort area is the last large area to leave them that depends on the learner area. Once `educator-interface-refactor-5-learner` has moved the shared learner/cohort tables and the membership actions, the cohort code can move in one reviewable step without an import cycle.

## What is settled

Line ranges below are main's, from `research_code_inventory.md` section 1. They are from before `extract_panels_framework-1-gather-generic-code` lands, and the spec must re-check every one. Names matter more than numbers.

Production code that moves, and where it goes:
- `panels/cohort/config.py`: `CohortConfig` and `CreateCohortAction` (V:1784-1846).
- `panels/cohort/data_tables.py`: `educator-interface-refactor-5-learner` creates this file with `CohortDataTable` and `LearnerCohortDataTable`, to break the learner/cohort cycle. This spec adds `CohortCourseRegistrationDataTable` (V:1473-1501) to it and does not recreate it. `CohortLearnerDataTable` lives in `panels/learner/data_tables.py`.
- `panels/cohort/data_table_panels.py`: `CohortLearnersPanel` (V:1502), `CohortCoursesPanel` (V:1535) and `CohortHistoryPanel` (V:1732).
- `panels/cohort/panels.py`: `CohortDetailsPanel`, `CourseCompletion`, `CohortCourseCompletionPanel`, `CohortNamePanel`, `CohortStaffPanel` and `CohortStatusPanel` (V:1457-1731 apart from the data-table panels above).
- `panels/cohort/report_panels.py`: the cohort half of `reporting.py` (R:135-330): `GenerateReportAction`, `CohortReportDownloadsPanel`, `CohortNeedsAttentionPanel`, `CohortReportBodyPanel`, `CohortReportStack` and `QuizConfusionCard`. `LazyBodyPanel`, `render_region` and the badges are shared and come from `panels/common/report.py`, which `educator-interface-refactor-1-scaffolding-and-common` creates. The dashboard half and `LearnerCoursesPanel` stay for their own specs.
- `panels/cohort/instance_view.py` (a file, not a directory): `CohortSettingsStack`, `CohortOverviewStack`, `CohortTabSet` and `CohortInstanceView` (V:1709-1782).
- `panels/cohort/actions.py`: `inactive_cohort_response`, `cohort_not_empty_sentence`, `RequiresActiveCohortMixin`, `EditCohortAction`, `CohortStateAction`, `DeactivateCohortAction`, `ReactivateCohortAction`, `DeleteEmptyCohortAction`, `RegisterCohortForCourseAction`, `KEEPING_NAMES_SHOWN`, `DeactivateCohortRegistrationAction`, `AddExistingLearnersAction`, `AddLearnerToCohortAction` and `cohort_state_actions` (A:310-353, 354-384, 414-448, 498-666, 782-843, 1439-1505, 1686-1706).
- `panels/cohort/bulk_actions.py`: `CohortBulkAction`, `CohortCourseBulkAction`, `RegisterCohortForCourseBulkAction`, `DeactivateCohortRegistrationBulkAction`, `CohortStateBulkAction`, `DeactivateCohortsBulkAction` and `ReactivateCohortsBulkAction` (A:3578-3772). Four are `@register_bulk_action` classes. The bulk framework and `CoursePickerMixin` stay in `panels/common/bulk_actions.py`.
- `panels/cohort/report_download.py`: `cohort_report_download` (V:2744-2757) and `_scoped_cohort`. The spec checks whether any other view uses `_scoped_cohort`. If one does, it stays in the shell and is imported.
- `panels/cohort/quick_view.py`: `CohortQuickView` (`quick_views.py:119`). The shared helper `visible_registrations_with_progress` stays where it is and is imported.

Things this spec reads from siblings and does not move:
- The membership actions and the learner actions that `CohortLearnersPanel` draws (`MembershipAction`, `RemoveFromCohortAction`, `MoveToCohortAction`, `AddLearnerAction`, `ImportLearnersAction`): `educator-interface-refactor-5-learner`.
- The cohort-scoped staff actions that `CohortStaffPanel` draws: `educator-interface-refactor-3-staff`.
- `HistoryPanel` and the audit tables that `CohortHistoryPanel` subclasses: `educator-interface-refactor-2-dashboard-and-audit-log`.
- This spec imports each from wherever it lives when the spec runs. Imports go one way only: `panels/cohort/` imports `panels/learner/`, never the reverse. Every `__init__.py` stays empty.

The migration:
- It is a new data migration in `freedom_ls/educator_interface/migrations/`, numbered next after the one `educator-interface-refactor-5-learner` adds. It does not edit `0001_rename_unregister_bulk_runs.py`.
- It rewrites `BulkActionRun.action_path` from `freedom_ls.educator_interface.actions.<Class>` to `freedom_ls.educator_interface.panels.cohort.bulk_actions.<Class>` for the four registered cohort bulk action classes. The spec reads the class list from `@register_bulk_action` and does not trust this text.
- It has a reverse that maps the paths back. It is idempotent and leaves other rows alone.
- It has a test in `tests/migrations/`, in the style of `test_0001_rename_unregister_bulk_runs.py`. The test covers forward, reverse and an untouched row.
- Its upgrade notes set `requires_migrations: true`.

Tests move with the code to `tests/panels/cohort/test_<module>.py`, each directory with an empty `__init__.py`:
- `test_cohort_delete_action.py` goes to `tests/panels/cohort/test_actions.py`.
- `test_create_cohort_action.py` goes to `tests/panels/cohort/test_config.py`.
- The cohort slices of `test_views.py` (research section 4.2, about 1500 lines) go to `test_data_tables.py`, `test_data_table_panels.py`, `test_panels.py`, `test_instance_view.py` and `test_report_download.py`.
- The cohort slices of `test_actions.py` (section 4.3: cohort actions about 1050 lines, cohort bulk about 370) go to `test_actions.py` and `test_bulk_actions.py`.
- The cohort slice of `test_reporting.py` goes to `test_report_panels.py`.
- The cohort slice of `test_quick_views.py` goes to `test_quick_view.py`.
- A test file exists only if its module exists in the same PR.
- Each spec removes only its own ranges from the shared test files, so merge conflicts stay mechanical.

References repointed in this spec:
- Every import and every `mock.patch` or `monkeypatch` string for a moved name. Each string points at the module where the name is looked up, not where it is defined. Attribute patches on a module object break silently, so the spec runs the tests and does not rely on grep.
- The cohort entries in `views.py` (`interface_config` imports `CohortConfig`) and the `cohort_report_download` line in `urls.py`. `educator-interface-refactor-7-cleanup` owns the rest of `urls.py`.
- The 5 test files that import `CohortConfig` and other moved names (`test_cohort_delete_action.py`, `test_create_cohort_action.py`, `test_filters.py`, the invariants and `interface_walk.py`) are repointed.
- The lazy and `TYPE_CHECKING` imports of `OrganisationScopedRequest` in cohort code come from `panels/common/request.py`.
- The 10 files of the `# educator_interface` block in `test_organisation/mirroring_baseline.txt` (lines 36-46 on main) lose a line for each file that moves in this PR. The checker fails on stale lines.

No shim. The old modules keep no re-export of what moved. The migration is how stored paths survive.

## Open until the spec

- Whether `_scoped_cohort` has users outside the cohort area.
- The migration number, which depends on what `educator-interface-refactor-5-learner` adds.
- The final line ranges after `extract_panels_framework-1-gather-generic-code` lands.

## Out of scope

- Any behaviour, UI, URL or template change.
- The learner area, the shared learner/cohort data tables and the membership actions: `educator-interface-refactor-5-learner`.
- The staff, course, dashboard and audit log areas.
- Deleting the emptied flat modules, trimming `views.py`, and the `templatetags`, `qa_helpers`, fls-dev docs and test-baseline updates: `educator-interface-refactor-7-cleanup`.
- The flat domain modules (`forms.py`, `staff.py`, `learner_import.py`, `messaging.py`).

## Resources

- `spec_dd/1. next/educator-interface-refactor/research_code_inventory.md`: line ranges (section 1), cycles (2.3), target tree (3), test split (4), dotted-path references (5), Option A and the migration decision (6).
- `spec_dd/1. next/educator-interface-refactor/research_collisions.md`: what `extract_panels_framework-1-gather-generic-code` and other specs touch.
- `spec_dd/1. next/educator-interface-refactor/research_downstream_imports.md`: why the break is clean.
- `freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py` and `freedom_ls/educator_interface/tests/migrations/test_0001_rename_unregister_bulk_runs.py`: the precedent.
- `freedom_ls/panel_framework/bulk_actions.py` and `freedom_ls/panel_framework/bulk_runs.py`: where `action_path` is written and read.
