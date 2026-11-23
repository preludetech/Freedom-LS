# Research: reference implementations

Topic: how the earlier specs of this effort split one area out of the flat `views.py`, `actions.py`, `reporting.py`, `filters.py` and `quick_views.py` into `panels/<area>/`, mirrored the tests, and migrated stored dotted paths. The in-repo references are authoritative. Sources are `spec_dd/3. done/*educator-interface-refactor-{1..5}*`, `freedom_ls/educator_interface/panels/`, `freedom_ls/educator_interface/tests/panels/` and `freedom_ls/educator_interface/migrations/`. I read the spec, plan and upgrade notes of spec 5 in full, the migration and its test, and the upgrade notes of spec 4. I did not read the review or QA notes of specs 1-4. The `todo.md` of spec 5 has no lessons-learned content.

## 1. Settled pattern (copy this)

### Source layout
- One directory per area under `panels/`, with an empty `__init__.py`. Module names are by role, not area: `config.py`, `data_tables.py`, `data_table_panels.py`, `panels.py`, `instance_view.py`, `actions.py`, `bulk_actions.py`, `filters.py`, `quick_view.py`. The learner area also has `messages.py` and `import_views.py`, and the course area has `content_preview.py`. These are one-off modules for blocks that did not fit a role without a cycle.
- Each new module starts with a one-line purpose docstring stating what it holds, never where it came from. Next comes `from __future__ import annotations`, then absolute imports only, then a sorted (`RUF022`) `__all__` of every name it owns, underscore names included.
- Moves are byte-for-byte: bodies, comments, `TODO`s and `@claude` comments, decorators and underscore spellings all stay, and only import lines change. Quoted casts such as `cast("OrganisationScopedRequest", ...)` stay quoted.
- Bulk-action registration is import-time. The bulk registry is filled by `@register_bulk_action` when the module is imported, so spec 5 had `panels/learner/config.py` import `panels.learner.bulk_actions` with `# noqa: F401` and a one-line why-comment. This keeps the action-bar order unchanged. Spec 6 must do the same in `panels/cohort/config.py` for the four registered cohort bulk actions. Registration order within the `cohort` table must stay as it is today.
- Where a name is shared between areas and would cause a cycle, it goes to `panels/common/` and not to the area that happens to define it. Spec 5 moved `inactive_cohort_response` to `common/actions.py`, `learner_status_badge` and `_LEARNER_STATUS_TONES` to `common/badges.py`, and (via spec 4) `_course_title_column` and `_cohort_links_column` to `common/tables.py`. Spec 6 should look for the same: its `RequiresActiveCohortMixin` already imports `inactive_cohort_response` from `common`.
- A helper that only one module uses should not be pulled out. A name that would force `config → instance_view → X → config` goes to the module that already imports `config` (for example `partial_oversight_thread_older` went to `import_views.py`, not `messages.py`).

### Import direction
Spec 5 states it as a rule and checks it with grep, with no import-linter contract:
- `panels/common` imports no area, and areas import `common`.
- `panels/cohort/data_tables.py` imports only `common`.
- `panels/learner/*` imports `common`, `audit_log.data_table_panels` (for `HistoryPanel`) and `cohort.data_tables`.
- Cohort (this spec) imports learner and never the reverse.
- A new area module never imports a flat module (`views`, `actions`, `reporting`, `filters`, `quick_views`). The only exception is `learner/import_views.py`, which imports the shell `views.py`.
- Inside the area, imports run one way: `filters ← data_tables ← data_table_panels`, `actions ← bulk_actions ← config`, `quick_view ← panels`, and `panels`, `data_table_panels`, `messages ← instance_view ← config`.
- Flat modules that stay may import from `panels/<area>/`. This was the way the stay-behind cohort code kept working during spec 5, and the flat cohort code is exactly what spec 6 now moves.

Spec 5's success criteria were grep checks over the new packages:
- No `freedom_ls.educator_interface.(actions|reporting|filters|quick_views)` strings.
- No `educator_interface.views` outside `import_views.py`.
- No `panels.(staff|course|dashboard)` imports.
- No relative `from .` imports.
- Every module imports in a fresh interpreter (`python -I` after `django.setup()`).
- `bulk_actions_for_table("<table>")` returns the same actions in the same order as on `main`.

