# Known complaints: large-module splits and package refactors

Sources are from general knowledge and were not re-fetched. The pytest facts about this repo were read from `pyproject.toml`.

## Repo pytest config (checked)

- `[tool.pytest.ini_options]` in `pyproject.toml`. There is no `pytest.ini`.
- There is no `--import-mode` in `addopts`, so pytest uses the default `prepend` mode.
- `python_files = ["tests.py", "test_*.py", "*_tests.py"]`.
- `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`.
- `freedom_ls/educator_interface/tests/` already has `__init__.py` in `tests/`, `tests/panels/` and `tests/panels/common/`. Each test directory is a package.
- In `prepend` mode a test directory without `__init__.py` is imported by bare basename. Two `test_data_tables.py` files in `tests/panels/course/` and `tests/panels/cohort/` would then fail collection with "import file mismatch".
- With `__init__.py` in every directory, the dotted names are distinct and the duplicate basenames are safe.
- `--dist loadfile` and `pytest-randomly` are on. Neither changes this.

## Complaints and what the spec should require

1. **Duplicate test basenames or a missing `__init__.py`.**
   - Without an `__init__.py`, collection fails with an "import file mismatch" error. This is the pytest `prepend` behaviour (https://docs.pytest.org/en/stable/explanation/pythonpath.html, https://docs.pytest.org/en/stable/explanation/goodpractices.html).
   - The spec should require an empty `__init__.py` in `tests/panels/course/`.
   - It should also require a collect-only check, `pytest --collect-only freedom_ls/educator_interface/tests`, that shows the course files collected and no import mismatch.
   - The idea already requires the `__init__.py`. The check is the missing piece.
2. **`mock.patch` paths that fail silently.**
   - Patching the old module path raises `AttributeError` only if the attribute is gone.
   - If a name is still imported there, for example through a leftover import in `views.py`, the patch succeeds and does nothing. The rule is to patch where the name is looked up (https://docs.python.org/3/library/unittest.mock.html#where-to-patch).
   - The spec should require a grep for every moved course name in string form, in `mock.patch`, `monkeypatch.setattr`, `patch.object` and `settings`/dotted-path strings.
   - It should require each patch to target the module that looks the name up.
   - It should require that no moved name stays importable from `views.py`. That is the no-shim rule, and it makes stale patches fail loudly.
   - It should require that each patched test fails if the patch is wrong, or asserts the mock was called.
3. **Import cycles.**
   - Moving classes into sibling modules can create a cycle through `views.py`, or through the common package back to `views.py`.
   - The spec should require that `panels/course/*` imports only `panels/common/*`, the domain apps and the stdlib. It must never import `views.py`, `cohort/`, `learner/` or `staff/`.
   - The existing `test_organisation/import_contracts.toml` checker already enforces module-level contracts. The spec should require that it passes.
   - A bare `python -c "import freedom_ls.educator_interface.panels.course.<module>"` run for each new module catches order-dependent cycles. The Django test run alone may not.
4. **Private `_name` helpers imported across modules.**
   - The moved code uses `_interface_link`, `_learner_column`, `_registration_columns`, `_form_page_rows` and `_condition_question_text`.
   - Importing underscore names across modules is a lint complaint (ruff PLC2701 `import-private-name`).
   - The spec should say that the `common/` helpers keep their names as `common/` defines them, with no rename in this spec.
   - It should say that course-internal underscore helpers stay inside `content_preview.py`.
   - It should require that nothing outside `content_preview.py` imports `_form_page_rows` or `_condition_question_text`. The grep for `OutlineRow` and `outline_rows` should cover these too.
5. **Lost git blame and history.**
   - A move that also edits the code makes `git blame` and `git log --follow` lose the trail. Blame can follow lines with `-M` and `-C` only when the moves are clean (https://git-scm.com/docs/git-blame).
   - The spec should require that test files move in a commit of their own, and that the code move changes nothing except imports. The idea already says the test move is its own commit.
   - It should also require the code cut in one commit with no refactoring or reformatting mixed in. The spec should note that `git blame -M -C -C` is how a reader recovers the history.
6. **Merge conflicts from parallel branches cutting the same file.**
   - Siblings cut other ranges from `views.py` and `test_views.py` and edit the same import block.
   - The spec should require removing only the course ranges, and no reformatting, import re-sorting or reordering of what stays.
   - It should require re-checking the ranges against the tree at spec time, and again at rebase. It should say that names are the contract, not line numbers.
   - It should tell whoever lands second to resolve import-block conflicts by dropping only the course names.
   - A full `pytest` run after the rebase is the final check.
7. **Downstream projects and other callers breaking without a shim.**
   - Anything that imports `freedom_ls.educator_interface.views.CourseConfig` or a similar path breaks. In this repo the known callers are the two `qa_helpers` commands, `tests/invariants/*` and `interface_config`.
   - A project-wide grep for `educator_interface.views` plus each moved name should cover `*.py`, `*.toml`, `*.txt`, `*.md` and templates.
   - The spec should require that grep, and that the result is empty for moved course names. The grep is the evidence for the decision to ship no shim.
   - It should require repointing the callers in the same PR, and a stated release-note line that the old import path is gone.
8. **Stale baseline and contract files.**
   - The checkers fail on stale lines in `mirroring_baseline.txt`, `import_baseline.txt` and `import_contracts.toml`.
   - The spec should require running the `test_organisation` checkers as acceptance criteria.

## Verdict

The idea already covers 1, 2, 3, 5, 6 and 7. The spec should add these acceptance checks:
- `pytest --collect-only` on the new directory.
- A string-form grep for moved names, with an empty result outside `panels/course/`.
- A bare import of each new module.
- The `test_organisation` checkers.
- A full test run.

status: ok
