# Best practices: moving the learner area into `panels/learner/`

Written from established practice and the Django, Python and import-linter docs. URLs are the references. No web fetch was run in this pass, so check the docs when a detail matters.

## 1. Splitting large modules safely

- **Move-only commits.** Do the move in commits that change no code. A move commit contains only cut and paste plus import-line edits. Any rename, signature change or cleanup goes in a separate commit, or not at all (the idea says "pure move").
- **One module per commit, or one per small group.** Order by dependency: leaves first (`config.py`, `filters.py`, `data_tables.py`), then panels, actions, bulk actions, instance view, import views. Run the tests after each commit. A failure then points at one move.
- **Use `git mv` for whole files** (the test files and `learner_section`). For partial moves out of a shared file, cut and paste exactly. Then check with `git diff --color-moved=dimmed-zebra --color-moved-ws=allow-indentation-change` (or `-M`/`-C` on `git log --stat`). Every moved block should show as "moved", and only import lines should show as changed. Reviewers can see the move is pure from this alone.
- **Verify no behaviour change mechanically**, not by reading:
  - The same test count passes before and after. Compare `pytest --collect-only -q` node counts, with test ids differing only by path. A dropped or duplicated test shows up as a count change.
  - `manage.py makemigrations --check --dry-run` gives no model changes. The URL set is identical: dump `reverse` names and paths from `get_resolver().reverse_dict` before and after, and diff.
  - Compare the set of top-level names per module across the move. A script using `ast` that lists each def/class and checks every name exists exactly once afterwards catches lost code.
  - Lint with ruff `F401` and `F821` (unused and undefined names) to find missing and leftover imports. Run `pyright` or `mypy` if the project has it. Both find stale imports that tests never import.
- **No re-export shim.** Without one, any missed import fails loudly at import time. That is the goal, so after the last move grep the old dotted path: `rg "educator_interface\.(views|actions|filters|quick_views|reporting)\.<MovedName>"`, covering `.py`, `.html`, `.md`, `.toml`, settings strings and templatetags. Also grep string references such as `"module.Class"` in `mock.patch`, registries and `import_string` calls. Plain imports are caught by the type checker. Strings are not.
- **Empty `__init__.py`.** An `__init__.py` that imports nothing means the package cannot cause a cycle by itself. It also stops import-time side effects such as `@register_bulk_action` firing in a surprising order. Check the registration side effect: a bulk action registers when its module is imported. After the move, confirm something still imports `panels/learner/bulk_actions.py` at startup (an `AppConfig.ready()` import or `urls.py` import chain). Otherwise the registry is empty in a fresh process. This is a classic hidden behaviour change in a move. Add a test or run a check that the registry holds all 7 learner names after `django.setup()`.

## 2. Import-cycle detection and breaking cycles

- **Detect with import-linter** (`lint-imports`). It supports `forbidden` contracts (for example `panels.learner` must not import `panels.cohort`), `layers` contracts (`cohort` above `learner` above `common`) and `independence`. Add the contract to `pyproject.toml`. A layers contract expresses "cohort imports learner, never the reverse" and keeps it true after spec 6. `grimp` (the engine behind it) can also print the cycle chain. Fallbacks are `pydeps --show-cycles` and `pylint --enable=cyclic-import` (slow, noisy). Run at module granularity, not only package granularity. A package-level cycle can exist without a module-level one.
  - Refs: https://import-linter.readthedocs.io/en/stable/contract_types.html and https://grimp.readthedocs.io/
  - Note: `lint-imports` counts imports inside functions and under `TYPE_CHECKING` by default. Use `exclude_type_checking_imports = true` only if the project means it.
- **Break the cycle by moving the shared symbols down, not by lazy imports.** This is the Dependency Inversion / "extract the shared dependency" fix. The two sibling areas both depend on a lower module. The idea does this: shared tables and membership actions go to the lower area (`cohort/data_tables.py` imports only `common`; membership actions live in `learner/actions.py`). Prefer this over a function-level import, which hides the cycle and can fail at runtime. Keep existing lazy imports only where they already exist (the idea keeps `interface_config` lazy).
- **Direction rule.** Decide one direction (cohort -> learner -> common) and write it as an import-linter layers contract. Then spec 6 cannot reintroduce the cycle unnoticed.
- **Subclassing across modules** (a table in A subclassing a table in B) is a hard import-time dependency. Move the base class to the lower module. Do not move the subclass.
- Watch for the cycle through the shell `views.py`. A panels module that imports `HistoryPanel` or `standalone_page_context` from the shell, while the shell imports panels, is a cycle. The idea already handles it by moving `HistoryPanel` to `panels/audit_log/`. A layers contract (`panels` above the shell, or the reverse) catches slips.

