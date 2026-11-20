# Research: reference implementations

Question: how do well-known Django projects lay out a per-area package with a shared common layer, avoid import cycles, and mirror tests? Sources are GitHub directory listings fetched on 2026-11-19. Listings can be truncated, so treat the lists as partial.

## 1. External projects

### Django admin
URL: https://github.com/django/django/tree/main/django/contrib/admin
- The app is flat. Shared helpers sit beside the code that uses them: `helpers.py`, `utils.py`, `decorators.py`, `filters.py`, `actions.py`, `widgets.py`. Only `views/` is a package.
- There is no `common/` package. Shared code gets a role-named module (`utils`, `helpers`).
- `options.py` and `sites.py` do the wiring and import the leaf modules. The leaf modules do not import `options`. Where a leaf needs a type from a wiring module, Django uses function-level imports or `TYPE_CHECKING`.

### Wagtail
URLs:
- https://github.com/wagtail/wagtail/tree/main/wagtail/admin/views
- https://github.com/wagtail/wagtail/tree/main/wagtail/admin/views/bulk_action
- https://github.com/wagtail/wagtail/tree/main/wagtail/admin/tests
- `admin/views/` holds area subpackages (`pages/`, `reports/`, `bulk_action/`, `generic/`) and flat per-area modules (`collections.py`, `workflows.py`, `tags.py`).
- The shared layer has two forms.
  - `views/generic/` holds the base views (index, create, edit, delete) that the areas subclass.
  - `views/mixins.py` holds small shared mixins.
- `views/bulk_action/` is the closest match to our `common/bulk_actions.py`. Its own package has `base_bulk_action.py`, `registry.py`, `dispatcher.py` and `mixins.py`. The registry and the base class sit in separate modules.
- Table and UI helpers live outside `views/`, in `wagtail/admin/ui/tables`. They are a sibling of the views, not a submodule of them.
- Tests live in `wagtail/admin/tests/` and are only partly mirrored. `ui/`, `pages/`, `viewsets/` and `api/` are subfolders. The view tests are flat files (`test_views.py`, `test_reports_views.py`, `test_collections_views.py`). Wagtail does not enforce strict mirroring.

### django-oscar dashboard
URL: https://github.com/django-oscar/django-oscar/tree/master/src/oscar/apps/dashboard
- Each area has its own subpackage (`catalogue/`, `orders/`, `offers/`, `users/`, `vouchers/` and others).
- Shared code stays as flat modules at the dashboard root: `tables.py`, `views.py`, `widgets.py`, `permissions.py`, `nav.py`, `menu.py`.
- Each area holds its own `views.py`, `tables.py`, `forms.py` and `urls.py`. Areas import from the root modules. The root modules never import from the areas.
- Test layout was not verified.

### Saleor
URL: https://github.com/saleor/saleor/tree/main/saleor/graphql
- There is one subpackage per area (`order/`, `product/`, `checkout/` and so on).
- Shared code is in `core/` and `utils/`.
- The rule is one-directional: areas import `core`, and `core` never imports an area. This is how it avoids cycles.
- Tests live in a `tests/` folder at the `graphql/` level and are not mirrored per module. (Observed from the listing only, which shows `tests` as a sibling of the areas.)

### Not fetched
Sentry, Zulip, django-tables2 and django-filter were not checked. Their layouts would add little beyond the pattern above.

## 2. Patterns across the projects

1. **Shared code goes in a leaf layer that areas import and that never imports an area.** Wagtail `generic/` and `ui/`, oscar root modules, and Saleor `core/` and `utils/` all work this way. The `panels/common/` plan matches it.
2. **Names are by role, not by "common".** Django uses `utils` and `helpers`. Saleor uses `core`. Wagtail uses `generic` and `mixins`. Our `common/` is a reasonable name for the layer. Within it, role-named modules (`request`, `tables`, `badges`, `ids`, `filters`, `actions`, `bulk_actions`, `report`) match Wagtail's `bulk_action/` split.
3. **Package `__init__.py` is empty or near-empty.** Importing `wagtail.admin.views` pulls in no subpackage. Our "empty `__init__`, no package-level imports" rule fits.
4. **Cycle avoidance is structural.**
   - The common layer holds only types and helpers, and imports only from the framework and models.
   - A few cases still use function-level imports. The lazy `interface_config` import in `actions.py` is that kind of case. It is about a cross-area import (staff code), and leaving it lazy is correct until spec 3.
5. **Test mirroring varies.** Wagtail and Saleor do not mirror strictly. FLS differs because the repo enforces mirroring through `mirroring_baseline.txt`, so `tests/panels/common/test_<module>.py` is a repo rule and not an external norm. The one-to-one rule means a test file exists only where its module does (`test_request.py` yes, `test_tables.py` only if a test slice exists). The spec already says this.

## 3. In this repo

- `freedom_ls/panel_framework/` is the nearest thing to a shared layer. It is a flat package of role-named modules: `tables.py`, `filters.py`, `actions.py`, `bulk_actions.py`, `bulk_runs.py`, `context.py`, `panels.py`, `lazy_panels.py`, `quick_view.py`. It has no `common/` and no per-area packages.
- Its tests mirror it flat (`tests/test_bulk_actions.py`, `tests/test_filters.py`, `tests/test_actions.py`), with subfolders only for topic groups: `components/`, `invariants/`, `templatetags/`, `playwright/`. Same names as the module they test, which is the pattern `tests/panels/common/test_actions.py` and `test_bulk_actions.py` follow.
- `TYPE_CHECKING` is still used in `panel_framework/bulk_actions.py` (2), `context.py` (3) and `tables.py` (2). Those are not part of this spec. They show the idiom is accepted here, but the spec's change turns the four `educator_interface` ones into ordinary imports.
- There is no `views/` package under `freedom_ls/` (the glob `freedom_ls/**/views/__init__.py` finds only a tests one).
- The only precedent for a nested test layout mirroring a source subpackage is `freedom_ls/learner_interface/tests/views/` (`test_dashboard.py`, `test_course_player.py` and others). There the source is still a flat `views.py`, so the test folder groups by feature, not by module. Other apps use topic subfolders (`tests/models/`, `tests/management/commands/`, `tests/templatetags/`).
- `freedom_ls/educator_interface/tests/` has `invariants/`, `migrations/` and `playwright/` subfolders. `tests/panels/` is a new kind of subfolder there, holding mirrored source tests. Every `tests/` subfolder in the repo has an `__init__.py`, so `tests/panels/__init__.py` and `tests/panels/common/__init__.py` fit.

## 4. Takeaways for the spec

- Keeping `common/` as a leaf layer is the one rule every reference shares. State it as a check: nothing under `panels/common/` may import an area subpackage, or `views.py`, `actions.py`, `quick_views.py` and the other flat modules. If the flat modules import `common` and `common` imports a flat module, the cycle comes back. Where `common` still needs something that stays flat (for example `EducatorBulkAction` using the staff `interface_config`), the lazy import stays.
- Consider a guard test or import-linter-style check that fails if `panels/common` imports an area. No reference project has one. It is optional and small.
- Wagtail's `bulk_action/` split suggests keeping registry code out of `common/bulk_actions.py`. The spec already does that, since the registry moves to `panel_framework`.
- Nothing in these projects supports a re-export shim. Wagtail and oscar import directly from the defining module, which agrees with the spec's "no old path stays".

status: ok
