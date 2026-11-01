# Panel framework: the backend stands alone

Spec 3 of 6 in the Panel framework extraction effort. Read the "Panel framework extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The Python in `freedom_ls/panel_framework/` stops importing anything from `freedom_ls` outside itself,
and its unit tests run without FLS.

- **Settings helper.** The framework carries its own copy of `AppSettings` and `Setting` (today
  `config.py` imports them from `freedom_ls/base/app_settings.py`).
- **CSV helpers.** The framework carries its own `escape_csv_formula`, `EchoWriter` and `UTF8_BOM`
  (today imported by `tables.py` and `views.py` from `freedom_ls/base/csv_safety.py` and
  `csv_import.py`). Only these three symbols are copied, not the learner-import parsing in
  `csv_import.py`. FLS keeps its own copies.
- **Site handling.** `BulkActionRun` stops subclassing `SiteAwareModel` and keeps its `site` foreign
  key to `django.contrib.sites`. The framework resolves the request's site through a settings-declared
  callable that takes a request and returns a `Site`. The default is Django's `get_current_site`; FLS
  sets it to its own resolver. The framework does its own site filtering and its own site assignment on
  save, so a run is still only visible to, and created under, the request's site. The tenant isolation
  in `views.py` (the run listing and lookup) and `bulk_actions.py` (run creation) behaves exactly as
  today.
- **`TASKS`.** The framework runs large bulk actions through `django.tasks`, so the host must configure
  a durable `TASKS` backend. That requirement is declared, as a system check or a documented setting.
- **Standalone unit tests.** The framework's unit tests (the 16 non-component, non-invariant,
  non-Playwright files) run under a minimal settings module and a conftest that live in the framework's
  `tests/`, with no FLS root conftest and no `config.settings_dev`. The site-context and factory helpers
  they used from FLS (`drop_ambient_request`, `SiteFactory`, `mock_site_context`, `site`) are copied or
  replaced with minimal versions.
- **`lxml`.** The invariant test `tests/invariants/test_templates.py` imports `lxml`, which FLS only
  has transitively. The framework's test dependencies declare it.
- **Import guard.** A test fails when any framework Python file, tests included, imports `freedom_ls`
  from outside the framework.

## Why

The other Django project that wants the framework cannot install a package whose models and settings
helper import FLS. The Python has few couplings (the audit found three files importing from outside the
app, plus the tests), so this is the cheapest part of the extraction. Doing it before the move, in
place, lets the FLS suite prove nothing changed for educators. It also keeps a tenant-isolation change
(the site handling) in its own spec, so a regression cannot hide behind the template diff in spec 4.

## What is settled

- **No shared core package.** The copies of `AppSettings` and the CSV helpers are intentional; two
  copies of a security helper is the accepted cost. If the site handling cannot be done without a
  shared core package (for example because the resolver needs `site_aware_models` internals), the spec
  stops and says so. This is the effort's check on the extraction staying cheap.
- **Multi-site stays.** `BulkActionRun` keeps a required `site` foreign key to `django.contrib.sites`.
  It does not become nullable, and a single-site host relies on the default resolver instead of
  leaving the setting unset.
- **The fields stay byte-identical** so migration `0001_initial` is not rewritten. The app label
  `freedom_ls_panel_framework` and the `freedom_ls.panel_framework` name stay too: the label rename and
  the clean migration are spec 5's.
- **No abstract base class** is added to replace `SiteAwareModel`.
- **The background-run task keeps its signature**, `_run_bulk_action_task(run_id, site_id)`. A worker
  has no request, so it is handed the site id.
- **FLS's own suite stays green unchanged**, and the framework's unit tier no longer needs FLS. The
  component, invariant and Playwright tiers still use FLS templates until spec 4. Educators see no
  change.
- **The stale-run sweep and `RunStatus` reuse** are other specs' business: the sweep moves in spec 1,
  and `learner_management` importing `RunStatus` from the framework is already the right direction.
- **Test stand-ins.** The minimal settings use a small custom user model with email login (the helper
  `make_staff_user` creates users by email), and an in-test stand-in for anything the framework
  expects from the host that is not Python: a `site_name` context processor, the `c-icon` component
  and the page shell. Those host-contract pieces themselves are spec 4's, so the unit tests here stub
  only what they touch.
- **The unit tier is the target.** Component, invariant and Playwright tiers need the template contract
  and run standalone only after spec 4. This spec makes only the invariant test's `lxml` import
  resolvable.
- **Runs in parallel with spec 2.** Both edit `freedom_ls/panel_framework/tests/conftest.py`; whichever
  lands second rebases.

## Open until the spec

- How filtering reaches the request without FLS's thread-local: an explicit request-taking queryset
  method used by `views.py`, or an ambient request set by a framework middleware. The audit recommends
  the explicit form, with the manager owned by the framework and `site` passed on create. The
  constraint is that every read and write path, including the `_base_manager` use in `bulk_runs.py`
  and the worker (which has only a site id), stays isolated by site.
- The setting's name and shape, and whether the resolver result is cached on the request.
- Which of the two forms the `TASKS` requirement takes (a check that warns on an immediate or dummy
  backend when `BULK_BACKGROUND_THRESHOLD` could be crossed, or a documented setting only).
- Whether the minimal settings module and conftest live in `freedom_ls/panel_framework/tests/` and
  take effect through a pytest ini-option or a separate command, given that the FLS suite must keep
  running with `config.settings_dev` from the same tree. Spec 5 moves them with the package.
- Which test databases the standalone unit tests use (SQLite or PostgreSQL), chosen on purpose after
  checking whether any test relies on PostgreSQL-only behaviour.
- How the unit tests reach the framework's own `site`, `logged_in_client` and background-task fixtures
  (`database_task_backend` in the FLS root conftest) as minimal copies.

## Out of scope

- Rewriting migration `0001_initial`, the app label rename, check-id prefixes and ContentType
  handling: spec 5.
- Templates, JS, CSS, icons, the page shell, primitives, the Tailwind source command, and the
  component, invariant (beyond `lxml`) and Playwright tiers: spec 4.
- Moving generic code into the framework (including the stale-run sweep): spec 1.
- The package repo, its `pyproject.toml`, and installing it into FLS: spec 5.
- Any change to `SiteAwareModel` or `site_aware_models` for the rest of FLS.

## Resources

- `spec_dd/1. next/extract_panels_framework/research_coupling_audit.md`: P1 to P5, X1, X2, X4 to X6
  and X10, section 5 (minimal settings) and section 7 (the backend-and-tests recommendation).
- `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md`.
- `freedom_ls/panel_framework/models.py`, `config.py`, `tables.py`, `views.py`, `bulk_actions.py`,
  `bulk_runs.py`, `tasks.py`, `checks.py`, `apps.py`.
- `freedom_ls/site_aware_models/models.py` (the manager, the thread-local and `get_cached_site` being
  replaced), `freedom_ls/base/app_settings.py`, `freedom_ls/base/csv_safety.py`,
  `freedom_ls/base/csv_import.py`.
- `freedom_ls/panel_framework/tests/conftest.py`, `helpers.py`, `invariants/test_templates.py`;
  `freedom_ls/conftest.py`; `freedom_ls/tests/site_context.py`, `freedom_ls/tests/factories.py`.
- `config/settings_base.py` and `config/settings_dev.py` for FLS's `TASKS` and resolver wiring.
- Skills: `ds:app-settings`, `fls-dev:app-settings`, `fls-dev:multi-tenant`, `ds:testing`,
  `fls-dev:testing`.