Spec 6's own grep set should add: under `panels/cohort/`, `panels.learner` may appear, but `panels.(staff|course|dashboard)` and `panels.audit_log` need justification. Note that `HistoryPanel` lives in `panels/audit_log/data_table_panels.py`, so `CohortHistoryPanel` imports `audit_log`, as the idea says. The current learner rule forbade `panels.audit_log` only under `cohort/`, and that rule must be relaxed for `CohortHistoryPanel`.

### Test layout
- `tests/panels/<area>/__init__.py` (empty) plus `test_<module>.py` mirroring the module. `audit_log/` also has its own `conftest.py`, which is allowed for area-only fixtures. Shared fixtures stay in `tests/conftest.py` and hand-imported helpers go in `tests/helpers.py`.
- A test file exists only where its module exists, and the `test-mirroring` hook needs the module to be in the same commit or an earlier one.
- Tests move by name, never by line range. Placement rule from spec 5: a test whose request is made against that area's page, panel or action moves. A test that drives a different area's page, spans areas, or is table-agnostic (bulk run status polling, `EDUCATOR_TABLES` and its parametrised tests) stays and only has its imports repointed.
- A moved test keeps its `_site_context` opt-in (module `pytestmark` if every test in the new file needs it, otherwise per-test or a local autouse fixture).
- Helpers used by both a moving test and a staying test, or by two new test files, go to `tests/helpers.py` with full type hints. This is the first commit of the work. It also repoints `tests/invariants/test_course_shares.py`, which imported `_learner_page` and `_learner_reregister_url` from `tests.test_views` and `tests.test_actions`. Spec 6 should look for the same cross-imports for cohort helpers (`_cohort_url`, `_cohort_rows`, `_bulk_cohort_post`, `_bulk_cohort_confirm`, `_bulk_confirm_with`, `_picker_dialog`, `_dialog_title`).
- Whole-file moves are a `git mv` with no content change in their own commit, and the import repoints land in the commit before. Check `git show --stat HEAD` reports a rename. The plan recorded `pytest --collect-only -q --no-cov | tail -1` into `.sdd-work/collect_count_before.txt` before any change, and the success criterion was the same count after, plus the new test cases. Spec 6 should do the same.
- `tests/test_reporting.py` has a `_NEW_REPORTING_FILES` list, a stored-progress guard. Spec 5 added `panels/learner/panels.py` to it, and left `panels/learner/data_tables.py` out because `progress_percentage` is a legitimate field name there. Spec 6 should check whether `panels/cohort/report_panels.py` and `panels/cohort/panels.py` belong in it. The reporting test is the module that currently holds the cohort slice (`test_report_panels.py`).

### Slicing and commits (spec 5 plan)
- About 13 slices, each a "behaviour" statement with Builds on / Touches / numbered steps. Each slice ran the targeted tier through `.claude/ds/scripts/select_tests.sh --working-tree`, then committed.
- Order: shared test helpers first; names shared across areas into `common`; leaf modules (filters, quick view); then `actions`, `bulk_actions`, `data_tables`, `panels`, `data_table_panels`, `messages`, `instance_view`, `config` and `import_views`; the migration and its test; the final sweep.
- "TDD for a move": no assertion changes. Red means a failing import or test after the cut, and the fix is the import, never the assertion. The only assertion-side edits spec 5 allowed were the `_NEW_REPORTING_FILES` entry, the `test_0001` migration target, the new `test_0002` and the reason-mixin walk.
- Patch strings: each points at the module that looks the name up. Spec 5's table:
  - `...actions.move_between_cohorts` became `...panels.learner.actions.move_between_cohorts`.
  - `...views.send_message` became `...panels.learner.messages.send_message`.
  - `...views.MAX_UPLOAD_BYTES` became `...panels.learner.import_views.MAX_UPLOAD_BYTES`.

  A stale string on a flat module that still imports the name resolves and patches nothing, so the tests still pass. The guard is a one-off mutation check at the end: point one patch string back at the old module and confirm its test fails. Spec 6 should repeat this for its patches, especially anything patched on `reporting` or `actions` for cohort code (report generation, `GenerateReportAction`, `record_*` audit helpers).
