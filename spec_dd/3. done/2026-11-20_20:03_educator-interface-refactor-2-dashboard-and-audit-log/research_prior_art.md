# Research: prior art for moving the dashboard and audit log areas into `panels/`

Scope: repo-internal. Read `idea.md`, the done specs for `educator-interface-refactor-1-scaffolding-and-common` and `extract_panels_framework-1/2/3`, and the current tree. No web search was run. The Bash tool was unavailable, so `git log` on `panels/` and `tests/panels/` was not run. See section 5.

## 1. What spec 1 did and what it left behind

Spec 1 (done 2026-11-20) created `panels/common/` with 8 modules: `request`, `badges`, `tables`, `ids`, `filters`, `actions`, `bulk_actions`, `report`. It created `tests/panels/common/` with `test_request`, `test_badges`, `test_filters`, `test_report` and `test_bulk_actions`. `todo.md` shows the QA step skipped (`do_qa` and `qa_fix` unticked), so **there is no QA or bugfix report for spec 1**. The only recorded feedback is its research and plan.

Its method is the template for this spec:
- One slice per module. Code move is one commit and the test move is its own commit. Whole-file moves use `git mv` with no content edits, so rename detection survives a rebase (`2. plan.md` ground rules).
- The move is byte-for-byte. Only import lines change.
- New modules begin with `from __future__ import annotations`, a purpose-only docstring and a sorted `__all__`. `__init__.py` files stay empty. A module never imports a flat module or a sibling area.
- No re-export shim (`upgrade_notes.md`). Old modules may still resolve a moved name only because they import it for their own use. The notes tell downstream users not to rely on that.
- Final slice 9 ran leaf-rule greps, a whole-repo reference grep per moved name, `manage.py check`, `makemigrations --check`, a fresh-interpreter import of every new module, a collect-count comparison and `pre-commit run --all-files`.
- A late fix-up commit exists in the log: "type the shared test helpers and reword the _site_context docstring" (77187808a). Moved helpers were added to `tests/helpers.py` untyped, and the CLAUDE.md type-hint rule caught it afterwards. Plan this spec's helper moves with type hints from the start.
- A shared autouse fixture caused a design choice. `tests/test_filters.py` had an autouse `_site_context`. Spec 1 turned it into a non-autouse fixture in `tests/conftest.py` plus `pytestmark = pytest.mark.usefixtures("_site_context")` in both the staying and the moved file. Slice 5 of the plan covers this. **Spec 2 moves audit filter tests out of `tests/test_filters.py`, so it will meet the same fixture. Reuse the pattern.**
- The same plan moves shared helpers to `tests/helpers.py` under their existing underscore names. The moved test imports them from `freedom_ls.educator_interface.tests.helpers`.

## 2. Failure modes recorded in the specs, and how each applies here

**Patch strings fail silently.** `research_collisions.md` and spec 1's `research_prior_art.md` flag this as the top risk. A `mock.patch` or `monkeypatch` on the wrong module either raises `AttributeError` or patches a namespace nothing reads. Patch the module that looks the name up. Spec 1's plan found no patch string naming a moved name, which was luck, not design. For spec 2 the exposure is real:
- `tests/test_views.py` has the `educator_views.*` references named in the idea (about 7089-7109, now shifted).
- The count of `educator_views.` or `educator_interface.(views|reporting|filters).<Name>` strings is 16 in `test_views.py`, 2 in `test_reporting.py` and 1 in `test_dashboard.py` (regex count, not a precise audit). Re-grep at plan time and read each hit.
- `test_views.py:7489` parametrises over `educator_views.LearnerHistoryPanel` and `educator_views.CohortHistoryPanel`. Those two stay in `views.py`. Only the audit tables and `HistoryPanel` entries repoint.
- A patch on a name that the code under test never calls still passes. Spec 1 proposed running the full `educator_interface` tests, not just the moved ones, as the guard.

