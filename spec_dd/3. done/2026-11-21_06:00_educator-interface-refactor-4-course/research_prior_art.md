# Research: prior art for moving the course area into `panels/course/`

Scope: repo history only (finished specs, sibling ideas, the parent effort's research, and a tree check). No web sources. No Bash or `git log` was available to this worker, so commit-level facts come from spec, plan, todo and QA files, not from commit messages or diffs. Gaps are marked.

## 1. What has already been tried

### 1.1 `educator-interface-refactor-1-scaffolding-and-common` (done 2026-11-20): the direct template

It moved shared helpers into `freedom_ls/educator_interface/panels/common/`: `request`, `badges`, `tables`, `ids`, `filters`, `actions`, `bulk_actions` and `report`. All eight modules exist in this tree. It was a pure move: no behaviour, URL, template or migration change, and no re-export shim. Its `upgrade_notes.md` lists every old and new dotted path, which is the shape this spec's upgrade notes should take. Its `todo.md` shows spec, plan, implement, document, PR and finish_worktree all ticked. `do_qa`, `qa_fix` and the user review items were never ticked, and there is no `qa_report.md` in its folder (no QA phase ran for a pure move). Nothing in the folder records a post-hoc bug fix, so I could not confirm or rule out fix commits from the files alone.

Conventions its plan settled (`2. plan.md`), which this spec should copy:

- **Slice by module.** Each slice is one commit that moves the code and repoints imports, then a second commit that moves the matching tests. Test moves are always their own commit.
- **`git mv` for whole-file test moves, with no content edits in that commit.** Edits that prepare the file, such as repointing an import, are done in place in the earlier code commit. Example: `test_denied_experience.py` had `OrganisationSectionConfig` repointed in the code commit, then `git mv`'d to `tests/panels/common/test_request.py` in the next commit. Slices cut out of big files (`test_actions.py`, `test_views.py`) have no rename detection, so the plan has the code commit and the test commit separate so a reviewer can verify the lines are identical.
- **Byte-for-byte moves.** Body, decorators, docstring and spelling (leading underscores included) are unchanged. Only import lines change. Unused imports left in the shrunk module are removed (ruff `F401` flags them).
- **New module shape.** Starts with `from __future__ import annotations` and a one-line purpose docstring that never says where the code came from, uses absolute imports only, and has a sorted `__all__` listing every moved name, underscore names included. `__init__.py` files are empty.
- **Module boundary rule.** `common` imports no flat module (`views`, `actions`, `filters`, `quick_views`, `reporting`) and no area package. It may import the flat `forms.py`. The course spec states the same rule for `course/` (imports only `common/`).
- **Patch strings.** After each slice, grep `patch|monkeypatch` for the moved names. A patch string must name the module that looks the name up, not the one that defines it.
- **Quoted casts** such as `cast("OrganisationScopedRequest", ...)` stay quoted.
- **Comments.** The stale `# TODO` block in `views.py` stays. Other `TODO` and `@claude` comments move with their code. No comment narrates the move or cites a spec.
- **Test helpers.**
  - A helper shared by a moving test and a staying test goes to `tests/helpers.py` under its existing name, and both files import it from there.
  - A helper only the moving tests use goes into the new test file.
  - A moved `autouse` fixture became a non-autouse `_site_context` fixture in `tests/conftest.py`, plus `pytestmark = pytest.mark.usefixtures("_site_context")` in both the old and the new test file. This avoids duplicating autouse fixtures after a split.
- **Tier discipline.** Before each commit, run `.claude/ds/scripts/select_tests.sh --working-tree` and the printed `command:` exactly, in the background (targeted tier). A final full-tier run uses `--range origin/main..HEAD`.
- **Pre-commit ordering.** The `test-mirroring` hook needs the production module to exist when its test file is committed, so the module lands in an earlier commit or the same one.
- **Collect-count guard.** `uv run pytest --collect-only -q --no-cov | tail -1` is recorded before the first change in `.sdd-work/collect_count_before.txt` and compared at the end. If a rebase brought tests from main, compare against `origin/main` plus the branch's moved-test count (net zero). The file is deleted by name afterwards.
- **Final slice (checks only).**
  - Leaf-rule greps over the new package (no imports of flat modules, none of other `panels.` areas, no relative `from .`).
  - A whole-repo grep that each moved name is defined only at its new home and imported nowhere at the old one.
  - `manage.py check` and `makemigrations --check --dry-run`.
  - A fresh-interpreter import of each new module and each flat module, via `uv run python -I -c` with `sys.path.insert(0, os.getcwd())` and `config.settings_dev`. This catches import cycles.
  - `pre-commit run --all-files` (runs `test-mirroring`, `lint-imports` and `app-map-fresh`).
  - `git diff main --stat` showing nothing under `templates/`, no `urls.py`, no migration.
- **Baseline edits are narrow.** The only `mirroring_baseline.txt` change was deleting the `test_denied_experience.py` line, and the plan asserts `git diff main -- test_organisation/mirroring_baseline.txt` shows only that.
- **Commit message style.** Imperative, naming the new home: `move the organisation request types into panels.common.request`, `move the VisibleCourseFilter tests beside panels.common.filters`. Fixups use `fix <what> after the panels.common move`.

### 1.2 `extract_panels_framework-1` to `-4` (done)

Closest earlier precedent: `-1-gather-generic-code` moved `ReasonMixin`, `LazyBodyPanel`, `render_region`, the bulk registry and the generic half of `EducatorBulkAction` out of `educator_interface`. It kept no aliases. Its plan rule: a slice that deletes or renames something greps for it before committing and leaves no reference behind, tests and comments included.

What went wrong or needed fixing:

- **Rebase cost, not code breakage.** Its frontend QA pre-step rebased onto 4 upstream commits and replayed 96 commits cleanly, and a lost-change check passed. A targeted tier run then failed once: `freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer`. It failed while QA drove the dev server and passed alone, so it was treated as a load flake. Lesson: do not run playwright-bearing tiers while a dev server is busy.
- **Rebase fallout needing human decisions** (from the parent research's reading of its `todo.md`): a new invariant exemption (`HAND_WRITTEN_TABLE_EXEMPTIONS`) was added during the rebase, and a leftover backup branch needed deleting.
- **Unrelated QA bugs.** B1 (a white table header band inside the import warning notice) stayed unresolved. B2 (the educator nav sheet's close control) was fixed. Neither relates to code layout.
- `-2` and `-3` QA reports show nothing import-related, only environment noise: a dev DB emptied by another process's post-rebase rebuild.
- `-4-template-contract` and `-1` produced `upgrade_notes.md` files. The course spec has no template or setting changes, so its notes are the simple "breaking path changes" kind from 1.1.

### 1.3 Other precedents

- `learner-terminology-rename` (done): bulk repointing was caught by tests, not by hand. 69 of 71 QA checks passed.
- `0001_rename_unregister_bulk_runs` migration: the precedent for changing a stored `BulkActionRun.action_path` (rename plus `RunPython`). The course area registers no bulk action, so there is no migration. The spec should show that with a grep for `register_bulk_action` and `RegisterBulkAction` under the course names.
- `extract_forms_into_seperate_app` research: check the app-level import graph before picking a home for shared bases. Not an issue here, since `panels/course` sits inside the same app.

## 2. Siblings in `spec_dd/2. in progress/`

- `educator-interface-refactor-2-dashboard-and-audit-log` and `-3-staff` have only `idea.md` and a blank `todo.md` (nothing ticked, no spec or plan yet). No lessons have been produced there. The course worktree is also at the start (this folder holds `idea.md`, `todo.md` and an empty `answers.md`).
- Remaining siblings still in `spec_dd/1. next/`: `-5-learner`, `-6-cohort`, `-7-cleanup`.
- All of 2 to 6 cut ranges from the same `views.py` and `tests/test_views.py` and add lines to the same import block. The prior art's remedy is to remove only your own ranges and keep the import block sorted and one-name-per-line, so conflicts stay mechanical.

## 3. Lessons from `spec_dd/1. next/educator-interface-refactor/` research

From `research_code_inventory.md`, `research_collisions.md` and `research_downstream_imports.md`:

- **Course area is `common`-only.** It uses `_interface_link`, `_registration_columns`, `_learner_column`, `uuid_or_404` (course preview) and `VisibleCourseFilter`. `CourseDetailsPanel` also uses `course_details_context`. No other area depends on course.
- **Outside importers of course names are only the two `qa_helpers` commands.**
  - `qa_create_course_cohort_registrations.py:50` imports `CourseCohortRegistrationDataTable`.
  - `qa_create_direct_course_registrations.py:42` imports `CourseLearnerRegistrationDataTable`. Its docstring at line 6 names `views.py`.
  - These break the moment the classes move, and nothing catches them in the educator tests. The refactor-1 research listed them as "area classes, not moved here", so refactor-1 left them alone and course must repoint them.
- **Baseline strings.** `test_organisation/import_baseline.txt:46` and `import_contracts.toml:197` name `freedom_ls.educator_interface.tests.test_course_visibility_and_interest` as a string. `mirroring_baseline.txt` carries that file as a line (line 38 in the idea; refactor-1 removed line 41 for `test_denied_experience.py`, so line numbers will have shifted and must be re-found by content, not number). The mirroring check also requires every new test file to have a matching module, so no test file for a module with no tests.
- **String patch targets fail silently.** About 29 `mock.patch` and `monkeypatch` strings name `freedom_ls.educator_interface.*` across the two big test files. Wrong namespace patches either raise `AttributeError` or silently patch nothing. A patched name that is never exercised passes silently.
- **No shim.** A shim would keep the `views` import cycle alive and does not solve persisted paths. `interface_config` is imported lazily from `views` by `actions`, `filters`, `quick_views` and `reporting`. That stays.
- **Test-file split (from the inventory).** `test_course_visibility_and_interest.py` (262 lines, 8 tests) goes to `panels/course/test_data_tables.py` and `test_panels.py`. The course slices of `test_views.py` are about 675-820 and 7699-8558 (~1000 lines). The inventory's target tree lists `course/` test files as `test_data_tables.py`, `test_panels.py` and `test_content_preview.py`. The idea extends that to `test_config.py`, `test_data_table_panels.py` and `test_instance_view.py`, where tests exist.
- **`instance_view` for course is a file, not a package.** It is about 10 lines (`CoursePanelStack` and `CourseInstanceView`).
- **Naming.** The idea's `course_staff` area became two areas, `course` and `staff`.

## 4. Current tree, as checked by this worker (staleness of the idea's ranges)

- `panels/common/` exists with eight modules, so the dependencies the idea names are available. Nothing under `panels/` exists for any area yet. Siblings 2 and 3 have not landed.
- The idea's line ranges are stale. In this tree: `CourseDataTable` is at `views.py:1848`, `CourseDetailsPanel` at 1962, `OutlineRow` at 2008, `outline_rows` at 2118, `CoursePanelStack` at 2452, `CourseInstanceView` at 2461 and `CourseConfig` at 2465. The idea says 1882, 2005, 2051, 2181, 2403, 2412 and 2416. The drift is about -40 to +50. `test_views.py` now runs past line 8968, versus 8558 in the idea. The spec must re-grep, and the plan should repeat that at implementation time.
- **Open question resolved: `OutlineRow` and `outline_rows` have no importer outside `views.py`.** The grep over `freedom_ls/` finds `views.py` (definitions and uses), plus unrelated hits:
  - `tests/test_views.py` has a different helper named `_outline_rows` (an HTML row finder, lines 8044-8968).
  - `tests/playwright/test_course_preview_flow.py:162,167` has a local variable named `outline_rows`.
  - `learner_interface/tests/views/test_course_player.py:5106` is a test name containing the words.
  - So a naive grep for `outline_rows` over-reports. Grep with `-w` and `import` context.
- A grep for `patch`/`monkeypatch` lines naming the course names (`Course*`, `outline_rows`, `PreviewContent`, `_form_preview_context`, `CourseConfig`) under `freedom_ls/` found no match. That suggests no course-name patch string exists today, but a patch string can name the module with the object on a separate line, so the spec's grep should also search for `"freedom_ls.educator_interface.views."` strings and check each against the course names.

## 5. Risk list for this spec (what went wrong or was nearly wrong before, applied here)

1. **Silent patch misses.** Check every `educator_interface.views.<name>` string against the course names, and prove coverage by running the targeted tier, since an unexercised patch passes silently.
2. **qa_helpers missed imports.** Two commands break with no failing test. Repoint them in the same slice as `data_tables.py`, and grep `freedom_ls/qa_helpers/` for every moved name.
3. **Baseline checker failures.** `mirroring_baseline.txt`, `import_baseline.txt` and `import_contracts.toml` fail on stale lines. Edit by content, not line number, and run `pre-commit run --all-files` (`test-mirroring`, `lint-imports`, `app-map-fresh`). If the split leaves no file importing `course_interest.factories`, delete the line, otherwise name each new importer.
4. **Import cycles.** Verify with a fresh-interpreter import of each new module and `views.py`. `course/` must import only `common/`. `instance_view.py` must not import `views`. `interface_config` in `views.py` names `CourseConfig`, so the import direction is `views -> course`, never the reverse.
5. **Rebase conflicts in `views.py` and `test_views.py`.** Siblings cut neighbouring ranges and add to the same import block. Cut only course ranges, keep imports sorted and one name per line, and keep test moves in their own commit so renames survive.
6. **Test fixture breakage.**
   - Helpers used by both the moved course tests and staying tests must go to `tests/helpers.py`. Course-only helpers move with the tests.
   - Autouse fixtures in `test_views.py` must not be duplicated. Use the non-autouse `_site_context` fixture from `tests/conftest.py` with `pytestmark` where a new file needs site context.
   - `tests/panels/course/__init__.py` must exist (`tests/panels/__init__.py` came from refactor-1).
7. **Unused import residue.** Ruff `F401` in `views.py` and `test_views.py` after each cut.
8. **Not mentioned elsewhere:** the course tests in `test_views.py` include a module-level `_outline_rows` helper (line 8044) used from several tests. If those tests split across `test_content_preview.py` and `test_instance_view.py`, the helper needs to land in `tests/helpers.py` or stay beside only one file.

## 6. References

All internal files:

- `spec_dd/3. done/2026-11-20_09:37_educator-interface-refactor-1-scaffolding-and-common/` (`2. plan.md`, `upgrade_notes.md`, `todo.md`, `research_prior_art.md`)
- `spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/qa_report.md`
- `spec_dd/1. next/educator-interface-refactor/research_code_inventory.md`, `research_collisions.md`
- `spec_dd/2. in progress/educator-interface-refactor-3-staff/todo.md`

status: ok
