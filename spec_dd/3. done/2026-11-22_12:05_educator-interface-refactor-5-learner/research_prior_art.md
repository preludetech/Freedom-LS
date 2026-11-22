# Research: prior art for moving the learner area into `panels/learner/`

Scope: repo-internal specs (done 1 and 2, in-progress 3 and 4, the effort research, `extract_panels_framework-1`) plus brief outside notes. No Bash was available, so no `git log` was read. Done specs 1 and 2 have no `qa_report.md` or bugfix notes: their `todo.md` files show `do_qa` and `qa_fix` unticked (spec 2 has no frontend QA plan, so QA was skipped as nothing in the UI changed). The only recorded evidence is each spec's research, plan, upgrade notes and todo.

## 1. What has been tried here

**`extract_panels_framework-1-gather-generic-code` (done 2026-11-16)** is the precedent for a clean break with no re-export shim.
- Plan rule: a slice that deletes or renames greps for the old name before committing and leaves no reference behind, tests and comments included. Moved files used `git mv`. `TODO` and `@claude` comments moved with their code.
- QA found no move-related breakage. The costs were rebase fallout: 4 upstream commits, a 96-commit replay that was clean, a new invariant exemption (`HAND_WRITTEN_TABLE_EXEMPTIONS`) added during the rebase, and a leftover backup branch.
- Specs 2 and 3 of that effort QA'd with only environment noise (a dev DB emptied by another process).

**`educator-interface-refactor-1-scaffolding-and-common` (done 2026-11-20)** made `panels/common/` (8 modules) and `tests/panels/common/`.
- One slice per module. One commit moves the code and a second moves its tests. Whole-file moves use `git mv` with no content edits.
- The move is byte-for-byte; only imports change. New modules start with `from __future__ import annotations`, a purpose-only docstring and a sorted `__all__`. Every `__init__.py` is empty. A module never imports a flat module or a sibling area.
- Its last slice ran the gates: leaf-rule greps, a repo-wide grep per moved name, `manage.py check`, `makemigrations --check`, a fresh-interpreter import of each new module, collect-count equality and `pre-commit run --all-files`.
- What went wrong: shared helpers were first added to `tests/helpers.py` untyped, and a fix-up commit (77187808a, "type the shared test helpers...") followed. Type-hint moved helpers from the start.
- Shared autouse fixture: `tests/test_filters.py` had an autouse `_site_context`. Spec 1 made it a non-autouse fixture in `tests/conftest.py` plus `pytestmark = pytest.mark.usefixtures("_site_context")` in the staying and the moved file. The learner filter tests will meet the same fixture.
- Mirroring baseline: it deleted exactly one line (`test_denied_experience.py`) and left nine.
- The idea's line ranges were stale by about 90 lines or more because extract-1 had landed. Spec 2 found them stale again after spec 1.

