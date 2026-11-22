# Best practices: pure-move PR, patch targets, path-rewriting data migration

Sources: Python docs "where to patch" (https://docs.python.org/3/library/unittest.mock.html#where-to-patch), Django docs on `RunPython` (https://docs.djangoproject.com/en/stable/ref/migration-operations/#runpython), Django docs on writing migrations / data migrations (https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations), and the repo precedent `freedom_ls/educator_interface/migrations/0002_move_learner_bulk_runs.py` and `tests/migrations/test_0002_move_learner_bulk_runs.py` (spec 5 already landed here; 0001 is the older precedent).

## 1. Pure-move PR

- Separate move from edit. Cut/paste whole definitions unchanged; the only edits are import lines, `mock.patch` strings and the `__all__`/registry-free references. Do not reformat, rename, reorder or "tidy" moved code, so `git diff --color-moved` (or `--color-moved=dimmed-zebra`) shows the move as moved blocks and a reviewer can check it mechanically.
- Commit in steps inside the PR: (1) move production module by module, (2) repoint imports, (3) move tests, (4) migration. Each commit should leave the suite green where practical, or at minimum the last one does.
- Moving a file with `git mv` only works for whole-file moves. Here most moves are partial (slices of `views.py`, `actions.py`, `reporting.py`), so git will not track rename; say so in the PR description and give the class list per target file so the reviewer can diff by name.
- Verify no behaviour change by evidence, not grep: run the full suite, plus `uv run manage.py makemigrations --check --dry-run` (a moved model/registry string must not produce a schema migration; here only the data migration should exist), and check URL names and template paths are unchanged (existing `interface_walk`/invariant tests).
- Dependency direction: land imports one way (`panels/cohort/` imports `panels/learner/`, never the reverse). Import each name from the module that now defines it; watch for import cycles (module-level import errors show up at collection time). Where a cycle cannot be broken, a function-level or `TYPE_CHECKING` import is the established stopgap, but the idea already settles the layout so prefer none.
- Registry side effects: `@register_bulk_action` runs at import time. Moving a class means the new module must be imported at startup (via a module that Django/URLs already import) or the registry loses the action. Confirm registry keys (`table_key`, `action_name`) are unchanged after the move; a test that enumerates the registry before/after is cheap proof.
- Empty `__init__.py` files and `git grep` for the old dotted path (`educator_interface.actions.<Name>`, `educator_interface.views.<Name>`) as a final sweep, including strings in templates, settings, docs, YAML, and `mirroring_baseline.txt`.

## 2. Keeping `mock.patch` targets correct

- Rule from the Python docs: patch the name where it is *looked up*, not where it is defined. After a move, a patch string like `freedom_ls.educator_interface.views.CohortConfig` is only valid if `views` still imports that name; otherwise `patch` raises `AttributeError` (the loud case) or, worse, patches an attribute nothing reads (the silent case: the test passes but the real code runs).
- For each moved name, find the consumers by running the tests, not only by grep. Per patch, decide: is the patched name used by the moved code (patch in the new module) or by an unmoved caller that imports it (patch in that caller's module)?
- Silent-failure guard: for each repointed `patch` of a function/class, make sure the test still asserts the mock was called (`assert_called_once...`) or that behaviour changed under the patch. A test that never asserts the patch took effect will pass with a dead patch.
- Use `mock.patch.object(module, "name")` with an imported module or `autospec=True` where touching existing tests is allowed, so a wrong target fails at patch time. Do not convert styles in a pure move; only repoint strings.
- `monkeypatch.setattr("dotted.path.name", ...)` strings behave the same as `mock.patch` and must be repointed too. Search for `monkeypatch.setattr(` and `patch(` and `patch.object(` string forms, plus `import_string(` and `override_settings` dotted paths.
- Cross-check by temporarily breaking: after repointing, confirm each previously-patched test still fails if the patch is removed (or at least that the touched tests pass with `-W error` and with `--import-mode` unchanged). At minimum run the full moved-test set and the whole suite once.

## 3. Reversible, idempotent data migration for stored dotted paths

Follow the established repo shape (0002 is the template; copy it, change the prefixes and the class list):

- `_OLD`/`_NEW` prefixes and a `MOVES` list of `(old_path, new_path)` pairs built from the class names. Take the class list from `@register_bulk_action` in the moved module (the four registered cohort bulk actions), not from the idea text. Unregistered bases are never stored and need no row.
- One `_repoint(apps, pairs)` helper used by both directions: `forwards` uses `MOVES`, `backwards` uses `[(new, old) for old, new in MOVES]`. `RunPython(forwards, backwards)` makes it reversible; do not use `RunPython.noop` as the reverse here, since old code reading old paths would break on a rollback.
- Use the historical model via `apps.get_model("freedom_ls_panel_framework", "BulkActionRun")`; never import the real model or the real action classes in a migration (migrations must not depend on code that is being moved).
- Match whole paths with `filter(action_path=old).update(action_path=new)` (exact equality, not `startswith`/`replace`), so a class sharing the prefix is untouched and the operation is idempotent: a second run finds no old-path rows. Running forwards twice or backwards on already-old rows is a no-op.
- Scope: the historical model's manager has no site filter, so all sites are updated. Keep that (0002 does and documents it). `update()` is a single query and needs no batching for this table size; no `atomic = False` is needed.
- Dependencies: `dependencies = [("freedom_ls_educator_interface", "0002_move_learner_bulk_runs")]`, and the file number is `0003_...` (check the directory again when the spec runs; spec 5 added 0002 and extract_panels_framework may add another). Never edit 0001/0002 (project rule).
- Do not mix schema and data operations in this migration; it has only `RunPython`.
- Elidable: do not mark `elidable=True`; stored paths must survive squashing decisions made by the maintainers, and the project has no policy to squash.

## 4. Testing the migration (existing style)

Reuse the `MigrationExecutor` pattern from `test_0002_move_learner_bulk_runs.py` in a new `test_0003_move_cohort_bulk_runs.py`:

- `@pytest.mark.django_db(transaction=True)` because the tests migrate down and up; a `migrated_back_to_the_leaf` fixture restores the schema afterwards (essential, otherwise later tests see a half-migrated DB).
- Cases: forward per registered class (parametrized old to new); `action_name` and other columns preserved; reverse per class; a row on another path (e.g. a learner path `...panels.learner.bulk_actions.X` or an unknown class under `educator_interface.actions.`) left alone; a row already on the new path left alone (idempotence); and a non-migration test that `import_string(NEW + name)` yields a `RecordedBulkAction` subclass, which fails if the class list drifts from the code.
- Add one drift guard beyond 0002 if cheap: assert the migration's class names equal the set of registered cohort bulk action classes from the registry, so a fifth registered action cannot be forgotten. Also add an explicit idempotence test (run forwards, then re-apply the forward function) in addition to the "already new" row.
- Note the 0002 test's parametrize lists spell out full dotted paths as literals; that is fine (it checks the migration's constants independently) and the spec should keep literals rather than reusing `MOVES`.
- `requires_migrations: true` in the upgrade notes, as the idea states.

## 5. Risks worth a line in the spec

- A stored-path row for a class moved by a later spec or still in `actions.py` must not be rewritten; the exact-match filter handles that.
- Rollback ordering: reversing 0003 must run before the code move is reverted; document that code and migration ship together.
- Deploys: during a rolling deploy old workers may still write old paths after the migration ran. Acceptable here (no shim by decision), but note it as the known window.

status: ok
