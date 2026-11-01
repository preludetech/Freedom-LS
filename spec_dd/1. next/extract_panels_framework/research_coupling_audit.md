# Research: coupling audit of `freedom_ls/panel_framework`

Audit date 2026-11-01, against `main` at 1593cb126. Everything below was grepped from the tree.
It checks and corrects the "Couplings that must be severed" table in
`research_packaging_and_distribution.md`. Size scale: S = under an hour, M = a few hours with
tests, L = a day or more or needs a design decision.

Package size: about 4,900 lines of Python outside `tests/`, 94 templates (43 under `templates/cotton/`
or `templates/panel_framework/` that are fragments, 24 cotton components), one 995-line JS file, one
model, one migration.

## Headline

1. **The existing research is wrong about the app label.** `apps.py:7` sets
   `label = "freedom_ls_panel_framework"` (name `freedom_ls.panel_framework`). The table is
   `freedom_ls_panel_framework_bulkactionrun`, the index is `freedom_ls__scope_t_9e7b0b_idx`
   (`migrations/0001_initial.py:43`), the check ids are `freedom_ls_panel_framework.E001..E008`, and
   ContentType rows use that label. "Keep the top-level package named `panel_framework`, so
   `app_label = panel_framework`" does not hold: moving the package under the old label means
   `AppConfig.name = "panel_framework"` with `label = "freedom_ls_panel_framework"` kept, or a rename
   migration. The migration is dated 2026-10-27, so whether any database holds it is a fact the owner
   must supply.
2. **The Python is much cleaner than the templates.** Only 3 non-test files import from outside
   the app (`models.py`, `config.py`, `tables.py`/`views.py` for CSV helpers). The templates and
   JS depend on a large unwritten host contract: a page shell, 10 FLS cotton components, 22 icon
   names, FLS theme tokens, base-bundle Alpine components, and a `comms` Alpine component.
3. **The test suite is not standalone.** 18 of its files lean on `freedom_ls/conftest.py`
   fixtures (343 references), the playwright fixtures, FLS's user model, FLS's
   `config.settings_dev`, and a test shell that extends FLS's `_base_interface.html`.
4. **Recommendation: split into two decoupling specs** (backend and test harness; template, JS and
   styling contract), then the mechanical move as a third. See the end.

## 1. Couplings from the framework to FLS

### 1a. Python