## 3. `mock.patch` after a move: patch where it is looked up

- Rule (Python docs): patch the name in the namespace of the module that uses it, not where it is defined. If `learner/actions.py` does `from x import send_message` and calls `send_message(...)`, patch `...panels.learner.actions.send_message`. Patching `x.send_message` has no effect on that module's already-bound name.
- After a move, each patch string must be re-derived from the module that now contains the *calling code*. A patch that targets the definition module only works if the caller does `import x` then `x.send_message(...)` (module attribute lookup at call time).
- A patch target that no longer exists fails with `AttributeError` or `ModuleNotFoundError`, which is good. The dangerous case is a target that still exists but is the wrong binding: the patch applies and does nothing, and the test then hits the real function or passes vacuously. Mitigations:
  - Use `mock.patch(..., autospec=True)` or `create=False` (the default) so a missing attribute errors.
  - Assert the mock was called (`mock.assert_called_once()`). A test that patches without asserting can pass after a wrong repoint.
  - Prefer `monkeypatch.setattr(module_object, "name", ...)` with an imported module object, not a string. A rename then fails at import time.
  - Run a before/after check: temporarily break the patched function to raise, and confirm the moved test fails. Cheap for the handful in the inventory (`move_between_cohorts`, `record_learner_entry`, `own_conversation_with`, `send_message`, `MAX_UPLOAD_BYTES`).
- A constant like `MAX_UPLOAD_BYTES` patched on a module is read at call time only if the code reads the module global. If code copied it into a default argument or class attribute at import time, patching the module attribute does nothing. Check by running the test.
- If a moved function is split from its callers (the callee moves, the caller stays), the patch string depends on the *caller's* module. Several tests may need different targets for one name.
- Ref: https://docs.python.org/3/library/unittest.mock.html#where-to-patch

## 4. Data migration that rewrites stored dotted paths

- **Shape.** `migrations.RunPython(forwards, backwards)` with two functions. Never `RunPython.noop` for the reverse when the path really changes. The idea requires a real reverse.
- **Use `apps.get_model("educator_interface", "BulkActionRun")`** (the historical model from the `apps` registry argument), never `from freedom_ls.educator_interface.models import BulkActionRun`. The historical model matches the schema at that migration state. App code can change later and break the migration. Do not import the moved action classes either. Hardcode the list of 7 names and the two prefix strings as literals in the migration. Importing the classes would couple the migration to the code it describes, and the old path no longer exists.
- **Dependencies.** `dependencies = [("educator_interface", "<previous>")]` so ordering is explicit. Never edit `0001`.
- **Rewrite precisely.** Filter by exact old value: `filter(action_path=f"{OLD}.{name}")` for each name, then `.update(action_path=f"{NEW}.{name}")`. A queryset `update` is one SQL statement per name and does not call `save()` or signals (good for a data fix). Do not do a prefix `replace` over every row. That would hit rows for staff or cohort actions that are not part of this spec. Leave `action_name` alone. Reverse swaps old and new. Make the forward and reverse idempotent (rerunning updates zero rows).
- **Site-aware models.** If `BulkActionRun` uses a site-aware manager with automatic site filtering, the historical model from `apps.get_model` has plain managers, but check `use_in_migrations`. Confirm the update covers every site. Test with rows on two sites.
- **`elidable=True`?** Django's `RunPython(elidable=True)` lets `squashmigrations` drop the operation. Set it only if a squash can safely discard it: true for a data fix whose old rows will not exist in a fresh database. Using `elidable=True` is the common convention for such data fixes. Follow what `0001` does so the pair behave alike.
- **`atomic`.** On PostgreSQL the migration is atomic by default (one transaction). That is right here. Do not mix schema changes and data changes in one migration.
- **Hints.** `hints={"target_db": ...}` is only needed for multi-db setups.
- Ref: https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations and https://docs.djangoproject.com/en/stable/ref/migration-operations/#runpython

