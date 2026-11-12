# Research: best practices (extract_panels_framework-1-gather-generic-code)

Only the django-filter page was fetched in this session. The other points come from established practice and the cited docs, and were not re-verified here.

## 1. Public API with per-module `__all__`
- `__all__` governs `from m import *` and signals the intended surface to readers and tools (PEP 8 "Public and internal interfaces": https://peps.python.org/pep-0008/#public-and-internal-interfaces). It does not enforce privacy.
- Practice: underscore-prefix helpers (`_helper`) *and* list public names in `__all__`. Underscore is the stronger signal and survives tools that ignore `__all__`.
- Do not re-export everything from the package `__init__.py` in a Django app. Importing models there breaks app loading ("apps aren't loaded yet"). Keep per-module surfaces (`models`, `filters`, `actions`) and let hosts import from those, as the user chose.
- Enforce with tests:
  - Parse host code with `ast` and collect `from freedom_ls.panel_framework.<mod> import name`. Assert each `name` is in `<mod>.__all__`.
  - Assert every `__all__` entry exists on the module.
  - Assert no underscore names are listed.
  - Optionally assert `views.py` helpers are all underscore-prefixed.
- Alternatives: import-linter contracts (https://import-linter.readthedocs.io/) can forbid host imports of private modules. `griffe` or `mypy --no-implicit-reexport` can check the surface.
- A host importing a name that is not public should fail the test, not be silently added to `__all__`.

## 2. Moving code between apps without data migrations
- Moving non-model code (mixins, forms, templates, JS) needs no migration. Moving models does: `SeparateDatabaseAndState` plus `db_table` or `AlterModelTable`. Docs: https://docs.djangoproject.com/en/stable/ref/migration-operations/#separatedatabaseandstate
- Here the models already live in `panel_framework` (`BulkActionRun`), so only Python and templates move. Run `makemigrations --check` after the move to prove nothing changed.
- With a single importer, update imports and delete the old modules. Compat aliases add untested surface that must later be removed (cf. Django's deprecation policy: https://docs.djangoproject.com/en/stable/internals/release-process/#deprecation-policy).
- Move code and its tests in the same commit.
- Template paths and cotton component names are also import paths. Grep for `c-modal-trigger`, `{% include %}` and `{% extends %}` references to the old app. Static JS moves need the `<script>` includes updated.
- Add no new `freedom_ls` imports beyond the existing ones, and list the ones that remain (as the idea requires).

## 3. Host-raised error type for a "too large" lazy region
- Pattern: the framework defines a small exception, for example `class RegionUnavailableError(Exception)`, with a user-facing `message` attribute. The host raises it, or translates its own error into it. The framework catches only that type, so it never imports host exceptions (dependency inversion).
- Django precedent: `ValidationError`, `PermissionDenied` and `Http404` are framework-defined exceptions that host code raises and the framework turns into responses. Docs: https://docs.djangoproject.com/en/stable/ref/exceptions/
- Make the message a constructor argument and keep it plain text (auto-escaped in the template). Subclass it for the host's specific case so host `except` clauses stay specific.
- Test it by raising it from a stub panel and asserting the rendered region shows the message. Also test that an unrelated exception propagates.
- Put it in a public module's `__all__`.

## 4. Generic bulk-action base class and registry
- Template method: the base class owns the fixed flow (`permitted` → `skip_reason` → `perform`, then `sentence` / `consequences`) and subclasses override only the hooks. Reference: https://refactoring.guru/design-patterns/template-method
- Django's own `ModelAdmin.actions` and `admin.site.register` are the canonical precedent (https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/), along with the `register` decorator.
- Registry practice:
  - A module-level `dict[table_key, list[type[Action]]]`, filled by a decorator.
  - Reject duplicate keys and names loudly.
  - Fill it at import time, with a documented place for hosts to import their actions (`AppConfig.ready()` or an autodiscover step as in `admin.autodiscover`: https://docs.djangoproject.com/en/stable/ref/applications/#django.apps.AppConfig.ready).
  - Provide a test helper to isolate or clear the registry, so tests don't leak.
- Keep the scoping, capability and notification logic in the host subclass. The base class declares the hooks and does not call them with host-specific arguments.
- Test the base class with a stub subclass, and test the registry for ordering, duplicates and unknown tables. The host keeps tests only for its own overrides.

## 5. Generic filters in table libraries
- django-filter fetched source: https://django-filter.readthedocs.io/en/stable/ref/filters.html
  - `BooleanFilter` is the toggle building block.
  - `DateFromToRangeFilter` takes a field name and uses `_after` / `_before` suffixes.
  - `DateRangeFilter` offers preset windows in the style of the admin changelist.
  - Custom filters take `field_name`, `lookup_expr` and `method`.
  - Both filters are configured by field name, not hard-coded to a model.
- django-tables2 leaves filtering to django-filter (`FilterView` / `SingleTableMixin`): https://django-tables2.readthedocs.io/en/latest/pages/filtering.html
- Admin's `SimpleListFilter` and `DateFieldListFilter` (with presets such as today, past 7 days, this month) are the reference for preset windows: https://docs.djangoproject.com/en/stable/ref/contrib/admin/filters/
- Practice for a period filter:
  - Presets are data: `{key: (label, timedelta or callable)}`.
  - Resolve "now" through a clock argument or Django's `timezone.now`, so tests can freeze it.
  - Use half-open ranges, `[start, now]` or `[start, end)`.
  - Validate unknown keys as empty, or as an error, not as a crash.
  - Name the filter for the behaviour (`TogglePeriodFilter`, not `AuditPeriodFilter`) and pass the field name in the constructor.
- Decide the constructor shape: keep the old signature only if every existing table needs it, otherwise use keyword arguments with defaults that reproduce the current behaviour. Cover every current table with a regression test.

## 6. Housekeeping sweeps as plain callables
- Plain functions, such as `reap_stuck_runs(now=None, *, older_than=...) -> SweepResult`, are the most portable. The host decides whether to run them from cron, Celery beat, `django-q`, or a management command wrapper (https://docs.djangoproject.com/en/stable/howto/custom-management-commands/).
- Precedent: Django's `clearsessions` management command is a thin wrapper around `SessionStore.clear_expired()`. django-celery-results offers `backend_cleanup` as a task, and `django-axes` offers `reset`. The logic lives in a callable, with scheduling outside.
- Practice:
  - Take `now` and the thresholds as parameters, with defaults from settings.
  - Use idempotent bulk `update()` / `delete()` with status filters, so overlapping runs are safe.
  - Return counts for host logging.
  - Document in the README how a host schedules it.
  - Retention deletion should be separate from reaping, so a host can run them on different cadences.
- Test with a frozen clock and rows in each state. Assert terminal and young rows are untouched.

## 7. Testing a reusable cotton/HTMX/Alpine component library
- django-cotton: render components in tests with `django.template.Template("<c-panel-stat-row .../>").render(Context(...))`, or `render_to_string` on a stub template. Assert on parsed HTML (`BeautifulSoup`, `lxml`), not exact strings. Docs: https://django-cotton.com/docs/
- Per component, test default slot and attributes, each variant, empty or missing data, and HTML escaping. Prefer a parametrised test over one per component.
- Playwright on stub pages: serve a minimal test-only view or template in the library's test settings (as the library's own tests do), with a stub panel. Use `pytest-playwright` with `live_server`: https://playwright.dev/python/docs/test-runners. Wait on DOM state (`expect`) rather than sleeps. Alpine components `tableSelection`, `listRefresh` and `headerRefresh` can be driven by stub HTMX endpoints.
- Alpine registration check: a plain pytest that regex-scans templates for `x-data="name"` (and `x-data="name(...)"`), parses `Alpine.data('name', ...)` in `alpine-components.js`, and asserts the first set is a subset of the second. Allow-list inline object literals (`x-data="{`). This catches a template depending on a component that moved. Alpine docs for `Alpine.data`: https://alpinejs.dev/globals/alpine-data
- Include a test that the framework JS defines each name exactly once. This is especially relevant for `sidePanel` and `refreshTimer`, so `base` and `comms` stop defining duplicates.
- Keep the host's cross-check tests (educator Playwright) running until the move is verified, then trim them to what the host still owns.

## Recommendations for the spec
1. Add an AST-based surface test plus an `__all__` integrity test.
2. Run `makemigrations --check` after the move.
3. Define a framework exception carrying `message`, which is the only thing the lazy region catches.
4. Use a template-method base with a registry that rejects duplicates and can be cleared in tests.
5. Make the housekeeping sweep a pure function taking `now`, returning counts, with reap and retention split.
6. Add the Alpine-name registry test, with a duplicate-definition check.

status: ok · reason: complete; only django-filter docs were fetched live