| # | Coupling | file:line | Resolution (confirm or correct) | Size |
| --- | --- | --- | --- | --- |
| P1 | `BulkActionRun(SiteAwareModel)`. Brings (a) UUID pk, (b) `site` FK to `sites.Site`, (c) `SiteAwareManager` as `objects`, which filters by the ambient request's site through a thread-local FLS middleware sets, (d) `save()`/`full_clean()` that fill `site` from that thread-local. | `models.py:13,26`; read path `views.py:974` (`BulkActionRun.objects.filter`), write path `bulk_actions.py:330` (`objects.create`); `_base_manager` use `bulk_runs.py:77` | **Corrects** the old row. "Keep the FK, make request-to-site resolution a settings callable" is not enough: the manager and the save hook are the tenant isolation, and the package has no thread-local. Replace with a package-owned manager and explicit `site` on create, resolved by a settings-declared callable (`request -> Site`). Views pass the request into the query (`BulkActionRun.objects.for_request(request)`). Keep the fields byte-identical so migration 0001 is unchanged. Re-point the tests (`drop_ambient_request`, `mock_site_context`). Needs a design decision, see Decisions. | L |
| P2 | `AppSettings`, `Setting` | `config.py:17` -> `freedom_ls/base/app_settings.py` (75 lines, pure Django) | Confirm: copy in. Also copy the ~6-line `required_settings_errors` only if a required setting is ever added (none today). | S |
| P3 | `escape_csv_formula` | `tables.py:12` -> `freedom_ls/base/csv_safety.py` | Confirm: copy in. `csv_safety.py` has two symbols (`escape_csv_formula`, `UTF8_BOM`). | S |
| P4 | `EchoWriter`, `UTF8_BOM` | `views.py:32-33` -> `base/csv_import.py:135`, `base/csv_safety.py` | Confirm: copy the 8-line `EchoWriter` and `UTF8_BOM`. Do **not** copy `csv_import.py` (it holds learner-import parsing). FLS then keeps its own copies; two copies of a security helper is the cost. | S |
| P5 | `django.tasks` background runs | `tasks.py:9,19`; `bulk_actions.py:343` (`.enqueue`) | Not an import coupling (`django.tasks` is Django 6). It is a host contract: the host configures `TASKS` with a durable backend (FLS uses `django_tasks_db`, `config/settings_base.py:86,610`, `settings_prod.py:87`). Document it; add a system check that warns when the default backend is the immediate or dummy one and `BULK_BACKGROUND_THRESHOLD` could be crossed. | S |
| P6 | **Missed:** the stale-run sweep lives in FLS. `mark_unpicked_runs_failed` / `_close_as_failed` close QUEUED and RUNNING `BulkActionRun`s as FAILED and call `report_finished`, with Sentry. | `deployment/housekeeping.py:27-28,255-284` (imports `bulk_runs.report_finished`, `models.BulkActionRun`, `RunStatus`) | A host that installs the package alone has runs that can stick forever. Move the sweep (without Sentry) into the package as a management command or function the host schedules; FLS's housekeeping calls it and keeps the Sentry reporting. Reverse-direction import stays valid (FLS depends on the package). | M |
| P7 | **Missed:** FLS domain code reuses `RunStatus` | `learner_management/models.py:12,318-321` | Reverse direction only; becomes `from panel_framework.models import RunStatus`. Note that `learner_management` now depends on the extracted package for an enum. Acceptable, but the spec should say so. | S |
| P8 | App label / check ids / stub app labels hard-coded | `apps.py:6-7,13`; `checks.py` 8 ids (lines 77-262); `tests/stub_models.py:27,44,56,68`; `tests/conftest.py:42,65`; `tests/stub_panels.py:100,104`; `test_panels.py:81`; `test_actions.py:313,328`; `test_field_display.py:60`; `test_checks.py` (10) | 32 occurrences in 9 files. Decide the label first (Decisions); then it is search-and-replace. If the label is kept, none change. | S |
| P9 | `request.panel_url_kwargs`, `request.panel_scope_name` | `views.py:1395`, `panel_tags.py:149,166`, `document_title.html:21` | Host-set request attributes read with `getattr(..., default)`. Already optional. Document in the contract. FLS sets them in `educator_interface/views.py:1884`. | S |
| P10 | Template variable `site_name` required by `navigation_response.html:15` -> `document_title.html:21` | templates | Comes from an FLS context processor. Host contract; give it a `{{ site_name|default:"" }}` fallback or a setting. | S |
| P11 | `config/urls.py:101` includes `panel_framework.urls` under `DEBUG` (component reference page) | `urls.py`, `reference.py` | Package keeps `app_name = "panel_framework"` (URL namespace, unrelated to the label). Host `include`s it. Confirm. | S |

No use of `django-guardian`, `ObjectRoleAssignment`, `accounts`, `educator_interface` or any other FLS
model. Permissions already go through host hooks on `SectionConfigBase` (`has_capability`,
`authorise_instance`, `get_scope`, `check_request`, `views.py:115-250`), deny by default. `AUTH_USER_MODEL`
is the only user dependency (`models.py:43`, migration `swappable_dependency`). No management
commands exist. System checks: one (`checks.py`, `check_panels`, registered in `apps.py:13`); it imports
`settings.ROOT_URLCONF` (`checks.py:38`), host-agnostic.

### 1b. Templates (host contract)

Grep of `{% extends %}`, `{% include %}`, `{% load %}`, `<c-...>`:

| # | Coupling | file:line | Resolution | Size |
| --- | --- | --- | --- | --- |
| T1 | `{% extends "_base.html" %}` | `reference/component_reference.html:1` | Confirm: make the base template a setting (default a package-shipped minimal shell). Also the test twin `tests/templates/.../test_component_reference.html:1`. | S |
| T2 | `c-page` | `component_reference.html:6` | Folded into T1; page shell is only used by the reference page. | S |
| T3 | `c-button` (variants primary/secondary/ghost/error; `size`, `href`, `loading`, `loading_text`, `dropdown`, `icon_left`, `disabled`, `x-on:*` passthrough) | 16 templates, e.g. `table_selection_bar.html:45,67,80`, `modal/form.html:13-54`, `delete_confirmation.html:28-34`, `modal_host.html:77-78`, `quick_view_host.html:142-164`, `table_toolbar.html:149-152`, `table_sheet.html:103-104`, `panel-attention-row.html:58`, `bulk_confirmation_form.html:18`; button.html is 106 lines | Not a "small one" to copy: variants, loading state, dropdown mode. See Decisions D3 (host contract with package-shipped overridable defaults). | M |
| T4 | `c-button-group` (89 lines; variant `right`) | `panel-card.html:52`, `panel-page-header.html:43`, 8 modal fragments | As T3. | S |
| T5 | `c-chip` (variants, `size="xs"`, `:attrs`) | `panel-status-badge.html:20`, `table_toolbar.html:57,72,88,132` | As T3 (26 lines; copy is cheap). | S |
| T6 | `c-pagination` (223 lines; takes `page_obj`) | `data-table.html:148`, `table_selection_bar.html:91` | Genuinely large. Either move into the package (it is a table component) or contract it. Recommend move: only data tables in the panel kit need it, but FLS's other apps also use it, so FLS keeps its copy too. | M |
| T7 | `c-dropdown-menu` (94 lines, needs Alpine `dropdownMenu` from the base bundle, `base/static/base/js/alpine-components.js:81`) | `table_selection_bar.html:59` | Template plus JS pair. Ship both in the package or contract both. | M |
| T8 | `c-callout`, `c-back-link` | `_examples.html:362`, `breadcrumbs.html:11` | Small; as T3. | S |
| T9 | **`c-modal-trigger`, `c-quick-view-trigger`** live in FLS `base/templates/cotton/`, 13 and 19 lines. Their own comment points at `panel_framework/.../alpine-components.js`. | `partials/modal_trigger.html:1`, `data-table-cells/link.html:26`; `base/templates/cotton/quick-view-trigger.html:5` | **Corrects** the old row, which listed them as "FLS base components". They belong to the framework: **move** them into the package (FLS's `base` then has none to keep). Their `base/static` JS mentions (`alpine-components.js:156,387`) are comments. | S |
| T10 | `c-icon` with 22 names (below) plus dynamic names from host data (`icon` on panel-empty-state, attention-row, sidebar items) | `c-icon` is `freedom_ls/icons/templates/cotton/icon.html`, backed by `{% load icon_tags %}` and a closed registry `icons/semantic_names.py` | Confirm: host contract. Static names used: `check close dropdown loading menu next search sort_asc sort_desc sort_neutral open_page quick_view trend_up trend_down boolean_true boolean_false` and via `c-button icon_left`: `add filter retry`. (The old row listed 7; real count is 21 static.) All exist in FLS's registry. Package ships a documented list and a system check that renders each. | M |
| T11 | `{% extends "_base_interface.html" %}`, `partials/page_title.html`, blocks `header footer sidebar_content content_header_top quick_view_host modal_host extra_alpine_components page_title sidebar_storage_key` | `tests/templates/panel_framework/test_interface.html:1-57` | **Missed** by the old table. This is the real "page shell" contract: the framework's `modal_host`, `quick_view_host`, `announcer_host`, `sidebar_nav`, `breadcrumbs`, `document_title` fragments are included by the *host's* shell (`educator_interface/templates/educator_interface/_shell.html:5,36,71,79,83,90,94`). The package needs its own minimal shell for tests and docs; the production shell stays host-owned. | M |
| T12 | `{% load %}` of panel_tags / data_table_tags only | 15 files | Package-internal. No external `{% load %}`; `static` only in the test shell. | none |
| T13 | `{% url %}`, `{% static %}` in package templates | none outside the test shell (`test_interface.html:10`) | Clean. URLs are built in Python with `reverse(url_name, kwargs={"path_string": ...})` (`views.py:1314,1364,1406`, `panel_tags.py:167`) using a host-supplied `url_name`. | none |
| T14 | `django-cotton` itself | whole `templates/cotton/` tree; `tests/cotton_helpers.py:10` imports `django_cotton.compiler_regex.CottonCompiler` | Runtime dependency `django-cotton>=2.1.3`. The compiler import is an internal module of cotton; the helper breaks on a cotton refactor. Note in the spec. | S |
| T15 | Template overrides: `tests/template_overrides/panel_framework/panels/panel.html` | `tests/invariants/test_templates.py:27` | Package-internal, fine. | none |

### 1c. JS and htmx

One file: `static/panel_framework/js/alpine-components.js` (995 lines, Alpine CSP build, no build step,
no imports). It registers `appModal`, `quickView`, `tableSelection`, `listRefresh`, `headerRefresh` and
store `bulkRuns`, plus document-level htmx listeners. The header comment says load it after the base
`alpine-components.js` and before Alpine. Couplings:

| # | Coupling | where | Resolution | Size |
| --- | --- | --- | --- | --- |
| J1 | Templates use `x-data="sidePanel"` (base bundle, `base/.../alpine-components.js:403`) | `table_toolbar.html:127` (the mobile filter sheet); and the host shell wraps the whole interface in it, as `appModal` and `quickView` comments assume ("nested in sidePanel's x-data scope") | The mobile filter/sort sheet is the framework's, so it needs `sidePanel` (or an equivalent). Move a framework copy, or reduce the sheet to its own small component. Verify: `appModal`/`quickView` already prefix state names to avoid colliding with the host's `sidePanel` scope, a shared-scope contract. | M |
| J2 | **`x-data="refreshTimer"`** and event `conversationChanged` in `sidebar_nav.html:26` | `refreshTimer` is defined in **`comms/static/comms/js/alpine-components.js:167`**, and `conversationChanged from:body` is a `comms` event | **Missed.** A framework template names an FLS app's component and event. Fix: move `refreshTimer` into the framework JS, make the refresh event list a field on the menu item (`count_refresh_events`), default empty. | M |
| J3 | Fixed DOM ids: `#main-content`, `#interface-main`, `#app-modal`, `#app-modal-body`, `#quick-view*`, `#instance-header`, `#sidebar-nav` | JS lines 53-56 (`main-content`), 28 (`interface-main`), 828 (`app-modal`), `quick_view_host.html:57,82` (CSS on `#interface-main`) | Host-shell contract. `#interface-main` also appears in `base/static/base/js/interface-swap-fallback.js:9-10`, which is FLS-owned and also needs the response to contain it. Document the ids; fine to keep. | S |
| J4 | `htmx` 2.x as a global, Alpine CSP build, `@alpinejs/collapse` unused by the package | `_base.html:54-71` loads them from jsdelivr CDN | Host provides htmx and Alpine; document versions. Check the package templates use only CSP-safe expressions (host runs the CSP build). | S |
| J5 | Load order: package JS must be before Alpine initialises, after the base bundle | comment at JS top; `test_interface.html:10` | Document; trivial in the host. | S |
| J6 | `window.location.reload()` on unmarked 403/404 for htmx user actions | JS lines 16-34 | Behavioural default, package-owned. | none |

### 1d. Styling and Tailwind

| # | Coupling | Resolution | Size |
| --- | --- | --- | --- |
| S1 | Tailwind `@source "./freedom_ls/**/templates/**/*.html"` (`tailwind.input.css:10`) scans package templates only because they are inside the FLS tree. | Confirm the old row: a generated `@source` CSS (like `write_active_theme_css`). Also scan the package's `.py` files if class strings live there (none seen; `tone_text_class.html` is a template). | M |
| S2 | **Role tokens** used as utilities (host's Tailwind theme must define them): colour roles `primary`, `on-primary`, `surface`, `surface-2`, `on-surface`, `muted`, `border`, `error`, `success`, `on-success-light`, `on-warning-light`, `on-error-light`, `on-info-light`, `focus-ring`; plus raw CSS vars `--color-primary`, `--color-secondary`, `--color-accent`, `--color-info`, `--color-surface` (avatar slots in `panel-avatar-chip.html:37-41`, sidebar bar `sidebar_nav.html:23`). `bg-sidepanel` is only in FLS's own shell. Package has an invariant forbidding raw hex and raw palette classes (`tests/invariants/test_templates.py:31-36`), so the token set is closed and enumerable. | Document the closed set; ship a reference `theme.css` block for the tests and for hosts. | M |
| S3 | **Component-layer CSS classes** defined in FLS's `tailwind.components.css`: `.panel-surface`, `.panel-canvas` (lines 224-228; themes override them, e.g. `themes/first_class/.../theme.css:156,160`), `.modal-backdrop-host` (line 360), `.btn`, `.btn-secondary` (used in `table_selection_bar.html:59`). `_main_base.html` says "the two surfaces are .panel-surface and .panel-canvas in tailwind.components.css". | `.panel-surface/.panel-canvas/.modal-backdrop-host` move to a package CSS file the host imports (the same generated-import mechanism as S1). `.btn*` goes with the button decision (T3). | M |
| S4 | `tests/invariants/test_templates.py:18,29` reads `FREEDOM_LS_PACKAGE_DIR.parent / "tailwind.components.css"` | Confirm: repoint at the package's own CSS file. | S |
| S5 | Playwright tests rely on compiled Tailwind (`md:hidden`, overflow assertions) | The package's CI needs a Tailwind build with the package CSS. Adds `node`/`tailwindcss` to package dev tooling. | M |

### 1e. Tests -> FLS

| # | Coupling | file:line | Resolution | Size |
| --- | --- | --- | --- | --- |
| X1 | `freedom_ls.tests.site_context.drop_ambient_request` | `test_bulk_runs.py:25`, `test_tables.py:29` | Tied to P1; becomes a package fixture once the site resolver exists. | S |
| X2 | `freedom_ls.tests.factories.SiteFactory` | `test_models.py:13` | Replace with `Site.objects.create`. | S |
| X3 | `freedom_ls.tests.playwright_helpers` (`assert_no_horizontal_overflow` + 3 others; imports only `playwright`) | `playwright/test_create_modal_flow.py:16`, `test_instance_dialogs_flow.py:14`, `test_data_table_flow.py:19`, `test_quick_view_flow.py:15`, `test_component_reference_flow.py:22` | Copy the used helpers. | S |
| X4 | Root `freedom_ls/conftest.py` fixtures: `site`, `mock_site_context`, `logged_in_client`, `live_server_site`, `logged_in_user`, via `freedom_ls/tests/playwright_fixtures.py`; 343 references in 18 test files; `UserFactory` (accounts) | `conftest.py:174-272`, `playwright_fixtures.py:172` | Package gets its own `conftest.py` with minimal versions. `mock_site_context` becomes "set the site resolver". Bulk of this unit's work. | L |
| X5 | `helpers.make_staff_user` calls `User.objects.create_user(email=..., is_staff=True)` | `tests/helpers.py:20-28` | Requires an email-login user model. Package tests should ship a tiny custom `AUTH_USER_MODEL` (or use `username` and adapt). | S |
| X6 | Test settings: `DJANGO_SETTINGS_MODULE = "config.settings_dev"` (`pyproject.toml:79`) | whole suite | See section 5. | M |
| X7 | `FREEDOM_LS_PACKAGE_DIR` | `invariants/test_templates.py:18` | = S4. | S |
| X8 | Test shell extends FLS `_base_interface.html` and `_base.html` | `tests/templates/panel_framework/test_interface.html:1`, `test_component_reference.html:1` | = T11. | M |
| X9 | Namespace-package hazard noted in `conftest.py:18-24`: "no `freedom_ls/__init__.py`" makes pytest import the tests as `panel_framework.tests.*` | `conftest.py`, `stub_panels.py:11-17` | Goes away when the package has a normal root with `__init__.py`; remove the relative-import workaround afterwards (optional). | S |
| X10 | Stub models registered at runtime against the app label | `tests/conftest.py:42-78` | Works unchanged if the label is kept; otherwise P8. | S |

## 2. Other things the old table missed (checked, status)

| Area | Finding |
| --- | --- |
| `django-guardian` / permission hooks | No guardian import. Authorisation is entirely host hooks on `SectionConfigBase`; deny by default. Clean. |
| `django.tasks` for bulk runs | Used; host must configure `TASKS` (P5). Task is `@task()` `_run_bulk_action_task(run_id, site_id)`; the `site_id` argument exists because FLS has no ambient site in a worker. The signature can stay. |
| htmx | Assumes htmx 2.x global, HX-Trigger, HX-Location, `hx-preserve`, `htmx:*` events, 422 on validation errors. Host must send the `X-CSRFToken` header globally (`hx-headers` on body, per FLS convention) because package forms are POSTed by htmx. |
| `SiteAwareModel` | P1. Largest single design item. |
| Migrations | Exactly one: `0001_initial.py` (generated 2026-10-27, Django 6.0.4). Dependencies: `contenttypes.0002`, `sites.0002`, `swappable_dependency(AUTH_USER_MODEL)`. No dependency on any FLS app migration. The only `freedom_ls` string is the auto index name (`freedom_ls__scope_t_9e7b0b_idx`), which follows the table name; it stays valid as long as the label (hence the table name) is kept. |
| Management commands | None in the package. (`qa_create_bulk_operations_scenario` in FLS touches `BulkActionRun`; stays FLS.) |
| System checks | `check_panels` (E001-E008), host-agnostic apart from the id prefix. Plan to add: icon-names check, `TASKS` check, base-template check. |
| Static | One JS file; `{% static 'panel_framework/js/alpine-components.js' %}` is loaded by the host shell (`_shell.html:5`). Packages ship static via `package-data`. |
| Setting reads | Only `BULK_BACKGROUND_THRESHOLD` (default 250) through `AppSettings`, plus `settings.AUTH_USER_MODEL`, `settings.ROOT_URLCONF`. After P1: a site-resolver setting. After T1: a base-template setting. |

## 3. Reverse direction: what in FLS imports or uses the framework

Python imports of `freedom_ls.panel_framework` outside the app: **55 lines in 22 files**.

| App | Files | Lines | Notes |
| --- | --- | --- | --- |
| `educator_interface` (prod) | `views.py`, `actions.py`, `reporting.py`, `learner_import.py`, `quick_views.py`, `filters.py`, `templatetags/educator_tags.py`, `notification_urls.py` | 25 (views 9, actions 6, reporting 4, learner_import 2, others 1 each) | The bulk of the rename. |
| `educator_interface` (tests) | `test_filters`, `test_actions`, `test_views`, `test_cohort_delete_action`, `test_create_cohort_action`, `test_notification_urls`, `interface_walk`, `invariants/test_config_authorisation`, `invariants/test_organisation_isolation` | 23 | |
| `deployment` | `housekeeping.py`, `tests/test_housekeeping.py` | 4 | See P6. |
| `learner_management` | `models.py` | 1 | `RunStatus` (P7). |
| `qa_helpers` | `management/commands/qa_create_bulk_operations_scenario.py` | 1 | |
| `base` | `tests/error_pages_urls.py` | 1 (comment) | |
| `config` | `settings_base.py:129` (INSTALLED_APPS), `urls.py:101` | 2 | |
| non-Python | `test_organisation/import_contracts.toml` (36 hits), `import_baseline.txt`, `mirroring_baseline.txt`, `mirroring_exemptions.txt`, `docs/app_structure.md` (13), `claude_plugins/fls-dev/skills/{alpine-js,testing}/SKILL.md` | | The contract files regenerate (`/ds:app_map`); docs and two fls-dev skills need hand edits. |

Templates using the framework by path (`{% extends/include "panel_framework/..." %}`): 18 references in
`educator_interface` (`_shell.html` x7, ten panel templates extending `panel_framework/panels/panel.html`
or `_panel_base.html`, six modal templates extending `modal/read_only.html` / including `modal/form.html`).
These use the template *directory* name, not the app label, so **they do not change** if the package keeps
the `panel_framework/` template namespace.

Cotton usage: `c-panel-*`, `c-data-table*`, `c-modal-header`, and `panel_tags`/`data_table_tags`
appear in **52 files, 169 occurrences** outside the app. Two are not in `educator_interface`:
`comms` (`recipient_picker.html`, `participant_avatar.html`, `conversation_list.html` use
`c-panel-search-field`, `c-panel-avatar-chip`, `c-panel-empty-state`; so the learner-side messaging
UI depends on the package) and `content_engine/cotton/table.html` (a comment only). Names do not change.
So `comms` becomes a second consumer; the old research lists only `educator_interface`,
`learner_management`, `deployment`, `base`, `qa_helpers`.

The rename is therefore mechanical: 22 Python files plus two settings lines plus docs, and no template edit.

## 4. Third-party dependencies for the package's own `pyproject.toml`

From FLS `pyproject.toml` and the code:

| Need | Where | Package dependency |
| --- | --- | --- |
| Django 6.x (`django.tasks`, `contenttypes`, `sites`, `auth`, templates `{% querystring %}` and `{% partialdef %}`, used at `table_toolbar.html:118`, `document_title.html:21`) | everywhere | `django>=6.0,<6.1` (matches FLS `>=6.0.4,<6.1`) |
| `django-cotton>=2.1.3` | `templates/cotton/` | runtime dependency |
| Task backend, e.g. `django-tasks-db` | host `TASKS` | **not** a package dependency; document (dev-only for the suite) |
| `psycopg` / PostgreSQL | FLS DB | none required; check whether tests rely on Postgres-only JSON lookups (not seen) and pick SQLite or Postgres for the suite deliberately |
| Dev/test: `pytest`, `pytest-django`, `pytest-mock`, `pytest-playwright`, `lxml` (invariant test `test_templates.py:9`; **not** declared in FLS, only transitive), `time-machine`, `pytest-socket`, `pytest-randomly`, `pytest-timeout`, `ruff`, `djlint` (custom_html `c-\w+`), `pytest-xdist` | tests | a `dev` dependency group; `lxml` must be added explicitly |
| `factory-boy` | not used by framework tests directly (only `SiteFactory`/`UserFactory` via FLS) | not needed once X2/X4 are done |
| Node/Tailwind | playwright and invariant tests | dev tooling, not a Python dependency |

No `nh3`, `markdown`, `guardian`, `allauth`, `httpx`, or `weasyprint` is imported by the framework.

## 5. Can the suite run under minimal standalone settings?

Yes, after the work in 1e, and the stubs already help: `tests/stub_models.py`, `stub_panels.py`,
`root_urls.py`, `urls.py`, `helpers.py` and `cotton_helpers.py` need nothing from FLS except the items
below.

Minimum settings module:

- `INSTALLED_APPS`: `django.contrib.{auth,contenttypes,sessions,sites,messages,admin}` (admin because
  `root_urls.py:12` mounts `admin.site.urls` so `admin:login` reverses), `django_cotton`, the package, a
  tiny user app, and the host-supplied icon app (a stand-in shipping the 22 names).
- `TEMPLATES` with `DIRS` + `APP_DIRS`, cotton loader, request context processor, and a stand-in context
  processor supplying `site_name`.
- `AUTH_USER_MODEL` pointing at a minimal email-login model (`helpers.make_staff_user`).
- `ROOT_URLCONF` is already overridden per test (`conftest.py:129`).
- `TASKS` immediate backend; a second fixture switches to the database backend for background-run tests
  (copy `database_task_backend`, `freedom_ls/conftest.py:355-361`).
- Middleware and the P1 site resolver.
- `STATIC_URL`, and a compiled `tailwind.output.css` for the browser tests.

Test tiers:

| Tier | Files | Standalone readiness |
| --- | --- | --- |
| Unit (`test_actions`, `test_bulk_actions`, `test_bulk_runs`, `test_checks`, `test_context`, `test_events`, `test_field_display`, `test_filters`, `test_models`, `test_panels`, `test_quick_view`, `test_reference`, `test_run_records`, `test_tables`, `test_views`, `templatetags/`) | 16 | Need X1, X2, X4, X5, X6 only. Ready after backend spec. |
| Component (`components/`, 10 files, via `render_cotton`) | 10 | Need the primitives present (T3-T10), i.e. the template-contract spec. |
| Invariants (`invariants/test_templates.py`) | 1 | Need S4/X7, lxml. |
| Playwright (5 flow files + `playwright/assertions.py`) | 5 | Need X3, X4, X8 shell, S5 Tailwind build, live-server fixtures. Last to move. |

## 6. Decisions the spec must make

- **D1. App label.** Keep `freedom_ls_panel_framework` as the label (zero DB impact, ugly) versus rename
  to `panel_framework` with a migration that renames the table, index, ContentType and permissions
  (breaks deployed `check` ids and history; only safe if no database holds migration 0001).
  Needs the owner's answer on whether `0001_initial` (dated 2026-10-27) is applied anywhere, including
  First-Class and production.
- **D2. Tenant model.** Package-owned manager plus explicit site (recommended), versus a swappable
  abstract base set by a setting (rejected: migration-hostile, and "Don't create abstract base classes unless asked").
  Also decide whether a single-site host must be able to leave the resolver unset (then the `site` FK
  would be nullable, which changes migration 0001; recommend keeping it required and shipping a default
  resolver based on `django.contrib.sites.shortcuts.get_current_site`).
- **D3. Primitive components.** Options: (a) pure host contract with a documented prop list; (b) the package
  ships default `cotton/button.html`, `button-group`, `chip`, `callout`, `back-link`, `page`, `icon` that any
  host overrides by template precedence (project `DIRS` and earlier apps win). Option (b) gives a new host a
  working kit; FLS keeps its own copies and wins by ordering. Recommend (b) plus a contract test that renders
  every primitive both ways. Does not apply to `pagination`, `dropdown-menu`, `modal-trigger`,
  `quick-view-trigger`, which are the package's own (T6, T7, T9).
- **D4. Where `sidePanel` lives** (J1) and how `refreshTimer` becomes framework-owned (J2).
- **D5. Keep the sweep in FLS or move it** (P6). Recommend a package function plus FLS wrapper.

## 7. Size and split recommendation

Total decoupling work: P1 (L), X4 (L), the shell and primitives (M, M, M), JS (M, M), Tailwind (M, M, M),
plus a handful of S. That is more than one run can verify in one PR and, more importantly, it breaks into
two outcomes that are independently demonstrable.

**Spec 1: "Panel framework backend and tests stand alone" (recommended first).**
Covers P1-P11, X1-X2, X4-X7, X9-X10, the backend half of section 5. User-visible outcome: bulk actions,
tables, panels, views, filters, checks behave identically in FLS (educators see no change), and the
framework's non-browser, non-template tests pass under a minimal settings module with a test that fails
if any non-test module imports `freedom_ls`. Independently testable: `pytest` in-tree with the new
settings; FLS full suite unchanged. Size M-L, dominated by P1 and X4.

**Spec 2: "Panel framework templates, JS and styling contract" (can follow or run in parallel after D3/D4).**
Covers T1-T11, T14, J1-J5, S1-S5, X3, X8, component and invariant and playwright tiers. User-visible
outcome: a bare Django project with only htmx, Alpine and the documented tokens renders the component
reference page and the full list/instance/modal/quick-view/bulk flow in a browser; FLS's educator
interface is pixel-equivalent (the existing playwright flows are the check). Independently testable:
the package's playwright suite against the package's own shell. Size L.

**Spec 3 (mechanical, small): the move.** Create the repo, move the directory, rename the 22 files'
imports, `INSTALLED_APPS`, `urls.py`, docs, skills, regenerate the import contracts. Outcome: FLS imports
the installed package, full FLS suite green. This is the old research's step 2-3; it assumes specs 1 and 2.

Why not one spec: spec 1 has no template or browser surface (it is verified by unit tests and the FLS
suite), spec 2 is verified entirely in a browser and by cotton rendering. They touch disjoint files
(except `tests/conftest.py`), so reviewers can check "no behaviour change" separately for tenant isolation
(security-sensitive, P1) and for markup/CSS (visual). Mixing them hides a tenancy regression behind
a large template diff. Why not three-plus: splitting P1 off alone would leave the test harness half-moved.

Checkpoint inherited from the old research stands, with a sharper trigger: if D2 cannot be solved without
a shared "core" package (for example because the site resolver needs `site_aware_models` internals), stop.

## References

All findings are from the local tree; no web sources were used. Key files:
`freedom_ls/panel_framework/{apps,models,config,tables,views,tasks,bulk_runs,bulk_actions,checks}.py`,
`freedom_ls/panel_framework/templates/**`, `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`,
`freedom_ls/panel_framework/tests/**`, `freedom_ls/site_aware_models/models.py`,
`freedom_ls/base/{app_settings,csv_safety,csv_import}.py`, `freedom_ls/base/templates/{_base,_base_interface}.html`,
`freedom_ls/base/templates/cotton/*`, `freedom_ls/icons/**`, `freedom_ls/comms/static/comms/js/alpine-components.js`,
`freedom_ls/deployment/housekeeping.py`, `freedom_ls/conftest.py`, `tailwind.input.css`, `tailwind.components.css`,
`pyproject.toml`.

status: ok