**`educator-interface-refactor-2-dashboard-and-audit-log` (done 2026-11-20)** moved `DashboardPanel` and the audit log into `panels/dashboard/` and `panels/audit_log/`.
- Placement rule: an area imports only `panels/common/`, `panel_framework`, the leaf `educator_interface.avatars` and other apps. It never imports `views`, `reporting`, `filters`, `actions`, `quick_views` or a sibling area. Checked by grep, with no new import-linter contract. Inside an area, imports run one way (`filters` <- `data_tables` <- `data_table_panels` and `config`).
- The `views.py` import block was kept alphabetical, one name per line, so sibling merges stay clean.
- The old-name path still resolves: `views.py` imports `HistoryPanel` and `TargetedAuditLogEntryTable` for its own subclasses, so `from ...views import HistoryPanel` keeps working. A stale `mock.patch` string on `views` still resolves and patches nothing, so a test can pass without patching what it meant to. Its upgrade notes tell downstream users not to rely on it. Its plan added a manual check: repoint the `learner_avatars` patch string back at `reporting` and watch the dashboard test fail.
- A planned `AuditPeriodFilter` no longer existed (extract-1 had generalised it to the framework's `PeriodFilter`). Re-derive every name by grep, not from the idea.
- Open follow-ups in its `todo.md`: a force-push after the rebase was declined by the permission system, so origin held the pre-rebase branch until a user pushed (`git push origin HEAD --force-with-lease --force-if-includes`). It also records a PR #265 review finding of an N+1 (`_gather_visible`), which predates the move.
- Known flakes that are not move-related: `freedom_ls/audit_log/tests/test_actions.py::test_course_progress_actions_describe_their_details` fails in loaded full runs and passes alone. `needs_fls_host` tests in `panel_framework/tests/test_reference.py` fail under xdist ("basename user already registered"). The playwright `test_quick_view_drawer` fails under load.

**Specs 3 (staff) and 4 (course) are ideas only** (`todo.md` has nothing ticked), so there is nothing to learn from their outcome yet. Their ideas show the conventions this spec should match:
- Both say "no migration", because none of their classes is `@register_bulk_action`. Only specs 5 and 6 add a migration.
- Both use the same patch rule (repoint at the module that looks the name up; attribute patches on the module object fail silently, so run the tests) and "test files move in a commit of their own".
- Spec 3 keeps the lazy `interface_config` import function-level (`refusal_response`) and only repoints its dotted path. Spec 5 does the same ("stays lazy in the staff block this spec does not touch").
- Spec 4 also edits `import_baseline.txt` and `import_contracts.toml`, because a split test file moved an importer of `course_interest.factories`. Check whether any moved learner test file has an entry in either file, not only in `mirroring_baseline.txt`.

**Stored-path migration precedent.** `0001_rename_unregister_bulk_runs.py` is a `RunPython` on `apps.get_model("freedom_ls_panel_framework", "BulkActionRun")`. It filters on `action_path` and updates `action_path` and `action_name`, and it depends on `("freedom_ls_panel_framework", "0001_initial")`. Its reverse is `migrations.RunPython.noop`. Spec 5's requirement differs in two ways: the reverse must be real, and `action_name` stays untouched. The existing test is `tests/migrations/test_0001_rename_unregister_bulk_runs.py`. Note too that 0001 still names the old `freedom_ls.educator_interface.actions.<Name>` for `DeactivateRegistrationBulkAction`, which is one of the 7 paths spec 5 rewrites. A fresh database runs 0001 then the new migration in order, so the chain still ends at the new path, but 0001 must not be edited.

## 2. Failure modes recorded in the effort research, applied to this spec

- **Silent patch strings** (`research_collisions.md`, `research_downstream_imports.md`). About 22 `monkeypatch.setattr`/`mock.patch` sites in `tests/test_actions.py` and several in `tests/test_views.py` name `...actions.<helper>` or `...views.<name>`. The learner share is the largest (`move_between_cohorts`, `record_learner_entry`, `own_conversation_with`, `send_message`, `MAX_UPLOAD_BYTES`). If a flat module imports a name with `from x import y`, a patch must target that flat module, not the defining one. State per patch which namespace does the lookup. Guard: run the whole `educator_interface` test directory, because a patch on a name never called still passes.
- **Cycles that move instead of ending.** Spec 1 flagged this for `common`. Here the learner-cohort cycle is the point of the spec. The planned fix (`panels/cohort/data_tables.py` imports only `panels/common`; membership actions live in `learner/actions.py`; learner imports nothing from cohort) is checkable by grep. `visible_registrations_with_progress` and cohort-owned helpers (`inactive_cohort_response`, `cohort_not_empty_sentence`) are the open leaks. Learner modules also import `HistoryPanel` from `panels/audit_log/`, never from `views` (spec 2 has landed, so it exists).
- **Stale ranges.** Treat every V:/A:/R: range in the idea as stale. Locate by class name.
- **Mirroring baseline.** Removing `test_learner_section.py` is one line. The check needs a production module for each test file, and an `__init__.py` at each level of `tests/panels/learner/` and `tests/panels/cohort/`. Spec 6 will recreate nothing in `cohort/data_tables.py`, so the file spec 5 creates there needs its `tests/panels/cohort/test_data_tables.py` and `__init__.py` for the `cohort` test directory (spec 6 must not recreate either).
- **Merge collisions with parallel specs.** Specs 3, 4 and 5 may run in parallel, cutting from the same `views.py`, `actions.py`, `test_views.py` and `test_actions.py` and editing the same import block. Rules from spec 2: each moved test removes only its own range, imports stay alphabetical and one per line. Re-check what landed on main before cutting. Later landers rebase onto the shrunk files.
- **Persisted paths.** Only `@register_bulk_action` classes matter. Confirm the exact list of seven by grep, and confirm none of the `BulkActionRun`-adjacent helpers (the base classes `LearnerBulkAction`, `CohortMembershipBulkAction`, `LearnerStateBulkAction`, `CourseRegistrationBulkAction`) are registered. `CoursePickerMixin` is already in `panels/common/bulk_actions.py`.

## 3. Lessons to bake in

1. Re-derive names and ranges by grep on the current tree and record them in the spec.
2. One commit moves code, a second moves its tests. `git mv` whole files with no edits. Slices cut from the 8k-line `test_views.py` and 9k-line `test_actions.py` have no rename detection, so keep them pure cut and paste.
3. After each slice, grep the whole repo (code, tests, patch strings, `claude_plugins/fls-dev` skills, docs, `templatetags/educator_tags.py`, `tests/playwright/test_learners_list_flow.py:18`) for the old dotted path.
4. Run the whole `educator_interface` test directory, not just moved tests. Use the manual "point one patch string back at the old module" check to prove the patch strings bite.
5. Type-hint moved test helpers from the start. Reuse the `_site_context` fixture-plus-`pytestmark` pattern.
6. Gates: leaf-rule greps (learner imports no `panels/cohort/` module), `manage.py check`, `makemigrations --check`, fresh-interpreter `python -I` import of every new module, collect-count equality, `pre-commit run --all-files` (`test-mirroring`, `lint-imports`, `app-map-fresh`).
7. Migration: model on 0001 but with a real reverse and no `action_name` change. Test forward, reverse and untouched rows (including a cohort bulk action row, which spec 6 will move later, and a row that already has the new path). Set `requires_migrations: true` in `upgrade_notes.md`. Name the move in the upgrade notes the way spec 2 did (old module to new module, per name, plus the "grep your `mock.patch` strings" step).
8. Expect a post-rebase force-push to need a user. Do not assume the agent can push a rebased branch.
9. Do not blame the known flakes (section 1) on the move. Check them against their known status first.

## 4. Elsewhere: big-module splits and stored-path renames

- Patch where the name is looked up: Python `unittest.mock` docs, "Where to patch". The same trap as the silent patch strings above. https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- Moving a name leaves `from old import X` working only while the old module still imports it. This is how the stale-patch-string failure hides. Removing the old import is the only way to make a stale reference fail loudly. Django's own deprecation practice is to keep shims for a release cycle, which this effort deliberately skips (no shim, so a downstream project must repoint).
- Stored dotted paths (Celery task names, `ContentType`, pickled classes, generic `import_string` settings) break when a class moves. The usual fix is a data migration or a name alias. Django's `RunPython` docs recommend a reverse function, or `RunPython.noop` only when reversing is safe. https://docs.djangoproject.com/en/stable/ref/migrations/operations/#runpython
- A data migration should use `apps.get_model` (historical models), not an import of the real model, so a later model change cannot break it. 0001 already does this.
- Circular imports from splitting a big module: the common advice is to move shared code down into a leaf module that both sides import, not to use lazy imports. That is the approach this spec plans. https://docs.python.org/3/faq/programming.html#what-are-the-best-practices-for-using-import-in-a-module
- Merge conflicts from parallel branches that cut the same file: keep each move to whole, contiguous blocks, keep import blocks sorted, and use `git mv` for whole-file moves in their own commit so rename detection survives a rebase (the hygiene roadmap states the same rule).

None of these URLs was fetched in this run. They are well-known documentation pages, cited from memory.

status: ok
