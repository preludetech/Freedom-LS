# Best practices: moving Django code between modules with no behaviour change

Written from established practice and the linked docs. I did not re-fetch the pages in this run.

## 1. Verifying a pure move

- **Commit order.** Do the move as a commit that only moves code and repoints imports. Do any edit (a rename, a tidy-up, a fix) in a separate commit. Git detects renames and copies by similarity at diff time, so a moved file with few changes keeps its history. When a class moves out of a big file into a new one, git cannot follow it. Use `git log -L :ClassName:path` or `git blame -C -C -M` on the new file. These find code moved or copied across files. https://git-scm.com/docs/git-blame (`-M`, `-C`)
- **Whole-file moves** (the test files): use `git mv`. Check with `git log --follow -- <new path>` and `git diff -M --stat`. `--follow` works for one file only and is heuristic. Keep the content change small so similarity stays above 50%. If you must edit it, move first and edit in the next commit. https://git-scm.com/docs/git-log (`--follow`)
- **Prove the move is pure.**
  - Run `git diff --color-moved=dimmed-zebra --color-moved-ws=allow-indentation-change main...`. Moved blocks are dimmed, so only real changes stand out. https://git-scm.com/docs/git-diff (`--color-moved`)
  - Compare the extracted class source before and after. For example, diff `inspect.getsource` output, or diff the old block from `git show main:path` against the new file. Only import lines should differ.
  - Compare the test collection before and after. Run `pytest --collect-only -q | sort`, then check that the set of test names is identical apart from path changes. Compare the counts of passed tests too. A silent drop in count means a lost test.
  - Run `manage.py makemigrations --check --dry-run`. It must report no changes. This is the check for "no database change".
  - Compare `show_urls`, or the output of `reverse` for each URL name, before and after, if `urls.py` is touched.
  - Run the full suite, `ruff`, and the type checker. Run `ruff check --select F401,F811,F821` to catch unused or undefined names left behind.
- **Leave no shim.** After the move, run `rg 'old_module\.(Name1|Name2)|from .*old_module import.*(Name1|Name2)'` for every moved name. It must return nothing, in `.py`, templates, docs and settings strings. Dotted-path strings are the usual leftover. Check the `interface_config`, registry and `import_string` style references. They fail only at runtime.

## 2. mock.patch rules

- **Patch where the name is looked up, not where it is defined.** `from a import X` in module `b` creates `b.X`, so patch `"b.X"`. `patch("a.X")` changes nothing in `b`. https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- After a move, the lookup site is often unchanged (for example `views.py` still calls the name) but the definition site has moved. Patching the old location, or a module attribute that no longer exists, behaves like this:
  - `patch("pkg.old_module.Name")` raises `AttributeError` if `Name` is gone from `old_module`. That is loud, which is good.
  - It does **not** raise if the name is still imported into `old_module`. The patch then silently has no effect on the moved code, which uses its own binding.
  - `monkeypatch.setattr("pkg.mod.Name", ...)` is loud by default (`raising=True`). Never pass `raising=False` during a refactor.
  - `monkeypatch.setattr(obj, "name", ...)` with a module object, as in `educator_views.<Name>`, has the same loud-by-default rule. It is silently wrong only when the name still exists on that module as a leftover import.
