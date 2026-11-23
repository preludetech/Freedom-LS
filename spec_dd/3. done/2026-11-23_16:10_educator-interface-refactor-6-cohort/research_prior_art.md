# Research: prior art for moving the cohort area into `panels/cohort/`

Method: read-only (no Bash, so no git log). Sources: `todo.md`, `upgrade_notes.md`, `research_prior_art.md` and plans of specs 1-5 in `spec_dd/3. done/`, `spec_dd/1. next/educator-interface-refactor/research_collisions.md`, and the current tree. Specs 1-5 have no `qa_report.md`, bugfix report or review notes: their `todo.md` files show `do_qa` and `qa_fix` unticked (pure moves, no frontend QA plan). So "what went wrong" comes from the spec 1/2 prior-art notes and the plans, not from QA reports.

## 1. State of the tree now (spec 6 starts from this)

- Specs 1-5 are done. Migrations present: `0001_rename_unregister_bulk_runs.py` and `0002_move_learner_bulk_runs.py`. **This spec's migration is `0003`.** The idea's "numbered next after spec 5's" resolves to 0003; its `dependencies` is `("freedom_ls_educator_interface", "0002_move_learner_bulk_runs")`.
- `panels/cohort/` holds only `__init__.py` and `data_tables.py` (spec 5). `tests/panels/cohort/` holds `__init__.py` and `test_data_tables.py`. This spec adds to both and recreates neither.
- Flat `actions.py` is now cohort-only (about 650 lines). Its classes: `RequiresActiveCohortMixin` (122), `EditCohortAction`, `CohortStateAction`, `DeactivateCohortAction`, `ReactivateCohortAction`, `DeleteEmptyCohortAction`, `RegisterCohortForCourseAction` (307), `DeactivateCohortRegistrationAction` (342), `AddExistingLearnersAction` (400), `AddLearnerToCohortAction` (452), `CohortBulkAction` (470), `CohortCourseBulkAction` (493), then four `@register_bulk_action` classes: `RegisterCohortForCourseBulkAction` (537), `DeactivateCohortRegistrationBulkAction` (559), `DeactivateCohortsBulkAction` (612), `ReactivateCohortsBulkAction` (642); plus `CohortStateBulkAction` (600, unregistered). The idea's A: ranges (3578-3772 etc.) are long stale. Locate by name.
- `_scoped_cohort` is at `views.py:615`, used at `views.py:627` (`cohort_report_download`). The grep over `freedom_ls/` found no other user. That settles one "open until the spec" question, subject to a re-grep in the spec (including templates and tests).
- Registered cohort bulk classes by grep: exactly four, matching the idea. `CohortBulkAction`, `CohortCourseBulkAction`, `CohortStateBulkAction` are unregistered bases, never stored.
- Mirroring baseline: `test_organisation/mirroring_baseline.txt` now lists only six `educator_interface` lines (36-42), not ten: `tests/test_cohort_delete_action.py`, `test_create_cohort_action.py`, `test_document_title.py`, `test_interface_urls.py`, `test_organisation_switcher.py`, `test_sidebar.py`. Earlier specs deleted their lines. This spec deletes only the first two (the idea's "10 files, lines 36-46" is stale). The checker fails on stale lines, so delete them in the same commit that moves the test file.
- Template for the migration: 0002 uses `MOVES = [(old, new) ...]` built from a name list, a shared `_repoint(apps, pairs)` with `apps.get_model("freedom_ls_panel_framework", "BulkActionRun")`, whole-path `filter(action_path=old).update(action_path=new)`, a real reverse built from the same pairs, and no `action_name` change. Its test is `tests/migrations/test_0002_move_learner_bulk_runs.py`. Copy that, not 0001 (0001's reverse is `noop`).
- 0001 still names the old `freedom_ls.educator_interface.actions.DeactivateRegistrationBulkAction` path. 0002 and 0003 rewrite other paths. Never edit 0001 or 0002. Reverse order is safe because each migration handles disjoint class names. Test that a learner row (already on `panels.learner.bulk_actions`) and an unrelated row survive 0003 forward and reverse untouched, and that an already-new cohort path is a no-op (idempotent).

## 2. What happened in specs 1-5 (lessons, with source)

Spec 1 (`scaffolding-and-common`, done 2026-11-20):
- One slice per module, one commit moving code, a second moving its tests; `git mv` for whole files with no edits. Final slice ran gates: leaf-rule greps, repo-wide grep per moved name, `manage.py check`, `makemigrations --check`, fresh-interpreter import of each new module, collect-count equality, `pre-commit run --all-files`.
- Went wrong: shared test helpers were first added to `tests/helpers.py` untyped; fix-up commit 77187808a. Type-hint moved helpers from the start (project rule: type hints on all functions).
- `tests/test_filters.py` had an autouse `_site_context`; spec 1 made it a non-autouse fixture in `tests/conftest.py` plus `pytestmark = pytest.mark.usefixtures("_site_context")` in both staying and moved files. Check every split test file for module-level autouse fixtures, module-level helpers and `pytestmark` before cutting. (The cohort slices of `test_views.py`/`test_actions.py` will meet the same issue.)
- Idea line ranges were about 90 lines stale after extract-1 landed; spec 2 found them stale again. Treat all ranges as stale.

Spec 2 (`dashboard-and-audit-log`, done 2026-11-20):
- Stale patch string trap: `views.py` imported `HistoryPanel` and `TargetedAuditLogEntryTable` for its own subclasses, so old-path imports and `mock.patch` strings on `views` still resolved and patched nothing. Its plan added a manual proof: repoint one patch string back at the old module and watch the test fail. Do the same for cohort patches.
- A named class (`AuditPeriodFilter`) no longer existed (extract-1 had renamed it). Re-derive every name by grep.
- Import block in `views.py` kept alphabetical, one name per line, so sibling merges stay clean.
- Placement rule: an area imports only `panels/common/`, `panel_framework`, leaf modules and other apps; never flat modules. Checked by grep, no new import-linter contract.
- Rebase left origin on the pre-rebase branch because the force-push was refused by the permission system; a user had to run `git push origin HEAD --force-with-lease --force-if-includes`. Expect the same.
- Known, non-move flakes: `freedom_ls/audit_log/tests/test_actions.py::test_course_progress_actions_describe_their_details` fails in loaded full runs and passes alone; `needs_fls_host` tests in `panel_framework/tests/test_reference.py` fail under xdist ("basename user already registered"); playwright `test_quick_view_drawer` fails under load. A PR review also flagged a pre-existing N+1 (`_gather_visible`).

Specs 3 (staff), 4 (course): no migration, patch-string rule as above; spec 4 also had to edit `import_baseline.txt` and `import_contracts.toml` because a split test file moved an importer of `course_interest.factories`. Check for entries in both files, not only `mirroring_baseline.txt`.

Spec 5 (learner), upgrade notes (the closest precedent):
- Flat cohort code left behind still imports moved names (`views` imports `LearnerConfig`, `CohortDataTable`, `CohortLearnerDataTable`, `ImportLearnersAction`, `MoveToCohortAction`, `RemoveFromCohortAction`; `actions` imports `AddLearnerAction`, `inactive_cohort_response` (now `panels.common.actions`)). So old-path imports still resolve for those. Spec 6 must repoint every one it touches (`AddLearnerToCohortAction(…, AddLearnerAction)` etc. should import from `panels.learner.actions`, never the old flat path).
- It documented, per moved name, old module to new module, the `requires_migrations: true` flag, the migration name, the whole-path-only note and a "grep your `mock.patch` strings" manual step naming each patched name and the module that now looks it up. Copy this shape for the cohort upgrade notes. Cohort-side patched names to list: whatever `test_actions.py`/`test_views.py` patch on cohort actions (for example `inactive_cohort_response`, cohort-membership helpers and any `send_*`/`record_*` calls); derive by grep of `mock.patch`/`monkeypatch.setattr` in the cohort test slices.
- Spec 5 removed the old module `filters.py` whole; spec 6's flat modules `reporting.py`, `quick_views.py` stay (shared with dashboard/other halves), so the cohort half of `reporting.py` is a partial cut, not a `git mv`.

## 3. Collision and sequencing facts from `research_collisions.md`

- `extract_panels_framework-1-gather-generic-code` (landed) already changed the shapes: `EducatorReasonMixin`, `EducatorBulkAction(PermittedBulkAction[User])`, `LazyBodyPanel`/`render_region` now in `freedom_ls.panel_framework.lazy_panels`, `ToggleFilter`/`PeriodFilter`. Specs for this move must use the framework names.
- `extract_panels_framework-5-package-and-install` will rewrite the `freedom_ls.panel_framework` import prefix (55 lines in 22 files) after the refactor; it is mechanical and wants the refactor first. Keep framework imports in moved files as the current `freedom_ls.panel_framework...` form, do not pre-empt.
- `audit-log-coverage-gaps` touches `cohort_report_download`; it prefers to land after the refactor. Mention `cohort_report_download` in the spec so that later spec can find it (`panels/cohort/report_download.py`).
- `deadlines-6-educator-management` / `deadlines-7-educator-at-risk` / `corporate-job-course-recommendations-4/5` edit cohort/learner panels and should rebase onto the new layout.
- The roadmap ordering (specs 3-5 may run in parallel; this spec depends on 5) means the shared `test_views.py` / `test_actions.py` are already reduced; take the cohort remainder with "pure cut and paste", each spec removing only its own ranges.
- `test-organisation-and-hygene-15-educator-interface` is blocked by this effort; it re-audits layering (rule 2) afterwards. Do not take on its work here.

## 4. Implications for how this spec should be written

1. State the migration as `0003_move_cohort_bulk_runs` depending on 0002, same shape as 0002, with the four class names listed and cross-checked against `@register_bulk_action` by grep; test forward, reverse, untouched rows (a learner-path row, an unrelated row, an already-new cohort path).
2. Per patch string, name the module that does the lookup, and require a manual "point one string back at the old module" proof run. The suite must run the whole `educator_interface` test directory plus `invariants/`, `interface_walk.py` users, `test_filters.py` (which imports `CohortConfig`).
3. Import direction: `panels/cohort/` imports `panels/learner/`, `panels/common/`, `panels/staff/`, `panels/audit_log/` (for `HistoryPanel`); no reverse. Verify by grep that nothing under `panels/learner/`, `panels/staff/`, `panels/common/` imports `panels/cohort/` other than `panels/cohort/data_tables.py` (which spec 5 created to break the learner/cohort cycle; check which direction its importers take).
4. Cycle risk is highest where cohort classes subclass learner ones (`AddLearnerToCohortAction(AddLearnerAction)`) and where `views.py` imports back from cohort modules. After the move, `views.py` still holds `interface_config`; its import of `CohortConfig` must be one directional.
5. Moved flat leftovers: after this spec `actions.py` should be empty-or-deletable and the cohort half of `reporting.py` gone; deletion of the emptied modules is owned by spec 7 per the idea, so leave empty-ish files but ensure nothing imports them (grep).
6. Test-mirroring: each new test file needs its production module in the same PR; delete exactly the two stale baseline lines; check `import_baseline.txt` / `import_contracts.toml` for moved test importers.
7. Gates to copy from spec 1: `manage.py check`, `makemigrations --check` (no model change, but proves the data migration does not need a schema one), fresh-interpreter `python -I -c "import ..."` of each new module (catches import cycles that only show on first-import order), collect-count equality before and after, `pre-commit run --all-files` (test-mirroring, lint-imports, app-map-fresh).
8. Do not blame the known flakes (spec 2 list above) on the move; run them alone first. Expect a rebase force-push to need the user.

## 5. External notes (cited from memory, not fetched this run)

- Where to patch: https://docs.python.org/3/library/unittest.mock.html#where-to-patch (patch the module that looks the name up).
- `RunPython` reverse guidance: https://docs.djangoproject.com/en/stable/ref/migrations/operations/#runpython
- Import cycles when splitting a module: move shared code down into a leaf both sides import (https://docs.python.org/3/faq/programming.html#what-are-the-best-practices-for-using-import-in-a-module), which is the approach spec 5 took with `panels/cohort/data_tables.py`.

status: ok
