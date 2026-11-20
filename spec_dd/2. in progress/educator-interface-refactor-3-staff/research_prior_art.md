# Research: prior art for moving the staff area into `panels/staff/`

Scope: repo history (read from `spec_dd/3. done/` and `spec_dd/1. next/`; no shell, so no `git log`), plus
documented outside experience. The repo findings are the stronger part: the same effort has already shipped
one move.

## 1. What has been tried here

### 1.1 `educator-interface-refactor-1-scaffolding-and-common` (done 2026-11-20): the direct precedent
- Moved the shared helpers out of flat `views.py` and `actions.py` into `panels/common/` (now on disk:
  `request.py`, `badges.py`, `ids.py`, `filters.py`, `actions.py`, `tables.py`, `bulk_actions.py`, `report.py`).
  Its tests went to `tests/panels/common/` (`test_request.py`, `test_badges.py`, `test_filters.py`,
  `test_bulk_actions.py`, `test_report.py`), with `__init__.py` at each level.
- No shim, one-way dependency (`common` imports nothing from flat modules). Its todo shows
  spec, plan, implement, document, PR and finish_worktree all ticked. There is no QA report in its directory
  (a pure move, no `do_qa`). I found no record of a failure in its files.
- Its plan (`2. plan.md`) set the working rules this spec should reuse:
  - a slice that moves something greps for the old name before commit and leaves no reference behind, tests and
    comments included; "Fix the import, never the assertion" (line 12);
  - after each slice run `grep -rn "patch\|monkeypatch" freedom_ls/` for the moved names (line 25);
  - record `uv run pytest --collect-only -q --no-cov | tail -1` before and after; counts must match, allowing for
    tests a rebase brought in from main (lines 75, 407);
  - `git diff main -- test_organisation/mirroring_baseline.txt` shows only the intended deletions (line 412).
- Its `research_prior_art.md` and `research_known_complaints.md` (same directory) are the best summary of risk.

### 1.2 `extract_panels_framework-1-gather-generic-code` (done 2026-11-16)
- Moved `ReasonMixin`, `LazyBodyPanel`, `render_region`, the bulk registry and the generic half of
  `EducatorBulkAction` out of `educator_interface`. "Old import paths are not kept as aliases."
- Rules from its plan: grep before committing; `git mv` for moved files; `TODO` and `@claude` comments move with
  their code; new modules get `__all__`.
- QA found no move-related breakage. The cost was a rebase: 4 upstream commits, 96 commits replayed cleanly,
  "lost-change check" passed (`qa_report.md` line 15). Its `todo.md` records rebase fallout needing a human
  call: a new invariant exemption (`HAND_WRITTEN_TABLE_EXEMPTIONS`) added during the rebase and a leftover
  backup branch.
