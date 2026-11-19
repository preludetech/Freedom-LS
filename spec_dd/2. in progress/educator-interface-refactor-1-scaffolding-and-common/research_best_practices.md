# Research: best practices for the scaffolding-and-common move

Topic `best_practices`. Sources: web (cited) plus project guidance. Findings from general knowledge are marked "(general practice)".

## 1. Structuring a large Django app into subpackages

- Split by area (feature), not by layer. One subpackage per area (`panels/dashboard/`, `panels/staff/`, ...) beats `views/`, `actions/`, `filters/` directories, because a change to one area then touches one directory. The idea already does this. (general practice)
- Keep the shared code in one `common/` leaf subpackage. Name modules by what they hold (`request.py`, `tables.py`, `badges.py`, `ids.py`), not `utils.py` or `helpers.py`. The idea already does this.
- Django needs nothing special from a subpackage. It is a plain Python package inside the app, so the app label, models, migrations and template paths do not change. This is why a pure move needs no migration.
- Anything stored by dotted path (here `BulkActionRun.action_path`) is the one hidden coupling to check before moving a class. The idea checks this and finds that no registered class moves.
- Keep `views.py` as the shell and the area code in place until its own spec moves it. Staging the move area by area keeps each diff reviewable.

## 2. Avoiding import cycles

- Dependency direction: `common` is a leaf. It imports from Django, `panel_framework` and other apps, and never from an area subpackage or the flat modules. Areas import `common`. Areas never import each other. If two areas need the same name, it belongs in `common`.
- The `if TYPE_CHECKING:` import exists only to hide a cycle from the runtime. Once the type lives in a leaf module, a normal top-level import is correct and the guard can go. The type is then also visible to runtime tools (`get_type_hints`, pydantic). (general practice)
- Rule of thumb: a cycle means a shared name sits in the wrong module. Fix it by moving the name down to a lower layer. Do not fix it with a lazy import. A function-level import is acceptable only as a deliberate, documented exception, as with the staff `interface_config` import this idea leaves alone.
- Prove the direction with a layered or forbidden-imports contract. `import-linter>=2.15` is already a dev dependency (`pyproject.toml` lines 74 and 226). The docs describe the `layers` and `forbidden` contract types: https://import-linter.readthedocs.io/en/stable/contract_types.html . A forbidden contract of `panels.common` -> `educator_interface.views`, `.actions`, `.quick_views`, `.reporting` would pin the leaf rule. Adding a contract is new tooling, though, and the idea says "do not build what is not requested". Treat it as an optional follow-up for the spec author to decide. A grep (section 5) is enough for this step.

## 3. mock.patch: patch where it is looked up

- Rule from the Python docs: "you patch where an object is looked up, which is not necessarily the same place as where it is defined." https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- Consequences for this move:
  - A string such as `"freedom_ls.educator_interface.actions.uuid_or_404"` must name the module whose code calls the name. After the move that is the area module that did `from ...common.ids import uuid_or_404`. Do not change it to the definition module (`common.ids`) just because the function moved. That patch would silently stop working, because the name was already bound in the importing module.
  - When a test patches a name that used to be defined and used in the same module, and the definition has now moved to `common/` while the caller stayed behind, the patch target is the caller module. When both moved to `common/`, the target is the `common` module.
  - A stale target fails loudly with `AttributeError` only if the attribute no longer exists in that module. A patch on a name that still exists in the old module (because it now imports it) succeeds and does nothing. So a green run alone does not prove a repoint is right. Check each patch by reading which module calls the name.
- `monkeypatch.setattr("dotted.path.name", ...)` follows the same rule. `monkeypatch.setattr(module, "name", ...)` lets you pass the module object, so it needs no string to repoint.
- Find every site with `grep -rnE "(patch|monkeypatch)[^\n]*(<moved name>)"` and by dotted old path, including `patch.object` and `@patch` decorators.

## 4. Keeping git history across file splits

- Git stores no renames. It detects them at diff or log time by similarity. `git diff -M` defaults to a 50% similarity index, and `-M90%` raises it. https://git-scm.com/docs/git-diff
- Splitting one file into many is the hard case. The new file is a copy of a slice, so only a new file whose content is mostly the old file's content can be detected as a rename. `-C` (copy detection) by default finds copies only when the source was modified in the same commit. `--find-copies-harder` inspects unmodified files, at high cost. https://git-scm.com/docs/git-diff
- Practical rules:
  1. One move per commit. Move the code and fix imports in that commit, and do no unrelated edit. Mixing a move with an edit lowers similarity under the threshold.
  2. For a whole-file move (`test_denied_experience.py` -> `tests/panels/common/test_request.py`), do a pure `git mv` with no content change in the same commit, then repoint patches or imports in a second commit if needed. Content stays 100% similar, so the rename is certain.
  3. For slice moves (a helper cut out of `views.py`), history follows the slice only through `git log -L :name:path` or `git blame -C -C`. `git log --follow` follows one whole file and does not follow a slice. Expect the old file to keep the history of the slice. Do not promise otherwise in the spec.
  4. Per-commit moves survive an interactive rebase because each commit's diff is small and self-contained. Squashing them would merge several moves into one diff and lose detection.
  5. Check with `git show -M --stat <commit>` or `git log --follow -- <new path>` after each commit.
