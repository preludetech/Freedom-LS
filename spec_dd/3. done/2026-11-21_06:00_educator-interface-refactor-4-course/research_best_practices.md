# Best practices: splitting views.py into a per-area package

Written from established practice (no live fetch this run). Reference URLs are listed per point. What the spec must require comes after each point.

## 1. Moving classes with no behaviour change, no shim
- Django has no rule about views layout. A `views` package or a module both work, because a URLconf references the callables it imports. https://docs.djangoproject.com/en/stable/topics/http/urls/
- A move is a pure cut and paste. The class bodies stay byte-identical. Only imports, module docstrings and dotted-path strings change.
- With no re-export shim, the old name must stop resolving. That makes a missed caller fail loudly with `ImportError`.

Spec must require:
- Every moved name is listed, and the code inside each is unchanged.
- A repo-wide grep for each moved name finds no remaining reference to the old path. Cover strings, docstrings and management commands as well as imports.
- Everything still resolves after the move: `uv run manage.py check`, `makemigrations --check --dry-run` (no migration is added) and the full test suite.
- URL names and the reversed URLs are unchanged.

## 2. Moving tests to mirror modules
- pytest discovers tests by file and package. Directories with the same basename need an `__init__.py` in each (rootdir/`rootdir`-based import mode, which FLS already uses). https://docs.pytest.org/en/stable/explanation/pythonpath.html
- Each test file mirrors one source module: `panels/course/data_tables.py` is tested by `tests/panels/course/test_data_tables.py`.
- Move the tests first as a count-preserving operation.

Spec must require:
- The test count before equals the test count after. Compare `pytest --collect-only -q` for the course tests.
- Fixtures and helpers that the moved tests share stay reachable. A fixture moves to a `conftest.py` only if more than one new file uses it.
- Each new directory has an empty `__init__.py`.
- The mirroring and import baselines are updated in the same PR (already in the idea).

## 3. Keeping git history
- Git does not track renames. It detects them at diff or blame time by content similarity, 50% by default. https://git-scm.com/docs/git-diff (`-M`) and https://git-scm.com/docs/git-log (`--follow`)
- A whole-file move that is committed alone is detected reliably. If a commit also rewrites the contents, the similarity drops and history is lost.
- Splitting one file into many has no rename. `git blame -C -C` (https://git-scm.com/docs/git-blame) follows copied lines across files. So the split commit is a pure move, and edits to the moved lines go in a separate commit.

Spec must require:
- Commit order: (a) move the code with the minimal import fix, (b) move the tests in a commit of their own (already in the idea), (c) repoint patches and baselines. Do not mix reformatting into the move commits.
- Whole-file moves, such as `test_course_visibility_and_interest.py`, use `git mv` in a commit with no content edits where that is possible. The split then follows.
- Do not run an auto-formatter over moved blocks beyond what the pre-commit hook forces.

## 4. Repointing mock.patch ("patch where it is looked up")
- Patch the name in the namespace of the module that uses it, not where it is defined. https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- After a move, a string like `"freedom_ls.educator_interface.views.X"` fails in one of two ways. It raises `AttributeError` if `X` is gone from `views`. Or it patches the wrong module and the test passes without patching anything, which is the silent case.
- `monkeypatch.setattr("dotted.path", ...)` behaves the same way. https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- Where the caller moved but the target stays in `views` (or the reverse), repoint to the module that now imports and calls the name.

Spec must require:
- Grep every moved course name inside `patch(`, `patch.object(`, `monkeypatch.setattr(` and string-valued settings or overrides.
- For each hit, the target is the module whose code does the lookup. Where a test patches a name on the module object, assert the patched thing is actually hit (the test fails if the patch is removed or wrong). Use `autospec=True` or `create=False` (the default for `patch`) so a wrong target raises.
- Run the tests after repointing. A pass is not enough evidence on its own for patches of module attributes.

## 5. Avoiding circular imports (shell `views.py` and area packages)
- Cycles come from an area module importing from `views.py` while `views.py` imports the area. Python then sees a half-initialised module. https://docs.python.org/3/reference/import.html#circular-imports (and https://docs.python.org/3/faq/programming.html#what-are-the-best-practices-for-using-import-in-a-module)
- Fix by direction, not by lazy imports. Dependencies point one way: `views.py` (shell) -> `panels/<area>` -> `panels/common` -> no one. No area imports another area or `views.py`.
- Django's string references (`"app.module.Class"`) and lazy `import` inside functions hide cycles. They are a fallback, and not what this spec uses.
- `panels/course/__init__.py` stays empty, so importing a submodule runs no other code.

Spec must require:
- The course package imports only from `panels/common/`, shared flat modules, and other apps. Not from `views.py`, `cohort/`, `learner/` or `staff/`. Check this with the repo's import contract checker (`test_organisation/import_contracts.toml`) and a grep for `from freedom_ls.educator_interface.views` under `panels/course/`.
- Any helper the course code still takes from `views.py` is a blocker. It belongs in `panels/common/` first (that is the scaffolding spec's job), not copied.
- `python -c "import freedom_ls.educator_interface.panels.course.<each module>"` succeeds for each module on its own, in a fresh interpreter. That catches cycles that import order hides.
- The existing lazy import in the test at line 260 is repointed, not turned into a top-level import (unless the move leaves no cycle).

## Sources
- https://docs.djangoproject.com/en/stable/topics/http/urls/
- https://docs.pytest.org/en/stable/explanation/pythonpath.html
- https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- https://docs.python.org/3/reference/import.html#circular-imports
- https://git-scm.com/docs/git-diff
- https://git-scm.com/docs/git-log
- https://git-scm.com/docs/git-blame

status: ok