- **Catch silently-wrong patches:**
  - Use `autospec=True` or `create=False` (the default), so a missing attribute fails.
  - Assert the mock was used, for example `mock.assert_called()`. A test that patches something and never asserts it was called proves nothing.
  - For each moved name, break the patch on purpose once (point it at a bogus module) and check the test fails. Or mutate the target and see the test fail.
  - Grep every string `"freedom_ls.educator_interface.` that contains a moved name, in tests and in non-test code.
  - Because there is no shim, once a name leaves `views.py` the import is gone from there. A stale `patch("...views.HistoryPanel")` then raises `AttributeError`. Moving the import away is itself the detector, as long as `views.py` does not still import the name for another reason. If `views.py` still imports it (for `LearnerHistoryPanel`'s base, say), patch whichever module's code actually executes the lookup.
  - Prefer patching at the real lookup site: the module whose function body names the class.

## 3. Avoiding circular imports in a package split

- Keep a one-way dependency graph: `panels/<area>/` imports `panels/common/` and `panel_framework`. `panels/<area>/` never imports `views.py`. `views.py` imports from `panels/<area>/`. The settled "neither area imports a sibling" rule already gives this.
- A shared helper that both the old module and the new one need goes down to `panels/common/` (or stays in the old module that the new one imports). It must not go in the opposite direction. The new module must not import from `reporting.py` or `views.py`. This matters for `LazyBodyPanel`, `render_region` and `OrganisationScopedRequest`, which the spec already redirects.
- Empty `__init__.py` files remove one source of cycles: package import has no side effects.
- A cycle shows up as `ImportError: cannot import name ... (most likely due to a circular import)`. It depends on which module is imported first, so run both `python -c "import freedom_ls.educator_interface.views"` and the new modules on their own, in a fresh interpreter. Also run `manage.py check`.
- If a cycle remains, fix it by moving the shared thing, not with function-local imports. Use `TYPE_CHECKING` imports only for type hints. The project forbids `Any` and `type: ignore`, so use string annotations or `from __future__`-style forward references where needed.
- Django-specific: model and app-registry imports at module top-level are fine once apps are loaded, but a module imported from `settings` or `apps.py` is not. The moved code is view-layer, so this should not apply.

## 4. Test relocation and pytest pitfalls

- **Duplicate basenames.** With the default `prepend` import mode, two `test_config.py` files in different directories need `__init__.py` in each directory. Without it you get `import file mismatch`. The spec's per-directory `__init__.py` (`tests/panels/dashboard/`, `tests/panels/audit_log/`, plus `tests/panels/` and `tests/`) solves this. Every directory in the chain needs one, or the second `test_config.py`/`test_panels.py` collides. https://docs.pytest.org/en/stable/explanation/pythonpath.html and https://docs.pytest.org/en/stable/how-to/writing_plugins.html#conftest-py-plugins (see also "Good Integration Practices")
- Stale `__pycache__`/`.pyc` files left in the old location can trigger `import file mismatch`. Delete `__pycache__` if collection errors appear after a move.
- **conftest and fixtures.** Fixtures are found by directory scope. A moved test that used a fixture from `tests/conftest.py` still sees it, because parent conftests apply. A fixture defined in a sibling `conftest.py`, or imported from another test module, does not travel. A helper imported by `from freedom_ls.educator_interface.tests.test_views import make_x` couples the new file to the old one. Move the helper to a shared `tests/` helper module, or to `conftest.py`, before the move, and keep the old one importing it. Check for such cross-test imports with `rg "from .*tests.*import"`.
- **Partial moves of a shared test file.** Cut by range, using the class or function name, and check each moved block's module-level helpers, constants, imports and fixtures. Run `ruff` for F401/F821 on both source and destination file. Never leave a helper used by only the moved half in the old file.
- **Verify counts.** Run collection before and after (see section 1). The sum of tests across the old and new locations must be equal. Check that `-p no:randomly` ordering is not hiding dependencies: run the moved files alone, and the remaining old files alone.
- Project-specific: `test_organisation/mirroring_baseline.txt` lists baselined test files. Drop the lines for moved files in the same commit, as the idea says.

## 5. Enforcing "no sibling area imports" with import-linter

- `import-linter` checks contracts in `pyproject.toml` (or `.importlinter`) and fails when one is broken. It is run as `lint-imports`, and can run as a pre-commit hook. https://import-linter.readthedocs.io/en/stable/contract_types.html
- **`independence` contract** is the exact fit: listed modules may not import each other, directly or transitively.

  ```toml
  [tool.importlinter]
  root_package = "freedom_ls"

  [[tool.importlinter.contracts]]
  name = "Educator panel areas are independent"
  type = "independence"
  modules = [
      "freedom_ls.educator_interface.panels.dashboard",
      "freedom_ls.educator_interface.panels.audit_log",
  ]
  ```

- **`layers` contract** can express "areas may import `common`, `common` may not import areas".
- **`forbidden` contract** can forbid area modules importing `views` or `reporting`.
- Notes:
  - Transitive checking can flag an indirect path through `panels/common/`. Use `allow_indirect_imports = true` or `ignore_imports` if it does. This is expected, because both areas import `common`.
  - The `independence` contract applies to the listed siblings only, so new areas (learner, cohort and the others) must be added to the list as later specs land.
  - The tool is not currently in the project. Adding it is new functionality the idea does not ask for ("Don't build functionality that is not explicitly requested"). Treat it as a suggestion for the roadmap, or for spec 7. A cheap substitute for this spec is a one-off check: `rg "panels\.(dashboard|audit_log)" freedom_ls/educator_interface/panels/<other area>`, which must return nothing, plus the `python -c` import checks above.
  - A lighter in-suite option is a small test that parses each area package with `ast` and asserts that no import names a sibling area.

## Practical checklist for this spec

1. Commit 1: move the code and tests (use `git mv` for whole files), repoint imports and patch strings. No other edits.
2. Run `--collect-only` before and after and compare the test names. Run the full suite and `makemigrations --check`.
3. Run `rg` for each moved name against the old module path, including strings and docs. It must return nothing.
4. Check the `educator_views.*` tuple and every patch target by breaking one on purpose.
5. Run `manage.py check` and import each new module alone in a fresh interpreter.
6. Remove the baseline lines for moved test files.

status: ok
