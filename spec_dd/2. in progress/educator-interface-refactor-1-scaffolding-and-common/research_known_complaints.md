# Research: known complaints about moving shared code into `panels/common/`

Question: what do developers and downstream consumers complain about with this kind of refactor, and
what can this spec adopt? Repo findings cite files; web findings cite URLs (section 9).

## 1. Broken downstream imports with no shim
- Complaint: consumers who subclassed or imported moved names get `ImportError` on upgrade, with no
  deprecation window.
- FLS facts (`spec_dd/1. next/educator-interface-refactor/research_downstream_imports.md`): the only
  configured concrete project, First-Class-LMS, imports none of `views/actions/filters/quick_views/reporting`.
  It only uses `include("freedom_ls.educator_interface.urls")` and INSTALLED_APPS. A shim would also keep the
  `views` import cycle alive. FLS "is designed to be extended", so an unknown project is the residual risk.
- Mitigation: keep the no-shim decision. Keep app label, `app_name`, URL names, template paths and `urls`
  stable. Write the new `common.*` paths for each public moved name into `upgrade_notes.md` "Breaking
  changes" (names verified against the tree). The notes have no frontmatter flag for import paths, so it is prose only.

## 2. `mock.patch` / `monkeypatch` strings patching the wrong module
- Complaint: patching "where defined" instead of "where looked up" leaves the real function running, or
  raises `AttributeError`. Tests then pass or fail for the wrong reason (section 9, items 1-2).
- FLS facts: dozens of string targets in `tests/test_views.py` and `tests/test_actions.py` patch
  `...actions.<helper>`. Several moved helpers (`_picker_on_get`, `uuid_or_404`, ...) are looked up in the
  caller module, not in `common`.
- Mitigation: repoint each string at the module that does the lookup. That is the old module if it still
  calls the name through its own `from ... import`. It is not automatically `common.*`. Make each patched test assert
  the mock was called (`assert_called`). Grep for `educator_interface\.(views|actions|filters|quick_views|reporting)\.` in
  strings before and after. Prefer `monkeypatch.setattr(obj, "name", ...)` with an imported module object over
  dotted strings, so a bad target fails at import.

## 3. "common/utils" dumping ground growing without bound
- Complaint: `common` becomes the default home for anything vaguely shared, then everything depends on it.
- Mitigation: the idea already splits by role (`request`, `tables`, `badges`, `ids`, `filters`, `actions`,
  `bulk_actions`, `report`) rather than one `utils.py`. Adopt an admission rule in the spec: a name enters
  `common` only if two or more areas use it today (cite the inventory section 1.5), never "might be shared".
  Area-only helpers (e.g. `_staff_member_param`, `learner_status_badge`) stay out. State that `common` imports no
  area package, so the dependency points one way.

## 4. Git blame and history loss on moves
- Complaint: moved code shows the mover as author, and `git log --follow` loses the trail (section 9, item 3).
- Caveat: git infers renames from content similarity (about 50%). This is a slice move out of a 6000+ line
  file, not a whole-file rename. `--follow` will not track it, but `git blame -C -C` can follow copied or moved lines.
- Mitigation: one commit per move (already planned), with no edits to the moved lines in the same commit.
  Repoint imports in a separate commit. Name the source file and line range in each commit message. Whole-file
  moves (`test_denied_experience.py` to `tests/panels/common/test_request.py`) use `git mv` alone first. Optionally list
  move commits in `.git-blame-ignore-revs` (only for pure reformat commits; a move still shows the true author under `-C`).

## 5. Merge-conflict pain for parallel branches
- Complaint: moving code out of a hot file conflicts with every open branch that edits it.
- FLS facts: the roadmap runs `extract_panels_framework-1-gather-generic-code` first and the five area specs after.
  `views.py` 249-1456 and `actions.py` are large edited files.
- Mitigation: land this spec fast and rebase siblings straight after. Re-check line ranges after extraction lands (idea
  says so). Keep each commit small so a rebase conflict is local. Do not reformat or reorder code that stays.

## 6. Circular imports surfacing only at runtime
- Complaint: moving code turns a lazy cycle into an import-time `ImportError` or half-initialised module, often
  only in one entry point (e.g. `urls.py` loading, a management command).
- FLS facts: `actions/filters/quick_views/reporting` import `OrganisationScopedRequest` from `views` under
  `TYPE_CHECKING` today. The spec turns those into top-level imports. The lazy `interface_config` import in `actions.py`
  stays lazy on purpose.
- Mitigation: `common` must never import `views`, `actions`, `filters`, `quick_views` or `reporting`. This
  is cheap to enforce with a test that imports each `common.*` module in a fresh interpreter (or `python -c`)
  and asserts no flat module is in `sys.modules`. Run `manage.py check`, plus the full suite, plus
  the QA helper commands that import `views` (`qa_create_*_registrations`) after each commit.

## 7. Too many tiny modules
- Complaint: eight files for a few helpers; `badges.py` and `ids.py` hold two or one functions.
- Mitigation: the idea's per-role split is deliberate (mirrors tests, one reason to change). Accept it. Do
  not add per-module test files without a real test slice (idea default: no). If review objects, merging
  `ids.py` and `badges.py` into `tables.py` is the fallback; decide in the spec, not during the move.

## 8. Tests that pass but no longer test the right thing
- Complaint: moved tests keep passing because they patch the wrong target, import a re-export, or lost
  fixtures/markers when cut into a new file. Mirroring test files shrink silently.
- Mitigation: before and after each move, compare the collected test count (`pytest --collect-only -q`) for
  the moved slice: the sum over old and new files must be unchanged. Copy module-level fixtures and
  marks with the slice. Keep invariant tests (`tests/invariants/`) unmoved and green. Delete the one mirroring
  baseline line only in the commit that moves `test_denied_experience.py`, and run the mirroring test to confirm
  it passes with the line gone.

## 9. Sources
1. https://dev.to/recca0120/python-mock-pitfall-patch-where-it-is-used-not-where-it-is-defined-1j2m
2. https://docs.python.org/3/library/unittest.mock.html#where-to-patch (cited by search result; page not opened)
3. https://github.blog/changelog/2022-06-06-view-commit-history-across-file-renames-and-moves/ and
   https://codemia.io/knowledge-hub/path/handling_file_renames_in_git (rename detection by similarity; move and
   refactor in separate commits)

status: ok
