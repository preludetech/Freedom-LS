# Research: prior art for the `panels/common/` move

Scope: repo-internal only (completed specs, parent effort notes, roadmap). No web sources. Bash was
unavailable, so `git log` was not searched; findings come from spec files and a tree check.

## 1. What has been tried

- `extract_panels_framework-1-gather-generic-code` (done 2026-11-16) is the closest precedent: it moved
  `ReasonMixin`, `LazyBodyPanel`, `render_region`, the bulk registry and the generic half of
  `EducatorBulkAction` out of `educator_interface`, with "old import paths not kept as aliases". Its plan rule
  (`2. plan.md` line 48): "a slice that deletes or renames something greps for it before committing and leaves no
  reference behind, tests and comments included". Moved files used `git mv`, and `TODO` and `@claude` comments
  "move with their code and stay". A new module gets its `__all__` when created.
- Its QA report found no move-related breakage. The only cost was a rebase: 4 upstream commits, a clean replay
  of 96 commits, and a "lost-change check" passed (`qa_report.md` line 15). Its `todo.md` shows rebase
  fallout that needed human decisions: a new invariant exemption (`HAND_WRITTEN_TABLE_EXEMPTIONS`) added during
  the rebase, and a leftover backup branch to delete.
- `extract_panels_framework-2` and `-3` QA reports show nothing import-related. Only environment noise: a dev
  DB emptied by another process's post-rebase rebuild.
- `extract_forms_into_seperate_app` research flagged one trap: putting shared bases in `base` would create a
  real cycle (`base -> site_aware_models` against `site_aware_models -> base`). Lesson: check the app-level
  import graph before choosing a home. Here `panels/common` sits inside the app, so there is no new app edge,
  but `common` must not import from flat `views.py`/`actions.py`.
- `learner-terminology-rename` (done): 69 of 71 QA checks passed, 0 failed. Its bulk repointing was caught by
  tests, not by hand. The two skips came from dev settings.
- The `0001_rename_unregister_bulk_runs` migration is the precedent for changing a stored
  `BulkActionRun.action_path` (rename with a `RunPython` update). That is why this spec, which moves no
  registered action, needs no migration. It must prove that: `EducatorBulkAction` and `CoursePickerMixin` are
  bases, not `@register_bulk_action` classes (verify by grep before committing).

## 2. Tree check: extract-1 has already landed, so the idea's line ranges are stale

The idea says its ranges are "main's" from before extract-1. Current tree (this worktree):
- `actions.py:379 EducatorReasonMixin(ReasonMixin)`, `:2829 EducatorBulkAction(PermittedBulkAction[User])`,
  `:3084 CoursePickerMixin` (idea says 3379).
- `views.py:256 OrganisationScopedRequest` (idea says 249-327 for the block), `views.py:1390 uuid_or_404` (idea
  says 1301-1308). Ranges have drifted by about 90 lines or more.
- `ShowInactiveFilter`, `LazyBodyPanel` and `render_region` no longer match as `^class`/`^def` in
  `educator_interface` (the research notes say they went to the framework). So the conditional placements
  in the idea ("only if it still exists") resolve to "no" for those three. Confirm for `ShowInactiveFilter`
  with a broader grep, because this check only looked at top-level definitions.
- Lesson: locate every name by grep at implementation time and ignore the idea's line numbers. Record the
  re-derived ranges in the spec.

## 3. Lessons from the parent research

From `research_collisions.md` and `research_downstream_imports.md`:
- **String patch targets fail silently.** `monkeypatch.setattr` and `mock.patch` on a moved module either raise
  `AttributeError` or patch the wrong namespace. About 22 sites in `tests/test_actions.py` (for example lines
  2494, 3388, 3591 ... 9424), plus `tests/test_views.py` 3610, 3641, 4802-4882 and 5543, patch `...actions.<helper>`
  or `...views.<name>`. A patch must name the module that looks the name up, not the module that defines it.
  Re-grep: line numbers shifted after extract-1. Search `"freedom_ls.educator_interface.(views|actions|filters|reporting|quick_views)\.` across
  the whole repo, including `qa_helpers`, `conftest.py` and playwright tests. A helper moved to `common/actions.py`
  but called from a flat `actions.py` function is still patched at `flat actions.<name>` if the flat module
  imported it by name (`from ...common.actions import _picker_on_get`). The spec must say which.