### Testing the migration

- **django-test-migrations**: `Migrator(database="default").apply_initial_migration(("educator_interface", "<previous>"))`, create rows with `old_state.apps.get_model(...)`, then `new_state = migrator.apply_tested_migration(("educator_interface", "<this>"))`, and assert. Call `migrator.reset()` at the end (the fixture does it). It supports `pytest` via the `migrator` fixture and marker `@pytest.mark.django_db`. Ref: https://github.com/wemake-services/django-test-migrations
- **Without that dependency**: `MigrationExecutor(connection)`, `executor.migrate([(app, prev)])`, rebuild with `executor.loader.build_graph()`, get `old_apps = executor.loader.project_state([(app, prev)]).apps`, insert rows, `executor.migrate([(app, this)])`, assert, then migrate back to `prev` and assert the reverse. Reset to the latest migration in a `finally`. Use `@pytest.mark.django_db(transaction=True)` because migrating inside a test transaction conflicts. The project already has `tests/migrations/test_0001_*`. Copy its approach rather than adding a dependency.
- **Cover**: forward on each of the 7 names; reverse on each; rows with other `action_path` values (cohort, staff, already-new path) unchanged; `action_name` unchanged; running forward then reverse gives the original data; an empty table works. A parametrised test over the 7 names keeps it short.
- Also assert the new path is importable: `import_string(new_path)` for each of the 7 names. This ties the migration literal to the real code. Do that in a normal test (not inside the migration), so a typo in the migration literals or a missed class fails.

## 5. Storing dotted Python paths in the database: risks

- **Coupling code layout to data.** Every module move, class rename or app rename silently orphans stored rows. This spec is the example. Stored paths need a migration on every move, and a missed one breaks runs at load time (`ImportError` when a run is rendered or retried).
- **Safer designs** (not in scope here, note for the future): store a stable registry key (`action_name`) and resolve to the class through a registry. The code can then move freely. The idea's `action_name` already looks like this. Check whether anything resolves by `action_path` when `action_name` would do, and note it as a follow-up TODO. Do not build it now ("don't build what is not requested").
- **Security.** `import_string(db_value)` on user-influenced data allows importing arbitrary modules (import side effects, not code execution of arbitrary text). Resolve only through an allow-list registry. Confirm stored paths are only written by code.
- **Failure mode.** Resolve defensively: an unresolvable path should give a clear error or a "no longer available" state, not a 500 in a list view. Check what the current code does. Do not change it in this spec.
- **Deploy ordering.** The migration and the code must ship together. Old code running against migrated rows (rolling deploy) fails the other way. For this project, an upgrade note with `requires_migrations: true` covers installs. Mention the reverse in the notes.
- **Other stores of the path.** Grep for the old path in fixtures, JSON, cached data, task queues (Celery args), audit-log payloads and docs. The migration only fixes `BulkActionRun.action_path`.

## 6. Checklist for the spec

1. Add an import-linter contract (layers: cohort > learner > common; no `panels/learner` -> `panels/cohort`) and run it in CI / pre-commit.
2. Move commit by commit, using `git diff --color-moved` to prove purity. Run the full test suite on each.
3. Re-derive every `mock.patch` / `monkeypatch` string from the calling module. Assert mocks are called.
4. Check that the `@register_bulk_action` import still happens at startup.
5. Migration: historical model via `apps.get_model`, literal names and prefixes, exact-match filter, real reverse, `elidable` as in `0001`, test for forward, reverse and untouched rows, plus `import_string` check.
6. Final grep for old dotted paths in code, templates, tests, docs and baselines. Update `mirroring_baseline.txt` in the same PR.

## References

- https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations
- https://docs.djangoproject.com/en/stable/ref/migration-operations/#runpython
- https://import-linter.readthedocs.io/en/stable/contract_types.html
- https://grimp.readthedocs.io/
- https://github.com/wemake-services/django-test-migrations
- https://git-scm.com/docs/git-diff#Documentation/git-diff.txt---color-movedltmodegt

status: ok