- Effect on this spec: the idea's line ranges are "main's, before extract-1"; the ranges have drifted
  (refactor-1's research measured about 90+ lines of drift in `views.py`/`actions.py`). Names are the contract.
  The class names in this spec's idea (`EducatorReasonMixin`, `EducatorBulkAction`) already reflect extract-1.

### 1.3 Recent rebase-integration failures (git log subjects, this branch's ancestry)
- `learner-profile-use-panels-framework-2-editable-list-panel: fix the wrapped-footer test after rebase`
  (`deecc4c35`) and `finish_worktree: fix an obvious rebase-integration test failure instead of stopping`
  (`0ad9ecb36`). Lesson: after rebase onto a main that moved, a test authored against the old layout can fail
  only at integration. Run the full `educator_interface` suite after the final rebase, not only before it.
  (Detail from the learner-profile-2 QA report: that failure class was a template/footer test, unrelated to
  imports, but it shows rebase-time failures happen late.)

### 1.4 Older done specs touching these modules
`educator-interface-6-cohort-administration`, `-7-learner-administration`, `-9-educator-administration` (the
staff features being moved) and `test-organisation-and-hygene-3/4` (mirroring check, shared test
infrastructure) plans mention baseline or patch handling. They built the code and the mirroring hook; none
attempted a split.

### 1.5 Planned collisions (not yet landed) from `spec_dd/1. next/educator-interface-refactor/research_collisions.md`
- Specs 2, 3 (this) and 4 run in parallel and all cut ranges from `views.py`, `actions.py`, `tests/test_views.py`
  and `tests/test_actions.py` and add lines to the one `views.py` import block. Each removes only its own
  ranges, so conflicts should be mechanical. Spec 2 (dashboard and audit log) is in progress now in a sibling
  worktree; expect conflicts in the import block and in `mirroring_baseline.txt`.
- Slices cut from a 9.8k-line `test_actions.py` have no git rename detection. Hygiene roadmap rule: move test
  files in a commit of their own. For slices, use one commit that moves code and one that moves its tests, so a
  reviewer can compare the lines.

## 2. State of the tree this spec starts from (checked)
- `panels/common/` and `tests/panels/common/` exist (above).
- `tests/test_actions.py` still has 23 occurrences of `freedom_ls.educator_interface.actions.` patch strings;
  `tests/test_views.py` has 2; `tests/migrations/test_0001_rename_unregister_bulk_runs.py` has 1 (a
  persisted `action_path` string, which is data, not a patch target; do not touch). The idea says "about 17" for
  staff names, so about 6 of the 23 target non-staff names and stay. Re-derive per name.

## 3. Failure modes seen or predicted, and lessons

| Failure mode | Seen here? | Lesson |
|---|---|---|
| Stale `mock.patch` / `monkeypatch` strings after a move | Predicted in refactor-1 research; ~22 sites; caught by tests, not by hand | Patch where the name is looked up. A flat module that does `from ...staff.actions import x` is still patched at the flat module. Assert the mock was called. Run the suite; `monkeypatch.setattr(module, ...)` on a module object fails silently. |
| Circular imports (`views` imports `interface_config`, actions import views lazily) | Predicted | Keep `refusal_response`'s `interface_config` import function-level (idea). Smoke-import each new module in a fresh interpreter. `panels/staff` must not import flat `views.py` at module level. Cohort -> staff is the only edge allowed. |
| Mirroring hook / baseline | Refactor-1 deleted exactly one line (41) from `test_organisation/mirroring_baseline.txt` | A test file exists only where its module exists. Delete only lines made stale; diff the baseline against main. |
| Test count drift | Predicted | Compare `--collect-only` before and after, allowing for tests a rebase brings in. |
| Idea line numbers stale | Seen (extract-1 landed) | Re-grep every name; record re-derived ranges in the spec. |
| Rebase fallout | Seen (extract-1: invariant exemption; learner-profile-2: late test failure) | Rebase, then rerun the full suite and the lost-change check. |
| Parallel sibling collisions | Planned | Remove only own ranges; keep the import block one name per line and alphabetical. |
| `@register_bulk_action` moved without a migration | Not applicable here | Verify by grep that no staff class is registered (idea claims none). The `0001_rename_unregister_bulk_runs` migration is the precedent if one were. |
| Lost `TODO` / `@claude` comments | Rule | They move with the code; never delete. |

## 4. Documented outside experience (not opened in full; search-result level)
- Patch where the name is looked up, not where defined (the classic move pitfall):
  https://docs.python.org/3/library/unittest.mock.html#where-to-patch and
  https://dev.to/recca0120/python-mock-pitfall-patch-where-it-is-used-not-where-it-is-defined-1j2m
- Git blame and `--follow` lose history on slice moves out of a big file; rename detection is similarity based
  (about 50%). Move and refactor in separate commits; `git blame -C -C` follows moved lines:
  https://github.blog/changelog/2022-06-06-view-commit-history-across-file-renames-and-moves/ and
  https://codemia.io/knowledge-hub/path/handling_file_renames_in_git
- Both URLs were carried over from the repo's own earlier research (`educator-interface-refactor-1`'s
  `research_known_complaints.md`); I did not re-fetch them. General advice on breaking up monoliths (move
  first, change nothing else; keep behaviour identical; one commit per move) matches the idea's pure-move rule.

status: ok
