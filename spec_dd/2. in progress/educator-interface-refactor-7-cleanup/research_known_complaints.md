# Known complaints: refactors that move modules and delete old import paths with no shim

Sources are general knowledge plus the standard docs below. I did not fetch them for this note.

- mock.patch "where to patch": https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- Celery task names: https://docs.celeryq.dev/en/stable/userguide/tasks.html#names
- Django `import_string`: https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.module_loading.import_string
- `git blame -C`/`-M`: https://git-scm.com/docs/git-blame

## Complaints and how each applies here

| Complaint | Applies? | Spec guard |
|---|---|---|
| **Broken downstream imports.** Projects that import `educator_interface.views.X` or `.actions.X` get `ImportError` on upgrade. | Yes. FLS is installed into other projects, and the idea says no shim is left. | Write the upgrade note with a verified old-to-new dotted path for every public name. Say that a project using only `include(...urls)` and INSTALLED_APPS needs no action. Verify each path in the note against the tree, for example with a test or script that imports it. |
| **Stale `mock.patch` targets.** A target string naming a deleted module raises `ModuleNotFoundError` or `AttributeError`. The worse case is patching the defining module when the code under test looks the name up in its importing module (the "where to patch" rule). The test then passes while the mock does nothing. | Yes. The idea sweeps `mock.patch` and `monkeypatch` strings, and moved code makes the second case likely. | Grep every `patch(`, `patch.object`, `monkeypatch.setattr` and `setattr("...")` string for the old module names. Patch the module that uses the name. For each repointed patch, check the mock is hit (`assert_called`) so it cannot pass vacuously. |
| **Dotted paths stored as data.** `import_string` settings, Celery task names (default name is the module path), registered bulk action paths in DB rows, pickled objects and ContentType-like rows all break silently or at runtime. | Partly. Registered bulk actions in the DB are already handled by the data migrations in specs 5 and 6, and this spec adds no migration. `tasks.py` is out of scope and stays put. Settings strings and `import_string` calls are not yet confirmed. | Grep for `import_string`, `"freedom_ls.educator_interface.` in settings, fixtures and JSON, and `@shared_task(name=`. Check that the sibling data migrations cover every moved stored path. Check that `upgrade_notes.md` has `requires_migrations: true` and the `migrate` step. Leave migration 0001 alone as history. |
| **Circular imports after splitting.** Moved helpers import each other, or `views` and `panels` import each other. This causes import-time `ImportError` or half-initialised modules, and often only in one entry order. | Yes, mainly for `urls.py`, which imports `views` plus the new modules, and for the lazy `interface_config` import in the staff actions. | Keep `views.py` as a leaf shell that panels do not import at module level. Leave the lazy `interface_config` import as is (the idea marks it out of scope). Run `manage.py check` and import each moved module on its own, in a fresh interpreter. The test-layout layering check belongs to spec 15. |
| **Lost git blame.** Moving and deleting code makes `git blame` point at the move commit. | Mostly accepted. The siblings already did the moves. This spec only deletes. | Put the deletions in separate commits from any edits. Do not squash moves together with changes. Mention `git blame -C -M` in the PR. |
| **Test discovery gaps.** Moved or new test dirs without `__init__.py` are not collected. Deleted files shrink the test count without anyone noticing. Mirroring baselines go stale. | Yes. The idea moves residual tests, creates directories and edits the mirroring baseline. | Add an empty `__init__.py` to every new directory (the idea already says so). Record the collected test count before and after, and explain any drop as only deleted duplicates. Run `check_test_mirroring.py` with no stale baseline lines. Run the full suite. Check that `import_baseline.txt:46` and `import_contracts.toml:197` (`test_course_visibility_and_interest`) are fixed. |
| **Leftover references in docs and skills.** `SKILL.md`, `testing.md` and docstrings keep naming old paths, and agents copy them. | Yes. These are listed in the idea. | Final grep gate over `freedom_ls/`, `claude_plugins/fls-dev/`, `test_organisation/` and `docs/`. The allowed exceptions are migration 0001 and its test, `spec_dd/3. done/`, and `panel_framework/tests/test_views.py:356`. |
| **Hidden live code in "empty" files.** Deleting a flat module that still holds a live definition breaks things at runtime. | Yes. The idea lists this as open. | Before deleting, check each file is only imports or unused leftovers. Move anything live to its home in the research target tree and say so in the PR. |

## Suggested acceptance checks

1. The old-path grep returns only the allowed exceptions.
2. `manage.py check`, `makemigrations --check` (no changes) and the full test suite pass.
3. A test or script imports every dotted path listed in `upgrade_notes.md`.
4. The mirroring checker passes.
5. The collected test count is explained.

status: ok