**Stale line numbers.** Spec 1 found the idea's ranges off by about 90 lines or more because `extract_panels_framework-1` had landed. Spec 1 landing has shifted them again. Current tree: `HistoryPanel` is at `views.py:997`, `LearnerHistoryPanel` at 1042, `CohortHistoryPanel` at 1695, `DashboardConfig` at 2482 and `AuditLogConfig` at 2691. The idea gives 1031-1075, 2436 and 2639. `DashboardPanel` is at `reporting.py:465` (idea: 332-560). Move by class name.

**The idea's `AuditPeriodFilter` no longer exists.** `filters.py` holds only `AuditActorFilter` (line 159) and `AuditActionFilter` (line 195). No `AuditPeriodFilter` class is defined anywhere in `freedom_ls`. The audit table builds its period filter with the framework's `PeriodFilter` directly (`views.py:881`). The idea already anticipates this ("move whatever audit filter classes remain"). The audit filter tests start at `audit_request` (`tests/test_filters.py:510`, not about 557). Tests import `AuditActionFilter` and `AuditActorFilter` from `filters` at lines 19-20, so those imports repoint.

**Mirroring baseline.** The `test-mirroring` hook needs the production module to exist when its test file is committed. So the production module lands in an earlier commit or the same one. Spec 1 deleted exactly one baseline line (`test_denied_experience.py`) and left nine. Here `freedom_ls/educator_interface/tests/test_dashboard.py` is line 40 of `test_organisation/mirroring_baseline.txt`. Delete only that line. A new test file is created only beside a module it mirrors. `test_filters.py`, `test_data_tables.py` and `test_data_table_panels.py` each need a matching module (`panels/audit_log/filters.py`, `data_tables.py`, `data_table_panels.py`). `test_config.py` needs `config.py`. Note that the mirroring check also covers the other directions: an `__init__.py` is needed at every level (`tests/panels/dashboard/` and `tests/panels/audit_log/`).

**Circular imports.** Spec 1 cleared the `TYPE_CHECKING` imports of `OrganisationScopedRequest` from `views`. Its warning: if a new module imports from `views`, the cycle only moves. `interface_config` is imported lazily from `views` in several flat modules and has to stay lazy. Risks specific to spec 2:
- `HistoryPanel` is at `views.py:997`, and `LearnerHistoryPanel` and `CohortHistoryPanel` in `views.py` subclass it. After the move, `views.py` imports `HistoryPanel` from `panels/audit_log/data_table_panels.py`. That module must not import `views`.
- `TargetedAuditLogEntryTable` is also drawn by the cohort History panel. Same rule.
- `views.py` builds `NavGroup(... [DashboardConfig, ...])` and `[StaffConfig, AuditLogConfig]` at import time (lines 2728-2730). The new `config.py` modules are imported by `views.py`. They must not import `views` back. Use `panels.common.request.OrganisationSectionConfig`, which already exists.
- `reporting.py` currently holds `DashboardPanel` and its figures. `LearnerCoursesPanel` and the cohort report classes stay there. Check that nothing staying in `reporting.py` uses a name that moves to `panels/dashboard/panels.py`. If so, that is a reverse import from `reporting` to the dashboard area, a cycle with a sibling.
- The dashboard imports `LazyBodyPanel` and `render_region` from `freedom_ls.panel_framework.lazy_panels` (spec 1 corrected the sibling ideas to say so).
- Spec 1 slice 9 imports every new module in a fresh interpreter with `python -I` and `django.setup()`. Do the same for the six new modules and `views`, `reporting` and `filters`.

**Migrations.** Spec 1 used the `0001_rename_unregister_bulk_runs` precedent to show that only a moved `@register_bulk_action` class changes the stored `BulkActionRun.action_path`. Verify by grep that none of the moved classes carries `@register_bulk_action`. `_record_export` is a function, not a bulk action. Check it anyway, because exports have a recorded run id in `_export_run_id`.

**Merge collisions.** `research_collisions.md` says specs 2, 3 and 4 of the effort cut ranges from `views.py` and `test_views.py` and edit the same import block. Rules: each moved test removes only its own range. Keep imports alphabetical and one name per line. Landing order is decided by the roadmap. Reconfirm what has landed on main before cutting.

## 3. What `extract_panels_framework-1/2/3` taught

