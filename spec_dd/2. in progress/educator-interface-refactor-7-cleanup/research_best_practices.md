# Best practices: finishing a module-split refactor

Drawn from established practice (not freshly fetched; URLs are the canonical references). Each point ends with how it applies to this idea.

## 1. Delete emptied modules, no shims

- A re-export shim is only justified when a deprecation window is promised (Django's own policy: https://docs.djangoproject.com/en/stable/internals/release-process/#internal-release-deprecation-policy). This effort promises none, so delete outright and document the break in the upgrade note. A shim would also hide stale importers, defeating the sweep.
- Delete a module only after proving nothing live is left. Check with `ast` or `grep -nE '^(def|class|[A-Za-z_]+ *=)'` that each file holds only imports or unused leftovers. Move any live definition to its target home and say so in the PR.
- Use `ruff` rule F401 (unused imports) and F811, plus `python -c "import freedom_ls.educator_interface.<mod>"` expecting `ModuleNotFoundError`, as the "gone" proof.
- Delete in one commit separate from the repoints, so the diff shows pure removal.
- Applies to: `actions.py`, `filters.py`, `quick_views.py`, `reporting.py`. Trim `views.py` to the shell list and re-check line ranges against the tree, not main.

## 2. Sweep stale dotted paths

- Grep both forms: dotted (`educator_interface\.(views|actions|filters|quick_views|reporting)`) and slashed (`educator_interface/(…)`). Also grep bare relative imports (`from \. import views`, `from \.views`, `from \.actions`) inside the app, because the dotted grep misses them.
- Strings are invisible to linters and type checkers. Cover:
  - `mock.patch("...")` and `mock.patch.object` string targets.
  - `monkeypatch.setattr("...")` string form.
  - `import_string(...)` and settings values.
  - Entries in `INSTALLED_APPS`, `AppConfig` paths, Django system-check or registry strings.
  - Celery task names, which are strings that look like paths.
  - Docstrings, markdown docs and skill files.
- Patch target rule: patch where the name is looked up, not where it is defined (https://docs.python.org/3/library/unittest.mock.html#where-to-patch). Moving a function therefore changes the correct patch target even when the test still imports fine. A patch of a name in the old module raises `AttributeError` or `ModuleNotFoundError` at run time, so the tests are a backstop. A patch that targets a name the new module imports but the code under test imports elsewhere fails silently. Re-read each patched call site rather than rewriting the prefix mechanically.
- Persisted dotted paths (data in the DB, for example registered bulk action paths in migrations) are the exception that needs a data migration. The siblings own those. This spec should check with a grep over fixtures and migrations that none remain, and leave migration 0001 alone as history.
- Verify with a final zero-hit grep, with explicit allow-listed exclusions (migration 0001 and its test, `spec_dd/3. done/`, the `panel_framework/tests/test_views.py:356` pointer). Record the allow-list in the PR so a reviewer can re-run the same command.
- Run `uv run python manage.py check`, `makemigrations --check --dry-run` (must show no migration, since this spec adds none), and the full test run. Run `pytest --collect-only` first to catch import errors cheaply.
- Applies to the listed repoints (`educator_tags.py`, the two qa_helpers commands, `reports/gather.py:371` docstring, the two fls-dev files). Keep generic plugins (`sdd`, `ds`, `productivity`) untouched.

## 3. Relocate residual tests

- Mirror the source layout, one test module per source module (the project's own `check_test_mirroring.py` enforces this). Move tests whole (class by class), preserving names, so `git log --follow` and failure history survive. Do not rewrite assertions during the move.
- Do the move as a pure move first, then fix imports and fixtures. Check that the test count before and after is equal (`pytest --collect-only -q | tail -1`), and that no test is lost to a name clash when two files merge into `tests/test_views.py`. Duplicate test function or class names inside one module silently shadow each other, so scan for duplicates after folding.
- Fold shared fixtures and helpers deliberately. Prefer the nearest `conftest.py` over importing helpers from another test module. Do not leave a test file importing from a deleted one.
- Create `__init__.py` in every new test directory. Create new test files only beside the module they mirror.
- Delete the emptied test files, then remove their baseline lines in the same commit, so `check_test_mirroring.py` passes with no stale baseline entries.
- Check the string references to test module names (`import_baseline.txt:46`, `import_contracts.toml:197`) after the moves.

## 4. Breaking-change upgrade note

Good upgrade notes (Django release notes and "backwards incompatible changes" sections are the model: https://docs.djangoproject.com/en/stable/releases/6.0/#backwards-incompatible-changes-in-6-0; also https://keepachangelog.com) share these traits:

- Lead with who is affected and who is not. Here: a project that only uses `include("freedom_ls.educator_interface.urls")` and `INSTALLED_APPS` needs no action.
- Give an old path to new path table, one row per public name, in the form downstream users can grep and sed. Generate the table from the tree (a script that imports each new path) so every dotted path is verified, not typed from memory.
- State what did not change (URL names, URL paths, template paths, app label), because that is what lets readers stop worrying.
- Give actionable manual steps in order: run `uv run manage.py migrate`, grep for the old module paths (give the exact regex), fix imports. Name any `mock.patch` or settings strings, since downstream tests will hit those.
- Say plainly there is no compatibility shim and the old paths raise `ImportError`.
- Follow `claude_plugins/fls-dev/commands/update_upgrade_notes.md` for frontmatter. The flag `requires_migrations: true` comes from the sibling migrations, not this spec.
- Write the note last, after the tree is final, so placements such as `OrganisationScopedRequest` and `interface_config` are described as they landed.

## 5. Process checklist for this spec

1. Re-read the tree after all siblings merge. Re-derive line ranges and the live-definition check for the four flat modules.
2. Run the sweep grep and save the output in the PR as "before".
3. Repoint, delete the modules, trim `views.py`, move the tests, clear the baselines (separate commits).
4. Re-run the grep (expect only the allow-list), `check`, `makemigrations --check`, `check_test_mirroring.py`, and the full test suite.
5. Write the upgrade note with verified paths.

status: ok