- Test files outside the area that import moved names are repointed in the same slice. Spec 5 listed `templatetags/educator_tags.py`, `tests/playwright/test_learners_list_flow.py`, the `EDUCATOR_TABLES` entries (`educator_views.<Name>`), `urls.py` and `claude_plugins/fls-dev/resources/testing.md`. The invariant `tests/invariants/test_reason_mixin.py` walks `actions` plus `panels.learner.actions` without duplicates and asserts the same count (9). Spec 6 adds `panels.cohort.actions` to this walk. Other invariants walk `interface_config`, so they stay valid.

### Mirroring baseline
- `test_organisation/mirroring_baseline.txt` lists flat test files that have no module of their own. The line for a file goes in the commit that moves that file. The checker fails on stale lines, so delete the line in the same commit as the `git mv`.
- It is not safe to trust the idea's "10 files, lines 36-46". On this branch the `# educator_interface` block (line 36) has only 6 entries: `test_cohort_delete_action.py`, `test_create_cohort_action.py`, `test_document_title.py`, `test_interface_urls.py`, `test_organisation_switcher.py` and `test_sidebar.py`. Specs 2-5 already removed the rest. Spec 6 therefore removes exactly the two cohort lines, `test_cohort_delete_action.py` and `test_create_cohort_action.py`, when those files move to `tests/panels/cohort/test_actions.py` and `test_config.py`. The other four stay. Re-read the file at spec time.
- Never add to `mirroring_exemptions.txt`.
- Spec 5's success criterion was that the diff of the baseline shows only the one removed line.

### Migration and its test (the exact precedent)
`freedom_ls/educator_interface/migrations/0002_move_learner_bulk_runs.py` already exists, so spec 6's migration is `0003_<slug>.py`, depending on `("freedom_ls_educator_interface", "0002_move_learner_bulk_runs")`. Its shape:
- `from django.apps.registry import Apps`, with `BaseDatabaseSchemaEditor | None` annotations on `forwards` and `backwards`.
- `_OLD = "freedom_ls.educator_interface.actions."` and `_NEW = "freedom_ls.educator_interface.panels.learner.bulk_actions."`, then a module-level `MOVES` list of `(old, new)` tuples built from a name list.
- One helper `_repoint(apps, pairs)` that calls `apps.get_model("freedom_ls_panel_framework", "BulkActionRun")` and then, per pair, `.objects.filter(action_path=old).update(action_path=new)`. `forwards` passes `MOVES` and `backwards` passes the swapped pairs. The docstring says the historical manager has no site filter, so all sites' runs are repointed, and that matching is on whole paths only. It imports no action class and uses literal strings.
- It updates only `action_path`. It leaves `action_name` alone.
- `operations = [migrations.RunPython(forwards, backwards)]`, with a real reverse and no `noop`.
- For spec 6 the four registered cohort bulk actions must be read from the `@register_bulk_action` decorators in `actions.py` (the idea says four of `CohortBulkAction`, `CohortCourseBulkAction`, `RegisterCohortForCourseBulkAction`, `DeactivateCohortRegistrationBulkAction`, `CohortStateBulkAction`, `DeactivateCohortsBulkAction` and `ReactivateCohortsBulkAction` are registered). Candidates are `RegisterCohortForCourseBulkAction`, `DeactivateCohortRegistrationBulkAction`, `DeactivateCohortsBulkAction` and `ReactivateCohortsBulkAction`; confirm with grep. The 0002 test already uses `DeactivateCohortsBulkAction` as its "untouched" case: `freedom_ls.educator_interface.actions.DeactivateCohortsBulkAction`. Once spec 6 moves it, that row is no longer untouched under migration 0003, but it is still correctly untouched under 0002. Check that the 0002 test still passes when 0003 sits on top. See the next point.

Test shape (`tests/migrations/test_0002_move_learner_bulk_runs.py`):
- Constants `APP = "freedom_ls_educator_interface"`, `RUNS = "freedom_ls_panel_framework"`, `BEFORE = [(APP, "0001_...")]`, `AFTER = [(APP, "0002_...")]`.
- A fixture `migrated_back_to_the_leaf` yields, then rebuilds the executor graph and migrates to `executor.loader.graph.leaf_nodes()`, so later tests see the full schema.
- `_historical_model()` migrates to `BEFORE` and returns the model from `project_state([(RUNS, "0001_initial")]).apps`. `_migrate(target)` builds a fresh executor, calls `build_graph()`, migrates, and returns the model at that state. `_make_run` creates a row with `site_id`, `requested_by_id`, `action_path`, `table_key`, `action_name` and `keys=[]`. `_stored` returns `(action_path, action_name)`.
- Every DB test is `@pytest.mark.django_db(transaction=True)`, with a "transaction=True: the tests migrate backwards and forwards" comment, and takes `mock_site_context` and the fixture.
- Cases (parametrised over every class): forward rewrites; `action_name` is unchanged; reverse restores the old path (rolls back to `BEFORE`); a run of another action or an unknown path is left alone; a row already on the new path is left alone; and a non-DB test asserts `issubclass(import_string(f"{NEW}{name}"), RecordedBulkAction)`.

