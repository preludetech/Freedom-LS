# Research: reference implementations (spec 2, dashboard and audit log move)

Scope: only what bears on moving two small areas into `panels/<area>/`. The wider survey is in `spec_dd/3. done/2026-11-20_09:37_educator-interface-refactor-1-scaffolding-and-common/research_reference_implementations.md`. It was fetched 2026-11-19 and is not repeated here.

## 1. External projects

- **django-oscar dashboard** (https://github.com/django-oscar/django-oscar/tree/master/src/oscar/apps/dashboard): one subpackage per area (`orders/`, `catalogue/`, `users/` and so on). Each area keeps its own `views.py`, `tables.py`, `forms.py`, `urls.py`. Areas import the shared root modules, and the root never imports an area. This is the closest match to `panels/<area>/{config,panels,data_tables,filters}.py` over `panels/common/`.
- **Wagtail admin** (https://github.com/wagtail/wagtail/tree/main/wagtail/admin/views): area subpackages (`pages/`, `reports/`, `bulk_action/`) beside flat modules for small areas. Package `__init__.py` files stay light. Direct imports from the defining module are normal, with no shim. Tests are only partly mirrored (https://github.com/wagtail/wagtail/tree/main/wagtail/admin/tests). Wagtail moves areas into packages one at a time, and the flat modules and packages exist side by side while that happens.
- **Saleor** (https://github.com/saleor/saleor/tree/main/saleor/graphql): one package per area, with `core/` below them. The rule is that areas import `core` and never each other. Tests are one folder per package, not per module.
- **Django admin** (https://github.com/django/django/tree/main/django/contrib/admin): flat, with only `views/` as a package. It uses function-level imports to break cycles. It is no guide to per-area packages.
- Sentry was not checked. It would add little beyond the pattern above.

Net: the move matches the common pattern (area packages above a leaf common layer, no area importing a sibling, no re-export shim). Strict per-module test mirroring is not an external norm. It comes from this repo's `mirroring_baseline.txt` rule.

## 2. In-repo precedent

- `freedom_ls/educator_interface/panels/common/` holds role-named modules: `request`, `tables`, `badges`, `ids`, `filters`, `actions`, `bulk_actions`, `report`. The spec 1 close-out said `common` is a leaf, and spec 2 relies on that. Dashboard and audit log import only `panels/common/` and `panel_framework`.
- Tests are at `freedom_ls/educator_interface/tests/panels/common/test_<module>.py`. There are `test_bulk_actions`, `test_request`, `test_badges`, `test_filters` and `test_report`. There is no `test_tables.py` or `test_ids.py`, so a test file exists only where a test slice exists. Both `tests/panels/__init__.py` and `tests/panels/common/__init__.py` exist and are empty. `tests/panels/dashboard/` and `tests/panels/audit_log/` need the same.
- Moved tests import straight from the new module, for example `from freedom_ls.educator_interface.panels.common.request import ...` in `test_request.py` and `tests/invariants/test_config_authorisation.py`. This is the clean-break style spec 2 asks for.
- `freedom_ls/panel_framework/lazy_panels.py` already defines `render_region` (line 20) and `LazyBodyPanel` (line 30). `DashboardPanel(LazyBodyPanel)` at `reporting.py:465` therefore has a framework import target ready.
- `panel_framework/tests` is flat and mirrors modules by name, with subfolders only for topic groups (`components/`, `invariants/`, `playwright/`).

## 3. Current tree, for re-checking ranges

- On this branch `reporting.py` has `InlineFigures` at line 273, `gathered_figures` at 449 and `DashboardPanel` at 465. `HistoryPanel` is at `views.py:997`. The idea's ranges (332-560 and 1031-1075) are main's from before the blocking specs, so they have drifted. The spec must move by class name and re-measure.
- Spec 1's tests were split by module (`test_request`, `test_badges`, and so on). Spec 2 does the same for `data_tables` and `data_table_panels`.

## 4. Takeaways

1. Keep the rule "area imports `common` and `panel_framework`, never a sibling". Add a check for it only if spec 1 added none. An optional small guard test that `panels/dashboard` and `panels/audit_log` import no sibling area fits the references.
2. The sibling areas that stay in flat modules (`LearnerHistoryPanel`, `CohortHistoryPanel`, `TargetedAuditLogEntryTable` users) import from the new area. That is the same one-way direction Oscar and Saleor use, and it needs no shim.
3. Create `__init__.py` files and test files only where a module or a test slice exists, as spec 1 did.
4. Patch targets are the risk in a pure move. Wagtail and Saleor have no equivalent, because their tests do not patch by module path. Here, patch strings and `educator_views.<Name>` accesses must follow the module where the name is looked up, and the tests must run to confirm. An attribute patch on the wrong module fails silently.

status: ok