- Do not reformat or reorder moved code in the same commit. Leave formatting for a later change, or let the pre-commit formatter run before the move commit so it does not rewrite the moved lines.

## 5. Verifying a pure refactor

- Full test suite before and after (`uv run pytest`). Record the pass and skip counts on main first, so a drop in the collected test count is visible. Moving tests can silently lose them. Compare `pytest --collect-only -q | tail -1` before and after. The counts should match exactly.
- `uv run python manage.py check` and `uv run manage.py makemigrations --check --dry-run` must report no changes. This proves no model or app label moved.
- Grep for old dotted paths and names across code, tests, templates, docs and settings. For each moved name, `grep -rn "views.RelationLinkColumn"`, `"actions import .*_uuid_from"` and so on must return nothing outside the intended new location. Include string forms (`mock.patch`, `import_string`, settings paths, stored `action_path` values) as well as `import` lines.
- Run the project's mirroring check (`check_test_mirroring.py`, below). The baseline file must lose exactly line 41.
- Run `ruff` for unused or missing imports. Also run the type checker, since a removed `TYPE_CHECKING` guard changes what is imported.
- Import smoke test: `python -c "import freedom_ls.educator_interface.panels.common.request"` in a fresh interpreter. It catches a cycle that a warm test run can hide through import order.
- Optional: an import-linter contract (section 2).

## 6. Empty `__init__.py` versus package re-exports

- Empty `__init__.py` keeps imports explicit (`from ...panels.common.request import X`). It makes the import graph greppable, it cannot create a cycle through the package root, and a rename is a plain find and replace. The idea chooses this. It is consistent with "no shim".
- Re-exports in `__init__.py` give a short public path (`from panels.common import X`) but import every submodule when the package is imported. That is how a cycle appears: importing any `common` submodule runs `common/__init__.py`, which imports all the others, so they must not depend on anything that imports the package back. They also make `mock.patch` targets ambiguous, since both `common.X` and `common.request.X` exist.
- A re-export shim at the OLD location (`views.py` re-exporting moved names) hides stale paths from grep and tests. The idea rejects it, and that is the safer choice for a pure move.
- Source: https://docs.python.org/3/reference/import.html#regular-packages (package `__init__` executes on import of any submodule). (general practice for the trade-offs)

## 7. Project guidance already in the repo

- `claude_plugins/django-stack/resources/testing.md`, "Mirroring": `<app>/<module>.py` -> `<app>/tests/test_<module>.py`. A subpackage mirrors as a test subdirectory (`templatetags/content_tags.py` -> `tests/templatetags/test_content_tags.py`). So `panels/common/request.py` -> `tests/panels/common/test_request.py`, matching the idea. A project enforces it with `[tool.test_organisation]` and `${CLAUDE_PLUGIN_ROOT}/scripts/check_test_mirroring.py`. The baseline file (`mirroring_baseline.txt`) lists known exceptions, and removing a resolved line is part of the change.
- The same file's "Dependency direction" section states that tests import only apps the app depends on at runtime, and that the `/ds:app_map` command produces the import-linter contracts. These cover app-to-app direction, not the `common` leaf rule inside one app.
- "Cross-cutting tests" there: a test with no module to mirror goes in a named group such as `tests/invariants/`. This is not needed here, because every moved test has a module.
- Skills in `claude_plugins/fls-dev/skills/` that touch this area: `educator-interface/SKILL.md` and `panel-framework/SKILL.md` (the panel layout and the framework half that `extract_panels_framework` removes), and `testing/SKILL.md` (in both `fls-dev` and `django-stack`). Spec 7 owns the `fls-dev` doc updates, so spec 1 changes none of them. The spec should note that the skills will describe the old flat layout until spec 7.
- Repo rules to respect: no `# type: ignore`, type hints everywhere, no `Any`, never delete `TODO` or `@claude` comments (the stale `# TODO` block at `views.py` 330-339 stays), commit with plain `git commit`.

## 8. Recommendations for the spec

1. Order commits: scaffold empty packages; move `request.py` (breaks the cycle, drops the four `TYPE_CHECKING` guards); then the leaf helpers; then the shared actions; then the tests. One commit per module and per test file.
2. Do each test slice in the commit that moves its code, so every commit is green on its own. This also keeps `git bisect` usable.
3. Define the patch-repoint rule in the spec: the target is the module that looks the name up. List the patch sites by grep, and review each by hand.
4. Add a verification checklist: the same collected-test count, `check`, `makemigrations --check`, grep for zero old paths, the mirroring checker with exactly one baseline line gone, and a fresh-interpreter import of every new module.
5. State that slice history is recovered through `git log -L` and `blame -C`, not `--follow`.

## References

- https://docs.python.org/3/library/unittest.mock.html#where-to-patch
- https://git-scm.com/docs/git-diff (`-M`, `-C`, `--find-copies-harder`)
- https://import-linter.readthedocs.io/en/stable/contract_types.html
- https://docs.python.org/3/reference/import.html#regular-packages
- Project: `claude_plugins/django-stack/resources/testing.md`

status: ok