- Spec 1 (done 2026-11-16): the plan rule "a slice that deletes or renames something greps for it before committing and leaves no reference behind, tests and comments included". Moved files used `git mv`. `TODO` and `@claude` comments move with their code. Recorded costs:
  - A rebase over 4 upstream commits (96 commits replayed cleanly, lost-change check passed).
  - A new invariant exemption (`HAND_WRITTEN_TABLE_EXEMPTIONS` in `panel_framework/tests/invariants/test_templates.py`) added during the rebase.
  - A leftover backup branch `extract_panels_framework-1-rebase-wip`.
  - A single failure: `panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer`, which failed under load while QA drove the dev server and passed alone. Spec 2 touches no browser test, but a full-tier run may hit the same load flake. `tests/playwright/test_audit_log_flow.py` stays put.
- Spec 2 (done 2026-11-18): no import-related QA failures.
- Spec 3 (done 2026-11-19): environment noise only. The dev DB was emptied by another process's post-rebase rebuild, so the first load of `/` returned 500 until the QA data helper reseeded it. The `todo.md` also records two known flakes unrelated to import moves, which are likely to appear in a full-tier run and should not be blamed on this move:
  - `freedom_ls/audit_log/tests/test_actions.py::test_course_progress_actions_describe_their_details` fails in loaded full runs and passes alone.
  - xdist-only failures of `needs_fls_host` tests in `panel_framework/tests/test_reference.py` ("DRF 'basename user already registered'"). Both are spun off as separate ideas.
  The audit log area is exactly what the first of these touches, so a failure there needs checking against its known-flaky status before it is attributed to this move.
- Other repo precedents:
  - `extract_forms_into_seperate_app` research: check the app-level import graph before choosing a home (the `base` and `site_aware_models` cycle). Not an issue here, since everything stays in one app.
  - `learner-terminology-rename`: 69 of 71 QA checks passed. Bulk repointing was caught by tests, not by hand.

## 4. Concrete lessons for the spec and plan

1. Re-derive every name and range by grep on the current tree. The ranges in the idea are stale twice over. `AuditPeriodFilter` is absent.
2. One commit moves code, a second commit moves its tests. `git mv` whole files without edits. Cuts from `test_views.py` (about 7.7k lines) and `test_filters.py` have no rename detection, so keep them reviewable as pure cut and paste.
3. Check `test_reporting.py` and `test_dashboard.py`. The idea leaves open whether `test_reporting.py` has dashboard tests: two `educator_views.`/`reporting.` hits exist there, so read them. The `test_dashboard.py` hit count is 1.
4. Patch strings name the looking-up module. Grep `patch|monkeypatch|educator_views\.` for every moved name across `freedom_ls/`, `claude_plugins/` and `config/`. Run the whole `educator_interface` test directory, not only the moved tests.
5. Type-hint every helper moved into `tests/helpers.py`. Reuse the non-autouse `_site_context` fixture plus `pytestmark` pattern for the audit filter tests.
6. Delete only the `test_dashboard.py` baseline line and run the mirroring check.
7. Run the slice-9 style gates: leaf-rule greps, no-old-reference greps, `manage.py check`, `makemigrations --check`, fresh-interpreter imports, collect-count equality, `pre-commit run --all-files` (`test-mirroring`, `lint-imports`, `app-map-fresh`).
8. Plan for the full-tier flakes in section 3 so they do not mislead.

## 5. Gaps and external accounts

- `git log` over `freedom_ls/educator_interface/panels/` and `tests/panels/` was not run (no Bash). The one fix-up commit seen in the supplied log is 77187808a (typing the shared test helpers). A reader with Bash should run `git log --oneline -- freedom_ls/educator_interface/panels freedom_ls/educator_interface/tests/panels` to look for other fix-ups.
- No external account was fetched. General background, unsourced and not verified here: large Python module splits commonly break on patch targets ("patch where it is looked up", from the `unittest.mock` documentation), on import cycles that move instead of ending, and on merge conflicts with parallel branches. The repo's own specs already name all three, so no outside source changes the plan.

status: ok