Two known pitfalls from spec 5:
- When 0002 landed, the existing `test_0001` test had been migrating to the graph leaf and then reading the rows it asserted on, so 0002 would have rewritten them. Spec 5 made the only assertion-side edit to an existing test: it now migrates forward to `("freedom_ls_educator_interface", "0001_rename_unregister_bulk_runs")` and builds its current-state model from that target. Spec 6 must make the same edit to `test_0002`, because `_migrate(AFTER)` there goes to 0002, which is fine. The danger is `test_0001`, which targets 0001 explicitly now and so is fine. The risk is any test that uses `leaf_nodes()` as its "after" state. The `migrated_back_to_the_leaf` fixture is the only one, and it only restores, so it is safe.
- The 0002 test's untouched parametrisation uses `DeactivateCohortsBulkAction` at the old `actions.` path. That case stays valid. In the new 0003 test, the equivalent "untouched" cases should be a learner path (an already-moved `panels.learner.bulk_actions.AddToCohortBulkAction`), an unknown path, and the unregistered cohort base classes.

### Upgrade notes shape
- Front matter has all the keys: `requires_migrations: true`, `requires_template_review: false`, `changed_template_paths: []`, and so on.
- A "Breaking changes" section opens with a statement that no behaviour, URL, URL name, template path or app label changed and there is no re-export shim. It then lists, per destination module, every moved public name ("To `<new module>`:" / "From `<old>` to `<new>`:"). It notes any flat module that no longer exists. It warns that names still imported by flat code that stays will work for now, and that later refactors trim those imports. It says that underscore names are not public API and moved with the same spelling.
- A "Stored bulk action paths" subsection names the migration (`freedom_ls_educator_interface.0002_move_learner_bulk_runs`), lists each rewritten class, and says it matches whole paths only, has a reverse and runs on every site. It tells downstream projects that store or compare these paths to use the new ones.
- "Manual steps": run `uv run manage.py migrate`, and say what happens until then. Existing runs name a path that no longer imports. `action_for()` in `panel_framework/bulk_runs.py` returns `None` on `ImportError` or a non-`RecordedBulkAction` class, so a missed rename shows the run as "This action is no longer available" and does not crash. Then comes the grep advice for old dotted paths in `mock.patch` targets, with the "patch where it is looked up" examples and the warning that a stale string on an old module can still resolve and patch nothing. Last, "No settings, packages, templates or Tailwind rebuild are needed."
- Spec 4's notes (course) use `requires_migrations: false` and the same "From views to X" structure, listing private helpers separately.

### Why the migration is needed (code facts, from spec 5's research)
- `panel_framework/bulk_actions.py` records the path as `f"{type(self).__module__}.{type(self).__qualname__}"`, so future runs pick up the new path on their own. Only past runs need the migration.
- `panel_framework/bulk_runs.py` `action_for(run)` calls `import_string(run.action_path)` and returns `None` on failure. The failure is silent, so the migration test is the guard.
- `BULK_ACTIONS` is keyed by `(table_key, action_name)`, not by module. The registry keys do not change, only registration order matters.
- `BulkActionRun.action_path` is `CharField(max_length=255)`. `freedom_ls.educator_interface.panels.cohort.bulk_actions.DeactivateCohortRegistrationBulkAction` is about 90 characters, which is fine.

## 2. What differs for the cohort spec (for the spec author)
- It is the last large move, and the one that uses learner code. The import rule runs one way: `cohort` imports `learner`.
- `panels/cohort/data_tables.py` already exists with `CohortDataTable` and `LearnerCohortDataTable`. Spec 6 adds `CohortCourseRegistrationDataTable` and does not recreate the file.
- Most shared names were already moved to `common` by specs 1, 4 and 5.
- The shell `views.py` keeps `interface_config`, which imports `CohortConfig`, and `urls.py` keeps its other lines. Only the `cohort_report_download` line moves in this spec.
- The leftover flat cohort code in `views.py` and `actions.py` currently imports learner names from `panels/learner/`. Those imports die with the move.
- Report panels use `LazyBodyPanel` and `render_region` from `freedom_ls.panel_framework.lazy_panels`, and the badges from `panels/common/report.py`, which spec 1 created.

