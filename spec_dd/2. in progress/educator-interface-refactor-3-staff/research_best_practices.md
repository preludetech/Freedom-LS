# Best practices: moving the staff area into panels/staff

Scope: a pure, behaviour-preserving move out of `views.py` / `actions.py` / `filters.py` / `quick_views.py` into `freedom_ls/educator_interface/panels/staff/`, tests moved to `tests/panels/staff/`, no shim. Sources are cited inline. Where a point rests on general practice rather than a fetched page, it says so.

## 1. Moving code safely: git, blame, one commit or several

- Git stores no renames. It detects them at diff/log/blame time by content similarity (default threshold 50%). A move that cuts a slice out of a 3,000-line file into a new file is a partial copy, not a rename, so `git log --follow` will not track it. `git blame -C -C` (or `-C -C -C`) detects lines moved or copied between files. Run it once after the move to confirm history is recoverable. (https://git-scm.com/docs/git-blame, https://git-scm.com/docs/git-diff#_diff_options)
- To keep blame useful, move text verbatim in the move commit. No reformatting, no import sorting of the moved bodies, no renames. Only the import block and patch strings change. Do the formatter and lint fixes in a separate follow-up commit, or run the formatter before the move so the move diff stays pure. A project can list the formatting commit in `.git-blame-ignore-revs` (`git config blame.ignoreRevsFile`). (https://git-scm.com/docs/git-blame#Documentation/git-blame.txt---ignore-revs-fileltfilegt)
- Commit shape for this repo (general practice):
  1. One commit per module move, in dependency order: `filters.py`, `quick_view.py`, `actions.py` (role helpers, then state helpers, then the actions), `data_tables.py`, `config.py`. Each commit moves the production code, repoints its importers and patch strings, and moves its tests. Each commit leaves the suite green.
  2. Do not do the whole area in one giant commit. A bisectable series is easier to review and to revert. Do not stage a shim between commits either, because the idea rules one out.
  3. Moving the staff `actions.py` slice first means `panels/staff/actions.py` imports from `panels/common/`, and the flat `actions.py` imports nothing from staff. The cohort Settings tab then imports the three cohort-scoped actions from `panels/staff/actions.py`, which matches the one-way dependency in the idea.
- The idea says to re-check every line range against the tree the spec starts from. Use symbol names (`ast` or `grep -n "^class \|^def "`) to cut ranges, not line numbers. A script that extracts top-level nodes by name is safer than hand-cutting by line, because decorators and comments directly above a def are easy to lose. Do not delete `TODO` or `@claude` comments inside moved ranges; they move with the code.

## 2. Where mock.patch targets must point: "patch where it is looked up"

- The rule: patch the name in the namespace that does the lookup, not where the object was defined. If `panels/staff/actions.py` has `from freedom_ls.educator_interface.staff import current_role_entries` and calls `current_role_entries(...)`, the target is `freedom_ls.educator_interface.panels.staff.actions.current_role_entries`. (https://docs.python.org/3/library/unittest.mock.html#where-to-patch)
- After this move, check each existing patch string by asking "which module's global namespace does the code under test read this name from?":
  - Patch targets that name a staff name which now lives in `panels/staff/actions.py` and is called from there (`assign_role`, `grantable_roles`, `grantable_roles_for`, `current_role_entries`, `cohorts_visible_to`, `deactivate_role`) become `...panels.staff.actions.<name>`.
  - Staff-name patches in code that still lives elsewhere may need a different module. Example: a test that drives the cohort Settings tab and patches `grantable_roles_for` must patch it in the module that tab's view reads it from. If the cohort code does `from ...panels.staff.actions import grantable_roles_for`, patch `...cohort_module.grantable_roles_for`, not the staff module.
  - Names that stay put, such as `staff.py`'s `current_role_entries` definition, keep their old target only if the code under test still looks the name up there (that is, it does `from ... import staff; staff.current_role_entries(...)`). If a moved function imports the name with `from ... import name`, the patch must move to the new module.
- The lazy `interface_config` import in `refusal_response` is a function-level import. It re-reads the attribute from the source module on every call, so patch it at its definition module (`...views.interface_config`), not at the staff module. Keep it function-level, as the idea says, and change only its dotted path.

## 3. Detecting silently-broken patches

`mock.patch("a.b.c")` with a stale path to an existing module fails loudly (`AttributeError`) when the attribute is missing. The risky cases are those that succeed but patch something nothing reads.

- Stale-but-present attribute. If `from x import name` is left in the old module (a leftover import, or a name still used there), patching `old.name` succeeds and the moved code never sees the mock. The test then runs the real function. Because the idea removes the names from the old modules (clean break), a stale `patch("...actions.assign_role")` raises `AttributeError`, which is what we want. Do not leave leftover imports in the flat modules to "keep things working". Run ruff F401 (unused import) so a leftover is flagged.
- `monkeypatch.setattr(module_obj, "name", ...)` with an object, not a string. `monkeypatch.setattr` with `raising=True` (the default) raises if the attribute does not exist, so it fails loudly when the name is gone. But when the old module still exposes the name, it patches the wrong namespace silently. Grep `monkeypatch.setattr(` with a module alias (`actions_module`, `views_module`) and check each by hand. The idea flags this class already. (https://docs.pytest.org/en/stable/how-to/monkeypatch.html)
- String form `monkeypatch.setattr("dotted.path.name", value)` resolves the path with `importlib`, so a stale module path fails at import time. This is the safer form and a good target for the rewrite, but the rewrite is a behaviour-preserving change only if the patched name is the same. Do not convert forms during this move; keep the diff to the path strings.
- Guard against patches that do nothing:
  - Keep `create=False` (the default for `mock.patch` / `patch.object`). Never add `create=True` while repointing.
  - Prefer `autospec=True` where the existing test already uses it, and do not remove it. For new repoints, `autospec` makes a wrong-signature call fail. Do not add it to patches that did not have it, since that can change behaviour (`autospec` on a function that is called with different args will now raise).
  - Assert the mock was used. In a few key tests, an `assert_called` on the patched object proves the patch took effect. Do this as a one-off verification (see §5, mutation check), not as new permanent tests; the testing guide discourages call-count assertions as implementation detail.
- One-off check that every patch bites: temporarily make each moved patch target raise (for example, replace the patched function in the new module with `raise AssertionError`). Any test that still passes was not exercising it through the patch. A cheaper variant is to run `pytest -p no:randomly` on the moved tests with the real function temporarily removed from the old location; the suite finding zero failures is the signal. (General practice.)

## 4. Circular-import risks when splitting modules

- The known cycle: `refusal_response` lazily imports `interface_config` from the shell `views.py`, which imports `StaffConfig` from `panels/staff/config.py`, which imports from `panels/staff/actions.py`. Keep the lazy import function-level (the idea says so). Do not hoist it to the module top. A top-level import turns an invisible runtime cycle into an import-time `ImportError` or a half-initialised module. (https://docs.python.org/3/faq/programming.html#what-are-the-best-practices-for-using-import-in-a-module)
- New cycles to watch while repointing:
  - `panels/staff/actions.py` must import only from `panels/common/`, `staff.py`, models and other flat domain modules. It must not import from `views.py`, flat `actions.py`, or the cohort area. The cohort to staff direction is one-way.
  - The flat `views.py` import block now imports staff names from `panels/staff/`. If any flat module that `panels/staff/*` imports itself imports `views.py`, you get a cycle. Check with `python -c "import freedom_ls.educator_interface.panels.staff.actions"` for each new module as the first import in a fresh interpreter, because import order hides cycles. Also run it for the old flat modules alone.
  - `from x import name` binds the name at import time. In a cycle it fails with "cannot import name ... (most likely due to a circular import)". `import x` then `x.name` at call time tolerates a cycle. Only use that style where a cycle already exists.
- `TYPE_CHECKING`-only imports are fine for annotations (the repo requires type hints). They do not create runtime cycles. Do not add new `# type: ignore`.
- Detect cycles mechanically: import-linter contracts (`layers` or `forbidden`) enforce the one-way rules. The repo already generates import-linter contracts from `[tool.test_organisation]` for app-level edges. A contract between `panels.staff` and `panels.cohort` is a new addition and the idea says to add nothing beyond the move, so use import-linter or a one-off `python -X importtime` / `pydeps`-style check as verification only. (https://import-linter.readthedocs.io/)

## 5. Verifying no behaviour change

Run in this order after each commit and again at the end:

1. Stale dotted paths: grep the whole tree (not just `freedom_ls/`) for each moved name and for the old module path. Include `.md` files (skills, docs), `.toml`, templates, `pyproject.toml`, `docs/app_structure.md`. Regex for old paths: `educator_interface\.(views|actions|filters|quick_views)\.(<moved names>)` and `educator_interface/(views|actions|filters|quick_views)\.py`. Also grep for relative imports (`from \.actions import`, `from \. import`) because they will not match a dotted-path grep.
2. Import every module: `uv run python -c "import freedom_ls.educator_interface.panels.staff.config, ...data_tables, ...actions, ...filters, ...quick_view"` and `uv run python manage.py check`.
3. Migrations unchanged: `uv run manage.py makemigrations --check --dry-run` must report no changes. The idea says no `BulkActionRun.action_path` row points at the moved classes. Confirm with a grep for `action_path` and `register_bulk_action` over staff classes.
4. Full test suite: `uv run pytest` (not a targeted tier). A move changes import resolution everywhere, so use the `full` tier from `select_tests.py`. Compare the collected test count before and after: `pytest --collect-only -q | tail -1` on the base commit and on the head. The count must match exactly, because the move adds and removes none. A drop means a test was lost in the slice; a rise means one was duplicated.
5. Test ids: compare the set of test names before and after (`--collect-only -q`, strip the path prefix, sort, diff). This catches a dropped or duplicated test that the count alone would miss when both happen.
6. Lint and types: `ruff check` (F401 unused import, F811 redefinition, F821 undefined name) and the repo's type checker. These find leftover and missing imports in the flat modules.
7. The pre-commit mirroring hook (`check_test_mirroring.py`) and `mirroring_baseline.txt`: remove only lines made stale by the move, in the same change.
8. Interface-level smoke: `tests/interface_walk.py` and the `invariants/test_config_authorisation.py` walk every config, so they cover URL names and paths. Compare `python manage.py show_urls` (or `reverse` over all names) before and after if a command exists; URL names and paths must be byte-identical.

## 6. Test file splitting conventions

- Mirror rule from `claude_plugins/django-stack/resources/testing.md`: `<app>/<module>.py` becomes `<app>/tests/test_<module>.py`, a subpackage becomes a test subdirectory, so `educator_interface/panels/staff/actions.py` becomes `educator_interface/tests/panels/staff/test_actions.py`. Each new test directory gets an `__init__.py` (the idea says this; it also avoids duplicate-basename collisions such as two `test_actions.py` files under the default `prepend` import mode, which would otherwise raise "import file mismatch"). (https://docs.pytest.org/en/stable/explanation/pythonpath.html)
- A test file exists only where its module exists. Cut the staff slice out of the flat test file by test function name, not by line range, and keep module-level imports, constants and helper functions the slice needs. Copy shared helpers to a plain module beside the tests (`helpers.py` / `builders.py`) if both the flat file and the new file need them. Never put plain helpers in `conftest.py`. Fixtures used by both stay in the nearest shared `conftest.py` (fixture placement rule).
- After the cut, run ruff F401/F811 on both the old and the new test file: the old one will have unused imports and the new one may miss imports. Remove unused imports in the old file only for names the cut made unused.
- Keep test function names and docstrings unchanged. Renaming makes the before/after test-id comparison (§5.5) useless.
- Do not tidy or deduplicate tests while moving. Test cleanup belongs to a later change, and the idea's scope is a pure move.
- Split `test_views.py`'s staff slice by "the module each test exercises": tests that build and render `StaffDataTable` go to `test_data_tables.py`; tests of `StaffConfig` go to `test_config.py`. Where a test exercises both, put it with the module whose behaviour it asserts on, per the mirroring rule. Leave a test where it is if it is cross-cutting and has no single module (`invariants/`).

## 7. Checklist for the spec

- [ ] Re-derive every range from symbols on the starting tree.
- [ ] Verbatim moves; formatting in a separate commit.
- [ ] One commit per module, each green; no shim in between.
- [ ] Every `patch("...")` string classified by "where is it looked up", and every `monkeypatch.setattr(<module obj>, ...)` read by hand.
- [ ] No `create=True`; keep existing `autospec`.
- [ ] Lazy `interface_config` import stays function-level.
- [ ] Test count and test-id set equal before and after; full suite green.
- [ ] `makemigrations --check` clean; `manage.py check` clean.
- [ ] Stale-path grep covers `.md`, templates, `.toml` and relative imports.
- [ ] `mirroring_baseline.txt` trimmed; hooks green.

## Sources

- https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- https://docs.pytest.org/en/stable/explanation/pythonpath.html
- https://git-scm.com/docs/git-blame
- https://git-scm.com/docs/git-diff
- https://docs.python.org/3/faq/programming.html#what-are-the-best-practices-for-using-import-in-a-module
- https://import-linter.readthedocs.io/
- Repo: `claude_plugins/django-stack/resources/testing.md` (mirroring, helpers, fixture placement), `spec_dd/2. in progress/educator-interface-refactor-3-staff/idea.md`.

Note: I did not fetch these pages in this run; the URLs are the standard documentation locations and the claims are from established knowledge of them.

status: ok