- **Importers outside the flat modules** (from section 3 of downstream imports): `qa_helpers` commands import
  `CourseCohortRegistrationDataTable` and `CourseLearnerRegistrationDataTable` from `views`. Those are area
  classes, so they are not moved here and stay untouched. `educator_tags.py:7-8` and `tests/interface_walk.py:20-21`
  are repointed here. The first-party consumer First-Class-LMS imports none of the moved modules, so no
  downstream change is needed (`urls.py` and `INSTALLED_APPS` only).
- **No shim, because** a shim would keep the `views` cycle alive and does not solve persisted paths. The
  `TYPE_CHECKING` imports of `OrganisationScopedRequest` (4 files) are the visible symptom to remove.
- **Lazy imports.** `interface_config` is imported lazily from `views` (`actions.py`, `filters.py`,
  `quick_views.py`, `reporting.py`) and stays that way. Moving `OrganisationScopedRequest` into `common.request` makes
  the `TYPE_CHECKING` imports ordinary, but `common/request.py` itself holds `OrganisationSectionConfig`.
  Make sure `common/request.py` imports nothing from `views`, or the cycle moves instead of ending. (Its
  `interface_config` reference, if any, is the one to check.)
- **Mirroring baseline.** `test_organisation/mirroring_baseline.txt` lines 36-46 list 10 `educator_interface`
  entries. `test_denied_experience.py` is line 41. Removing it is the only line to delete. The mirroring check
  must pass after the move: every new test file under `tests/panels/common/` needs a matching module, and
  every module that gets a test slice needs a matching file. Don't invent test files for `tables`, `badges` or
  `ids` unless a slice exists. A new `tests/panels/` directory also needs `__init__.py` at each level.
- **Rename detection.** The hygiene roadmap rule: "move test files in a commit of their own so the rename survives
  a rebase". `git mv` a whole file (for example `test_denied_experience.py` -> `panels/common/test_request.py`)
  in its own commit with no edits. Slices cut from big files (`test_actions.py`, 9.8k lines) have no rename
  detection and can only be reviewed as cut-and-paste. Do each slice as: one commit that moves the code, one
  that moves its tests, so a reviewer can verify the lines are identical.
- **Parallel spec collisions** (roadmap): `-2`, `-3` and `-4` all cut ranges out of `views.py`, `actions.py`,
  `test_views.py` and `test_actions.py` and add lines to the same import block. This spec runs first and alone, so
  its risk is the reverse: it must not leave the old import block in a shape that conflicts mechanically.
  Keep the import block alphabetical and one-name-per-line (or per project formatter) so sibling merges
  stay clean. Landing `learner-public-profile-1-profile-picture` first (it edits `views.py` select_related
  and the learner templates) is also a stated precondition. Confirm it has landed.

## 4. Concrete lessons for this spec

1. Re-derive every range and name by grep on the current tree. Extract-1 landed, so the idea's ranges are
   wrong by dozens to hundreds of lines.
2. Resolve the idea's conditional placements now: `ShowInactiveFilter`, `LazyBodyPanel` and `render_region`
   are probably already gone. Name the final `common/filters.py`, `common/actions.py` and `common/report.py`
   contents explicitly.
3. One commit per move (code, then tests); `git mv` for whole-file moves with no content edits in the same commit.
4. After each commit grep for the old dotted path in the whole repo (code, tests, `mock.patch` strings, docs
   and skills under `claude_plugins/fls-dev`, docstrings and comments) and leave zero hits for moved names.
5. Patch strings point at the namespace that performs the lookup. State this in the spec. Add a verification
   step: run the full `educator_interface` tests, because a wrong patch string can pass silently when a patched
   name is never exercised.
6. Add `__all__` to new modules that are meant as the public surface (framework precedent). Keep `__init__.py`
   empty.
7. Keep the stale `# TODO` block in `views.py` and move other `TODO` or `@claude` comments with their code.
8. Verify no `@register_bulk_action` class is moved, so the "no migration" claim holds.
9. Delete exactly baseline line 41 and run the mirroring check; do not touch the other nine lines.
10. Check `common/*` modules import nothing from flat `views.py`, `actions.py` or `reporting.py` at module
    level, and add an import-order smoke test or rely on `python -c "import ..."` for each new module.
    Consider whether the repo's import-contract linting (the app-map and contracts regenerated by
    extract-1 slice 10) needs no change, since all edges stay inside one app.

status: ok