## 3. External references (brief, only where they add something)
- Django `RunPython`, reversibility and historical models via `apps.get_model`: <https://docs.djangoproject.com/en/stable/ref/migration-operations/#runpython>. The in-repo migrations follow this already, and the one point it adds is a real `reverse_code` instead of `noop`.
- Wagtail renamed page model data migrations (hand-written `RunPython` with forward and backward functions updating stored content-type rows): <https://docs.wagtail.org/en/7.1/reference/streamfield/data_migrations.html>. This is taken from spec 5's research and I did not re-verify it. The lesson that applies is to rewrite every table that stores the name and to roll back with its own function.
- Celery task renames (edX registered the function under both the old and new names for one deploy so queued messages were not dropped): <https://git.andalsoftware.com/Andal.LND/edx-platform/commit/b626a43fa1869f2cb8b70db51cfc1694c2029f59>. This is the alias/shim approach, which the idea rejects. A DB-stored path suits a one-shot data migration better. This too comes from spec 5's research and was not re-verified.
- Gap: I know of no external project that stores a dotted action path in a database column and moved it. The in-repo `0001` and `0002` migrations are the best precedent.

## 4. Checklist for spec 6
1. Role-named modules under `panels/cohort/` (`config`, `data_table_panels`, `panels`, `report_panels`, `instance_view`, `actions`, `bulk_actions`, `report_download`, `quick_view`) with a one-line docstring, `from __future__ import annotations`, absolute imports and a sorted `__all__`. `__init__.py` is empty, and `data_tables.py` is extended, not recreated.
2. Register the cohort bulk actions at startup by importing `panels.cohort.bulk_actions` from `panels/cohort/config.py` with `# noqa: F401` and a why-comment. Check the order of bulk actions for the cohort table against `main` in a fresh interpreter.
3. Grep-based import-direction checks as in spec 5, with the learner direction reversed, plus a fresh-interpreter import of every new module.
4. A first commit that moves shared cohort test helpers into `tests/helpers.py`, and repoints any cross-imports (check `tests/invariants/*` and `interface_walk.py`).
5. Migration `0003_<slug>.py`, modelled on `0002_move_learner_bulk_runs.py`. It has `_OLD`, `_NEW`, a `MOVES` list built from the registered classes (read from `@register_bulk_action`, not from the idea), a shared `_repoint` helper, exact-match filters, only `action_path` updated, and a real reverse.
6. Test `tests/migrations/test_0003_<slug>.py` built from `test_0002`, with `BEFORE` set to 0002 and `AFTER` to 0003, covering forward, `action_name` unchanged, reverse, untouched rows (a learner path, an unknown path, a row already on the new path) and an `import_string` resolvability check. Confirm `test_0001` and `test_0002` still pass with a new leaf above them.
7. Mirror the tests by module name, with `git mv` for whole files in a separate commit (`test_cohort_delete_action.py` to `test_actions.py`, `test_create_cohort_action.py` to `test_config.py`). A whole-file `git mv` into an existing name needs care, because `tests/panels/cohort/test_actions.py` will also receive the cohort slice of `tests/test_actions.py`. Do the `git mv` first and then append. Delete the two matching lines from `test_organisation/mirroring_baseline.txt` in the same commit. Re-read the baseline first, because only 6 lines are in the block now.
8. Repoint every `mock.patch` string at the module that looks the name up, then run one mutation check (point one string back at the old module and expect a failure). Add `panels.cohort.actions` to the `test_reason_mixin.py` walk and check the count still holds.
9. Record the collected-test count before the work and compare after. The expected delta is the new `test_0003` cases, plus any `_NEW_REPORTING_FILES` case.
10. Upgrade notes in the same format as spec 5: `requires_migrations: true`, per-module lists of moved names, the rewritten `action_path` values, the underscore-names caveat and the `mock.patch` grep step.
11. Do not touch `templates/`, `static/` or the `fls-dev` skill file path sweep (spec 7). `git diff main --stat` should show only one migration file added.

status: ok
