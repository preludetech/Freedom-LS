# Research: reference implementations

Question: how do reference implementations solve moving an area out of flat modules into a per-area package with mirrored tests?

## 1. In-repo precedent (the one to follow)

### `educator-interface-refactor-1-scaffolding-and-common` (done, 2026-11-20)
Folder: `spec_dd/3. done/2026-11-20_09:37_educator-interface-refactor-1-scaffolding-and-common/` (`1. spec.md`, `2. plan.md`, `research_reference_implementations.md`, `research_codebase.md`). It is the same kind of pure move, so its method carries over.

Package layout (the tree today):
- `freedom_ls/educator_interface/panels/__init__.py` and `panels/common/__init__.py` are empty. No package-level imports.
- Role-named modules in `panels/common/`: `request.py`, `badges.py`, `tables.py`, `ids.py`, `filters.py`, `actions.py`, `bulk_actions.py`, `report.py`. The staff spec's module names (`config.py`, `data_tables.py`, `actions.py`, `filters.py`, `quick_view.py`) follow the same "named by role, same name as the flat module it came from" rule.
- Each new module starts with `from __future__ import annotations`, a one-line purpose docstring (never "moved from"), absolute imports only (no `from .`), and a sorted `__all__` listing every moved name, underscore names included (confirmed by grep: every `panels/common/*.py` has `__all__`). Staff modules should do the same.
- Moved names keep their spelling and bodies byte for byte. Only import lines change.
- `panels/common/` is a leaf. Greps over it find no flat-module import, no area import, and no relative import. Staff is the first area package, so the mirror rule is: `panels/staff/` imports `panels/common/` and the flat domain modules (`forms.py`, `staff.py`), and `common` never imports staff. The idea's "cohort imports staff, never the reverse" adds a second one-way edge to check by grep.
- No re-export shim and no migration. No `@register_bulk_action` class moved, so no `BulkActionRun.action_path` changed. (Staff: same reasoning, stated in the idea.)

Tests (the tree today):
- `tests/panels/__init__.py` and `tests/panels/common/__init__.py` are empty. Test files are `test_request.py`, `test_badges.py`, `test_filters.py`, `test_bulk_actions.py`, `test_report.py`. A test file exists only where its module exists, because the `test-mirroring` pre-commit hook fails otherwise. `common/actions.py`, `tables.py` and `ids.py` got no test file because nothing tests them directly. For staff: `tests/panels/staff/__init__.py` plus `test_actions.py`, `test_data_tables.py`, `test_config.py`, `test_filters.py`, `test_quick_view.py`, each only if a test slice exists for it (the idea already says so).
- `tests/panels/__init__.py` already exists, so staff adds only `tests/panels/staff/__init__.py`.
- Test helpers: a helper used by only the moving slice moves with it. A helper used by both the moving and the staying tests goes to `tests/helpers.py` under its current spelling, and both files import it from there. This will matter for `test_actions.py` (about 3,450 staff lines out of about 9,400) and for `_interface_url`-style helpers, which refactor-1 already moved to `tests/helpers.py`.
- A fixture the moved tests need goes in `tests/conftest.py` as non-autouse. Files opt in with `pytestmark = pytest.mark.usefixtures("_site_context")`. Refactor-1 did this for `_site_context` in `test_filters.py`. Check whether the staff slice of `test_filters.py` still relies on the same fixture.
- Mirroring baseline: `test_organisation/mirroring_baseline.txt` carries nine `# educator_interface` lines today (`test_cohort_delete_action`, `test_course_visibility_and_interest`, `test_create_cohort_action`, `test_dashboard`, `test_document_title`, `test_interface_urls`, `test_learner_section`, `test_organisation_switcher`, `test_sidebar`). Refactor-1 removed only the `test_denied_experience.py` line, in the same commit that moved the file. None of those nine is a staff file, so the staff move should delete no baseline line. The idea says "removes any line the move makes stale", so the spec must confirm with the hook that none is stale rather than assume.

Process (from `2. plan.md`):
- Slices ordered by dependency. Each slice is a code commit, then a separate test-move commit. The production module lands before or with its test file, so the mirroring hook passes at every commit.
- A whole-file test move is a `git mv` with no content change, so git keeps it as a rename through a rebase. Staff slices are cuts of larger files, not whole-file moves, so this does not apply. Cuts are by named test and section, not by line number.
- Line numbers are only a locator: "re-find each name by grep before cutting it". The idea says the same (line ranges predate `extract_panels_framework-1`).
- Record `pytest --collect-only -q --no-cov | tail -1` before any change and compare at the end. A pure move must collect the same number. Refactor-1 stored it in `.sdd-work/collect_count_before.txt` and deleted it at the end.
- Close-out checks, which are reusable: leaf-rule greps, a whole-repo grep of every moved name for the old module path, `manage.py check`, `makemigrations --check --dry-run`, a fresh-interpreter import of every new and every flat module (`python -I`, with the project root put on `sys.path`), `pre-commit run --all-files` (`test-mirroring`, `lint-imports`, `app-map-fresh`), `git diff main --stat` showing no change under `templates/`, no `urls.py`, no migration, then the full tier.
- Patch strings name the module that looks the name up, not the defining module. Refactor-1 found none to repoint (its research section 4 says no `mock.patch` targeted a moved name). Staff is different: the idea counts about 17 patches in `test_actions.py` and 2 in `test_views.py`. So the staff spec must list each one and decide per patch whether the lookup site is `panels.staff.actions` or a flat module that still imports the name. `monkeypatch.setattr(actions_module, ...)` fails silently, so only running the suite proves it.
- Invariant tests were repointed rather than loosened. In `tests/invariants/test_reason_mixin.py`, the exclusion became `common_actions.EducatorReasonMixin`, and the walk over `actions` kept its `len(found) == 9`. Staff actions subclass `EducatorReasonMixin`, so moving them out of `actions` will change that count unless the walk also covers `panels.staff.actions`. The spec must decide this, and it is the most likely place for a silent break (also `test_bulk_run_scoping.py`, which scans `BulkActionRun` queries in source files, and `test_config_authorisation.py` and `interface_walk.py`, which import configs).
- Docs: `upgrade_notes.md` lists the old and new import path of each moved name, as a breaking change. The sibling ideas in `spec_dd/1. next/` that the move made stale were corrected in the same effort.
- Refactor-1 had no `qa_report.md` or `frontend_qa.md` (it is a pure move with no UI), and its todo shows QA unticked. The staff spec needs none either.

### `extract_panels_framework-1..4` and `learner-profile-use-panels-framework-1, 2`
These are in `spec_dd/3. done/`. They build `freedom_ls/panel_framework/` and a learner-profile panel, not a move into a per-area package, and there is no `panels/` directory outside `educator_interface` (a glob of `freedom_ls/*/panels/**/*.py` finds only `educator_interface/panels/common/` and `panels/__init__.py`). I did not mine them for package layout. Relevant general points only:
- `panel_framework` is a flat package of role-named modules (`tables.py`, `filters.py`, `actions.py`, `bulk_actions.py`, `bulk_runs.py`, `panels.py`, `lazy_panels.py`, `quick_view.py`), with `__all__` per module. Its tests mirror it flat, with subfolders only for topic groups. This is the module-naming source for the staff modules (`quick_view.py`, singular, matches `panel_framework/quick_view.py`).
- The framework specs mention that framework names are imported only through each module's `__all__`, as refactor-1's plan said.

## 2. Well-known Django projects (short; fetched 2026-11-19 for refactor-1, not re-fetched)
- Django admin (https://github.com/django/django/tree/main/django/contrib/admin): flat modules by role (`options.py`, `sites.py`, `helpers.py`, `filters.py`, `actions.py`, `utils.py`). Only `views/` is a package. The wiring modules import leaves, and leaves import back only lazily or under `TYPE_CHECKING`. URLs are built in `sites.py` (`AdminSite.get_urls`) from each `ModelAdmin.get_urls`, not from per-area `urls.py`.
- Wagtail (https://github.com/wagtail/wagtail/tree/main/wagtail/admin/views): area subpackages and flat per-area modules, a shared `generic/` base layer, and each area's URLs attached by a viewset (`wagtail/admin/viewsets/`). Tests are only partly mirrored.
- django-oscar dashboard (https://github.com/django-oscar/django-oscar/tree/master/src/oscar/apps/dashboard): one subpackage per area, each with its own `views.py`, `tables.py`, `forms.py` and `urls.py`. Root modules hold shared code and never import the areas.
- Takeaway for this spec: all three keep shared code in a layer the areas import and that never imports an area, which `panels/common/` already is. None of them keeps a re-export shim. Two of them (oscar, Wagtail) put the area's URLs beside the area. FLS deliberately does not: `urls.py` is unchanged and URL names, paths and template paths stay, so URL organisation is out of scope.

## 3. Takeaways for the staff spec
1. Copy refactor-1's package conventions exactly: empty `__init__.py`, sorted `__all__`, absolute imports, purpose docstring, byte-for-byte moves, no shim, no migration.
2. Add `panels/staff/` as the first area. Keep the one-way rule: staff imports `common` and the flat domain modules, `common` never imports staff, and cohort imports staff (not the reverse). The lazy `interface_config` import in `refusal_response` stays function-level with its path changed.
3. Slice by module, in dependency order: `filters.py` and `quick_view.py` (smallest, independent), then `actions.py` helpers and actions, then `data_tables.py` (needs the filter and actions), then `config.py` (needs the table and actions), then repoint the shell `views.py` (`interface_config`) and the cohort code. Each production slice gets its own test-move commit. Use names, not line numbers.
4. Repoint patches by running the suite, not by grep alone. Extend the `test_reason_mixin.py` and `test_bulk_run_scoping.py` invariants' module walk to cover `panels.staff.actions` if they enumerate modules, and keep the same expected counts in total.
5. Take the collect-only count before and after. The mirroring baseline should lose no line, and the close-out checks are the ones listed above.
6. Helpers shared by the moved staff tests and the staying tests go to `tests/helpers.py`, not into two copies. A fixture both need goes in `tests/conftest.py`.

status: ok
