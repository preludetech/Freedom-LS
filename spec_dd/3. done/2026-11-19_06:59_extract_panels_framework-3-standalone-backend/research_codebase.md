# Research: what the codebase gives and constrains for spec 3 (standalone backend)

Worktree `extract_panels_framework-3-standalone-backend`, branch tip `0d55135e9`. Everything below was
read or grepped from the tree; nothing was run (no test, no check), so "no PostgreSQL-only behaviour" is
a static finding, not a verified one.

## 0. Findings that change the idea (read first)

1. **A fourth non-test coupling the idea and the audit both miss.** `freedom_ls/panel_framework/field_display.py:74`
   does `from freedom_ls.base.date_display import DATE_DISPLAY_FORMAT, DATETIME_DISPLAY_FORMAT`
   (used at lines 237, 240, 262, 264 in `formats.date_format(...)`). `base/date_display.py` is pure Django
   (`django.utils.formats/timezone/translation`), 45 lines; the two constants are `"j M Y"` and
   `"j M Y, H:i"`. The idea's "What" lists models/config/tables/views only. The import guard will fail
   without handling this. Resolution options: copy the two format strings into `field_display.py` (or a
   new framework module), or make them a framework setting. Same "no shared core, copies are fine"
   ruling applies. Spec 2 (`LazyBodyPanel` `as_of` "the framework's existing date formatting") builds on
   the same formats, so the spec should name where the copy lives.
2. **Spec 1 has landed**, so the framework now holds `housekeeping.py`, `forms.py` and `lazy_panels.py`.
   The framework unit tests are **19 files, not 16** (see section 6). `housekeeping.py` has a second
   FLS-fixture dependency set (`SiteFactory`, `site_context`) not in the idea's helper list.
3. **The unit tier renders FLS templates.** `test_tables.py`, `test_views.py`, `test_bulk_actions.py`,
   `test_actions.py`, `test_panels.py`, `test_quick_view.py`, `test_reference.py`, `test_lazy_panels.py`,
   `test_field_display.py` call `fetch()`/`render_to_string`/`Client` (467 content/render hits in
   `test_*.py`). `tests/view_helpers.py:13` uses template `panel_framework/test_interface.html`, which
   `{% extends "_base_interface.html" %}` (FLS `base/templates`) and the framework's partials, which use
   FLS cotton components: `c-button`, `c-icon`, `c-chip`, `c-pagination`, `c-dropdown-menu`,
   `c-callout`, `c-back-link`, `c-page`, `c-button-group` (72 `c-` hits in 20 files under
   `templates/panel_framework`; `table_selection_bar.html` 17, `table_toolbar.html` 12,
   `reference/_examples.html` 12). The idea says the unit tests stub "only what they touch" (`site_name`
   processor, `c-icon`, page shell). In fact the data-table and toolbar paths touch `c-button`,
   `c-chip`, `c-pagination`, `c-dropdown-menu` and `c-button-group` as well. Either the stand-in set
   is larger than the idea says, or the standalone tier has to be scoped to tests that avoid those
   templates. This is the single biggest sizing risk. `test_tables.py:2208,2225` also override
   `FREEDOM_LS_ICON_SET` (an FLS setting read by the FLS icon app) and pin heroicons SVG output, so those
   tests depend on FLS's icon backend.
4. **FLS code outside the framework creates `BulkActionRun` without a `site`**, relying on the
   thread-local save hook: `educator_interface/tests/test_views.py:5485`, `test_actions.py:7367,8338`,
   `test_notification_urls.py:18,35`, `invariants/test_config_authorisation.py:203`,
   `invariants/test_organisation_isolation.py:171`. Each calls `BulkActionRun.objects.create(scope=..,
   requested_by=.., table_key=.., action_name=..)` with no `site=` and passes only because
   `SiteAwareModelBase.save()` fills `site` from `_thread_locals.request`. Once the model stops
   subclassing `SiteAwareModel`, these seven call sites fail (IntegrityError, `site` NOT NULL) unless
   the framework's `save()` still has a way to fill `site`, or they pass `site=`. "FLS's own suite
   stays green unchanged" in the idea cannot hold for them as written. Also `.objects.get()` reads in
   `test_actions.py:6826,7510` and `test_notification_urls.py:43` rely on ambient filtering only
   loosely (single site), so they likely survive.
5. **`get_cached_site` can return a non-`Site`.** `site_aware_models/models.py:37-83` returns
   `Site | RequestSite`, and `UnknownSite` (a `RequestSite` subclass, not a row) on `DisallowedHost`. The
   framework's contract "callable returns a `Site`" does not fit FLS's resolver directly, and today's
   `SiteAwareManager` falls through **unfiltered** for `UnknownSite` (`models.py:127-129`). The spec
   must say what the framework does for a non-`Site` result (raise, 404, or empty queryset). Reaching
   a view with a DisallowedHost is not possible in practice (CommonMiddleware rejects it first) but the
   code path exists.

## 1. Imports from `freedom_ls` outside `freedom_ls/panel_framework/`

Python, whole `freedom_ls/panel_framework/` tree (self-imports under `freedom_ls.panel_framework.*` are
omitted; they are the rename in spec 5, not this spec's).

Non-test files:

| File:line | Import | What it needs |
| --- | --- | --- |
| `models.py:13` | `freedom_ls.site_aware_models.models.SiteAwareModel` | UUID pk, `site` FK, `SiteAwareManager`, save/full_clean hook |
| `config.py:17` | `freedom_ls.base.app_settings.AppSettings, Setting` | settings helper |
| `tables.py:12` | `freedom_ls.base.csv_safety.escape_csv_formula` | used at `tables.py:256` |
| `views.py:33` | `freedom_ls.base.csv_import.EchoWriter` | used `views.py:1369` |
| `views.py:34` | `freedom_ls.base.csv_safety.UTF8_BOM` | used `views.py:1371` |
| `field_display.py:74` | `freedom_ls.base.date_display.DATE_DISPLAY_FORMAT, DATETIME_DISPLAY_FORMAT` | **missed by the idea** |

Test files:

| File:line | Import |
| --- | --- |
| `tests/test_bulk_runs.py:25` | `freedom_ls.tests.site_context.drop_ambient_request` |
| `tests/test_tables.py:38` | `freedom_ls.tests.site_context.drop_ambient_request` |
| `tests/test_models.py:13` | `freedom_ls.tests.factories.SiteFactory` |
| `tests/test_housekeeping.py:26-27` | `freedom_ls.tests.factories.SiteFactory`, `freedom_ls.tests.site_context.site_context` (**not in the idea's list**) |
| `tests/playwright/test_create_modal_flow.py:16`, `test_instance_dialogs_flow.py:14`, `test_data_table_flow.py:19`, `test_quick_view_flow.py:15`, `test_component_reference_flow.py:22` | `freedom_ls.tests.playwright_helpers` (spec 4's tier) |
| `tests/invariants/test_templates.py:18` | `freedom_ls.base.theming.FREEDOM_LS_PACKAGE_DIR` (lines 29, 31, 33, 36, 548, 592, 614 use it for paths into `base/templates`, `educator_interface`, `tailwind.components.css`) |

Not imports but FLS strings: `tests/test_tables.py:2208,2225` (`FREEDOM_LS_ICON_SET` setting);
`tests/invariants/test_public_names.py:11-12,36-38` (`FRAMEWORK = "freedom_ls.panel_framework"`, and it
walks `FREEDOM_LS.rglob("*.py")` outside the framework to police host imports; it is a host-side
invariant and only meaningful in the FLS tree); `tests/conftest.py:42,65`, `tests/stub_models.py:32,49,
61,73` (`"freedom_ls_panel_framework"` label, kept by this spec); `tests/conftest.py:129` (ROOT_URLCONF
`"freedom_ls.panel_framework.tests.root_urls"`). `stub_panels.py`, `view_helpers.py`, `urls.py` import
only `freedom_ls.panel_framework.*`. No non-test `.html/.js/.css/.md/.toml` file under the framework
contains `freedom_ls` (grep count 0).

Relevance to the import guard: the guard must allow `freedom_ls.panel_framework...` (and the
`freedom_ls` package prefix from the framework's own absolute self-imports until spec 5), and flag every
other `freedom_ls.*` module import. It must scan tests too, so `tests/invariants/test_templates.py` and
the `playwright/` files fail it; the idea ("tests included") means either those files are fixed here (the
`FREEDOM_LS_PACKAGE_DIR` and `playwright_helpers` uses are spec 4's) or the guard exempts the
component/invariant/Playwright tiers explicitly. The idea's "What" is silent on that conflict.

## 2. `BulkActionRun`: reads, writes and what `SiteAwareModel` provides

Model: `models.py:32` `class BulkActionRun(SiteAwareModel)`. Migration `0001_initial.py:39` has `site =
ForeignKey(on_delete=PROTECT, to='sites.site')` and a UUID pk. `SiteAwareModel` (`site_aware_models/
models.py:166`) = `SiteAwareModelBase` + `id = UUIDField(primary_key=True, default=uuid.uuid4,
editable=False)`; `SiteAwareModelBase` (line 132) = `site = ForeignKey(Site, on_delete=PROTECT)` +
`objects = SiteAwareManager()` + `save()`/`full_clean()` calling `_set_site_from_request()`.

To replicate for byte-identical migration: `id` UUIDField(primary_key, default=uuid.uuid4, editable=False)
and `site` FK to `sites.Site` PROTECT, in the same field order as `0001_initial.py` (declared order is
id, site, then the model's own fields; check `makemigrations --check` stays empty). `BulkActionRun`'s own
`save()` (`models.py:88-93`) only normalises `scope_id`; it calls `super().save`, so it keeps working.

Provided by `SiteAwareManager`/thread-local that must be replaced:
- Read filter: `SiteAwareManager.get_queryset()` (`models.py:119-129`) reads `_thread_locals.request`
  (set by `site_aware_models/middleware.py:10-36` `CurrentSiteMiddleware`, in `MIDDLEWARE` at
  `config/settings_base.py:182`), resolves `get_cached_site(request)` and filters `site=site` only when
  the result `isinstance(site, Site)`; with no ambient request it returns the unfiltered queryset.
- Write fill: `_set_site_from_request()` (lines 148-158) on `save()` and `full_clean()` when
  `site_id` is falsy.
- Request cache: `get_cached_site` caches on `request._cached_site`, honours `config.FORCE_SITE_NAME`
  (dev sets `"DemoDev"`, `settings_dev.py:158`; tests force it to None via autouse
  `_disable_force_site_name`, `conftest.py:45`), and falls back to `get_current_site(request)`. It
  raises `SiteResolutionError` with no request and no pin.
- `site_of`, `site_display_name`, `TimestampedModel`: not used by the framework; `BulkActionRun` has its own
  `created_at`.

Every read and write path in the framework (exhaustive grep of `BulkActionRun`, `_base_manager`, `site_id`):

| Where | How | Isolation today |
| --- | --- | --- |
| `views.py:1147` `_handle_run_status` | `BulkActionRun.objects.filter(requested_by=request.user, table_key=..., **scope_lookup(...))` then `get_object_or_404(runs, pk=...)` | ambient thread-local site filter |
| `bulk_actions.py:383` `RecordedBulkAction.execute` | `BulkActionRun.objects.create(requested_by=ctx.request.user, scope=ctx.scope, action_path, table_key, action_name, target, keys, status)` (no `site`) | site filled by save hook |
| `bulk_actions.py:396,398` | `_run_bulk_action_task.enqueue(str(run.pk), run.site_id)` / `run_bulk_action(str(run.pk), run.site_id)` | passes the row's own site id |
| `bulk_runs.py:72-80` `_run_on_site(run_id, site_id)` | `BulkActionRun._base_manager.filter(site_id=site_id, pk=run_id).select_related("requested_by","scope_type").prefetch_related("scope")`; feeds `claim_run`, `record_run`, `report_finished` | explicit `site_id`; the plain base manager bypasses ambient filtering |
| `tasks.py:19-23` | `@task() _run_bulk_action_task(run_id: str, site_id: int)`; `_report(run)` calls `report_finished(str(run.pk), run.site_id)` | explicit `site_id` |
| `housekeeping.py:92,116,134` | `model._base_manager.filter(...)` across every site, `values_list("pk","site_id")` | deliberately cross-site; generic over `model` (FLS also passes `LearnerImport`, `deployment/housekeeping.py:236`) |
| `run_records.py:29` | a `RunRecord` protocol with `site_id: int` | any model with a `site_id` |
| `bulk_runs.py:153` `run_summary`, `views.py` | read the instance only | n/a |

`_base_manager` here is Django's plain `Manager` (the model's `base_manager_name` is unset), so it is
unaffected by replacing `objects`; `housekeeping.py` depends on that for the generic `model._base_manager`
call. A framework-owned `objects` manager does not change those four sites. Only `views.py:1147` and
`bulk_actions.py:383` need to change, plus `tests/*` listed below. FLS code outside the framework that
touches the model: `deployment/housekeeping.py:39,236`, `educator_interface/actions.py:183,2837,2846`
(hooks only), `educator_interface/notification_urls.py:12-15`,
`qa_helpers/management/commands/qa_create_bulk_operations_scenario.py:56,182,445` (uses
`_base_manager`), `educator_interface/tests/migrations/test_0001_rename_unregister_bulk_runs.py:30,49`
(historical model, unaffected), and the seven `.objects.create(...)` call sites in finding 4.

Framework tests that read/write the model: `test_models.py` (lines 22-86, includes
`test_a_run_takes_its_site_from_the_ambient_site` and `test_the_default_manager_hides_another_sites_runs`,
which assert exactly the behaviour being replaced and must be rewritten), `test_bulk_runs.py:48,74,119`,
`test_run_records.py:23,29`, `test_bulk_actions.py:1239,1292,1317,1325`, `test_housekeeping.py:51-61,
256,266,276,284,295,313`.

## 3. FLS's site resolver and where `PANEL_FRAMEWORK_SITE_RESOLVER` goes

- Resolver today: `freedom_ls.site_aware_models.models.get_cached_site(request: HttpRequest | None) ->
  Site | RequestSite`. It is already request-in, cached on the request. Other users:
  `referral_tracking/middleware.py:32,120,141`; `site_display_name_for_request`; context processors.
- Signature fit: takes a request and returns a site, so `"freedom_ls.site_aware_models.models.
  get_cached_site"` is a valid dotted path for the new setting. Caveats: the `UnknownSite`/`RequestSite`
  return (finding 5) and `FORCE_SITE_NAME` handling (dev pins `DemoDev`, so in dev the framework's
  default `get_current_site` would resolve by host instead, while `get_cached_site` honours the pin; FLS
  must set the resolver to `get_cached_site`, not leave the default).
- Where to set it: `config/settings_base.py` (shared by dev, prod, tests via `settings_dev`); there is
  no `PANEL_FRAMEWORK_*` setting anywhere today (only `BULK_BACKGROUND_THRESHOLD` is read through
  `AppSettings`, and tests set `settings.BULK_BACKGROUND_THRESHOLD = 1` at `test_bulk_actions.py:1288,
  1311`). `config/settings_base.py` has no `SITE_ID` (grep of `config/`: none), so Django's default
  `get_current_site` resolves by request host via `Site.objects.get_current(request)`, with the site cache.
- The cache attribute: FLS uses `request._cached_site`. The new framework cache should use its own
  attribute name so FLS's resolver and the framework do not alias each other's cached value (the
  answers file says "result cached on the request").
- Test ambient mocks: `freedom_ls/tests/site_context.py` `site_context(site)` sets
  `_thread_locals.request = Mock(_cached_site=site)`, clears `SITE_CACHE`, seeds `SITE_CACHE["testserver"]`,
  and patches `freedom_ls.site_aware_models.models.get_current_site`,
  `django.contrib.sites.shortcuts.get_current_site` and `SiteManager.get_current`. A framework that does
  `from django.contrib.sites.shortcuts import get_current_site` at import time holds an unpatched
  reference; resolving the setting with `import_string` at call time (not at import) keeps the mock
  effective for FLS runs. `drop_ambient_request()` only deletes the thread-local request.
  RequestFactory requests (used by `view_helpers.make_request`, `test_context.py`) carry host
  `testserver`; for the default resolver they need `SITE_ID` set or a Site row with domain `testserver`
  (Django's test runner does not create one; `django.contrib.sites` creates `example.com` via
  `post_migrate` with pk 1).

## 4. `freedom_ls/base` helpers to copy

- `base/app_settings.py` (75 lines, pure Django): `Setting(NamedTuple: default, required)`, `AppSettings`
  with `declared_settings`, `__getattr__` (reads `django.conf.settings`, strips strings, treats None/""
  as unset, `deepcopy` of default, raises `ImproperlyConfigured` when required), `missing_required()`,
  and `required_settings_errors(config, app_label)` (builds `<label>.E001` Errors). The audit says copy
  `required_settings_errors` only if a required setting is added; this spec adds a (non-required)
  resolver setting, so it needs only `Setting`/`AppSettings`. If the resolver setting is declared with
  `Setting(default="django.contrib.sites.shortcuts.get_current_site")`, `AppSettings` returns the
  default when unset. It treats `""` as unset too.
- `base/csv_safety.py`: **the widened `FORMULA_TRIGGERS` is already on main and in this tree.**
  `FORMULA_TRIGGERS = ("=","+","-","@","\t","\r","\n","＝","＋","－","＠")`, a
  `_E164_PHONE_NUMBER` exemption (`\+[0-9]{7,15}` full match), `UTF8_BOM = "﻿"`, and
  `escape_csv_formula` checking `value[:1]` and `value.lstrip()[:1]`. Its tests are
  `freedom_ls/base/tests/test_csv_safety.py` (parametrised over `FORMULA_TRIGGERS`; pins the tuple at
  line 35; E.164 cases at 59-81). The framework's copy needs a copy of those tests (the tuple-pin test is
  the one that makes the two copies stay equal). Other users of the FLS copy:
  `site_aware_models/admin_exports.py:20`, `base/csv_import.py:14`, `base/tests/test_csv_import.py:17`,
  `site_aware_models/tests/test_admin_exports.py:13`. FLS keeps its own.
- `base/csv_import.py:135-141`: `class EchoWriter: def write(self, value: str) -> str: return value`
  (the entire class, 8 lines with docstring). `csv_import.py` also holds `write_error_csv` (line 144)
  and learner-import parsing; copy none of that. `UTF8_BOM` is in `csv_safety.py`, not `csv_import.py`.
- `base/date_display.py`: see finding 1.
- Copies mean three places hold the `UTF8_BOM`/`escape_csv_formula` pair after this spec (FLS
  `csv_safety`, FLS `csv_import` re-import, framework). No existing test links the copies; a drift test
  would have to live in FLS and import both.

## 5. Checks, `TASKS` and settings

- `apps.py:6-7,13-15`: `name = "freedom_ls.panel_framework"`, `label = "freedom_ls_panel_framework"`,
  `ready()` imports `check_panels` and `register(check_panels)` (one registered check).
- `checks.py`: one function `check_panels` plus helper functions; ids `freedom_ls_panel_framework.E001`
  to `E008` (lines 92, 77, 103, 142, 152, 186, 234, 262). E-numbers 009 onward are free; there are no
  warning (`W`) ids. `check_panels` does `import_module(settings.ROOT_URLCONF)` (line 38), so under the
  standalone settings `ROOT_URLCONF` must be importable at `manage.py check` time. A new `TASKS` check
  would be a second registered function in `apps.py` (or a function inside `check_panels`); the answers
  file requires a Warning-level, `DEBUG`-False-only check on immediate/dummy backends.
  `test_checks.py` uses `call_command("check")`-style tests and `gc`; it runs under the stub apps.
- FLS `TASKS`: `config/settings_base.py:619-626` sets
  `"django.tasks.backends.immediate.ImmediateBackend"` (dev and tests); `config/settings_prod.py:87`
  `TASKS = fls_defaults.DATABASE_TASKS` (django_tasks_db DatabaseBackend; `pyproject.toml:35`
  `django-tasks-db==0.12.0`). `settings.DEBUG`: dev `True` (but pytest forces False, `settings_dev.py:
  65-68`), prod `False`. Consequence for the FLS suite: a `DEBUG`-False-only warning fires under
  pytest because Django's test runner sets `DEBUG=False`, but `check` is not run by pytest-django
  per test; `test_checks.py` runs `call_command` in some tests, which would see the new warning under
  `ImmediateBackend` unless the check's output is filtered by id or the tests use `--fail-level`.
  Spec must check `test_checks.py` for assertions on the whole check output.
- `BULK_BACKGROUND_THRESHOLD` default 250 (`config.py:31`); read at `bulk_actions.py:364`; the check's
  condition ("could be crossed") is effectively always true for a host.
- `database_task_backend` (`freedom_ls/conftest.py:399-406`) sets `settings.TASKS = {"default":
  {"BACKEND": "django_tasks_db.DatabaseBackend"}}`. **No framework test uses it** (grep over
  `panel_framework/tests` finds no match); the framework tests call `_run_bulk_action_task.func(...)`
  directly (`test_bulk_runs.py:107,129,184,199`) or use immediate-backend inline execution. So the
  standalone suite does not need that fixture or `django_tasks_db`; the idea's list ("`database_task_backend`
  ... copied") is not required. `test_bulk_actions.py:1288,1311` set a threshold of 1 and enqueue under the
  immediate backend, so the standalone `TASKS` must be `ImmediateBackend`.

## 6. The framework's unit test files and the FLS fixtures each uses

Files in scope (18 top-level `tests/test_*.py` plus `tests/templatetags/test_panel_tags.py` = 19; the
idea and the audit say 16, which predates `test_forms.py`, `test_housekeeping.py`, `test_lazy_panels.py`
arriving through spec 1): `test_actions, test_bulk_actions, test_bulk_runs, test_checks, test_context,
test_events, test_field_display, test_filters, test_forms, test_housekeeping, test_lazy_panels,
test_models, test_panels, test_quick_view, test_reference, test_run_records, test_tables, test_views`
and `templatetags/test_panel_tags.py`.

Fixture uses (occurrence counts from grep):

| Fixture or helper | Source | Where used |
| --- | --- | --- |
| `mock_site_context` | `freedom_ls/conftest.py:251` (wraps `site_context(site)`, depends on `site`) | test_bulk_runs 30, test_housekeeping 22, test_tables 87, test_views 62, test_bulk_actions 83, test_actions 76, test_panels 35, test_quick_view 12, test_models 7, test_reference 4, test_lazy_panels 5, test_panel_tags 5, test_run_records 1, helpers.py (docstring) |
| `site` | `conftest.py:218` (SiteFactory, name "TestSite", domain "testsite", parametrisable) | indirect via `mock_site_context`; direct param use 1 hit in test_tables, test_housekeeping, test_bulk_actions each |
| `SiteFactory` | `freedom_ls/tests/factories.py:8` (`django_get_or_create = ("domain","name")`) | test_models (`SiteFactory()` at line 43), test_housekeeping:326 |
| `site_context` | `freedom_ls/tests/site_context.py:15` | test_housekeeping:327 |
| `drop_ambient_request` | `freedom_ls/tests/site_context.py:57` | test_bulk_runs:61, test_tables |
| `make_staff_user` | framework's own `tests/helpers.py:20` (calls `get_user_model().objects.create_user(email=..., password=..., is_staff=True)`; counter-based unique emails) | test_actions 51, test_bulk_actions 19, test_views 5, test_reference 4, test_bulk_runs 2, test_run_records 2, view_helpers 2 |
| `logged_in_client` | `conftest.py:258` | **not used by any framework test** (zero matches under `panel_framework/tests`). The idea lists it; `test_reference.py` builds `Client()` and calls `client.force_login(...)` itself (lines 137, 144, 153, 230) |
| `database_task_backend` | `conftest.py:399` | **not used** |
| `UserFactory` | `freedom_ls/accounts/factories.py` | not used (`make_staff_user` replaces it) |
| autouse FLS fixtures that affect results | `_disable_force_site_name` (FORCE_SITE_NAME=None), `_clear_django_cache`, `_isolate_media_root`, `_clear_course_access_backend_cache`, `_clear_rule_kind_cache`, `_clear_messaging_policy_cache`, `_clear_deadline_policy_cache` (`freedom_ls/conftest.py:45-199`) | all autouse, so every framework test currently runs under them; the standalone run has none. Only `FORCE_SITE_NAME` and the cache clear are plausibly relevant (the first does not exist in a standalone settings module; `config.FORCE_SITE_NAME` is FLS-only) |
| Playwright fixtures `logged_in_page`, `logged_in_user`, `playwright`, `reset_local_storage`, `live_server_site` | `freedom_ls/tests/playwright_fixtures.py` via root conftest | Playwright tier only (spec 4) |

Local conftest (`tests/conftest.py`): three autouse fixtures: session-scoped `_panel_test_tables`
(creates `StubModel`, `StubChild`, `StubGrandchild`, `StubProtectedChild` via `connection.schema_editor()`
and registers them in `apps.all_models["freedom_ls_panel_framework"]`; also pre-creates ContentTypes),
`_reset_recording_capability_config`, `_use_panel_test_templates` (prepends `tests/templates` to
`TEMPLATES[0]["DIRS"]`), `_use_panel_test_urls` (ROOT_URLCONF to `tests/root_urls.py`, which mounts
`admin.site.urls` so `admin:login` reverses, plus `tests/urls.py`). The module docstring says "no
cross-app imports", true today. Uses relative imports because of the namespace-package layout (see
section 9).

`make_staff_user`'s user model: FLS's `accounts.User` (`accounts/models.py:110`, `SiteAwareModelBase`
+ `TimestampedModel` + `AbstractBaseUser` + `PermissionsMixin`, `USERNAME_FIELD = "email"`,
`create_user` at line 39). Standalone settings need a tiny `AUTH_USER_MODEL` with `create_user(email=...,
password=..., is_staff=True)` and `USERNAME_FIELD = "email"`; `BulkActionRun.requested_by` is a CASCADE FK to
it (`models.py:48-50`).

## 7. SQLite or PostgreSQL for the standalone tier

Static search of the framework (Python, tests included) for PostgreSQL-only constructs: no
`django.contrib.postgres`, `ArrayField`, `SearchVector`, trigram/unaccent, `__contains`/`__has_key`/
`__overlap` on JSON, `select_for_update`, `skip_locked`, `connection.vendor`, or raw SQL. The only
text lookup is `Q(**{f"{search_field}__icontains": ...})` at `tables.py:405`. JSON use is plain
`JSONField` storage on `BulkActionRun` (`target`, `keys`, `result`). Points worth a verification run
rather than an assumption:
- `icontains` on SQLite is ASCII case-insensitive only; a framework search test with non-ASCII text could
  differ from PostgreSQL. Not seen, not run.
- `test_bulk_actions.py:793` is `@pytest.mark.django_db(transaction=True)` and the session fixture
  `_panel_test_tables` creates stub tables outside migrations, then per-test teardown of a transactional
  test flushes tables. SQLite handles this, but the interplay (flush emptying the stub tables is fine; the
  tables are dropped at session end) should be run once, in-memory SQLite, `pytest -p no:randomly`.
- `claim_run`/`record_run` (`run_records.py`) use `QuerySet.update` with status filters; no row locking
  was seen. A concurrency claim ("a sweep closed it") is tested by monkeypatching, not by two connections.
- FLS's real database is PostgreSQL 17 (`settings_dev.py:127-138`, port 6543, `TEST.TEMPLATE = template0`).
  Spec 5's package CI would be the place for a PostgreSQL leg. The decision "SQLite, chosen on purpose"
  is supportable on this evidence; the decision belongs to the spec, with the above as the checks to run.

## 8. How test tiers and commands are defined (to add a standalone tier)

- `pyproject.toml:82-98` `[tool.pytest.ini_options]`: `DJANGO_SETTINGS_MODULE = "config.settings_dev"`,
  `python_files = ["tests.py","test_*.py","*_tests.py"]`, `env = ["DJANGO_ALLOW_ASYNC_UNSAFE = True"]`,
  `testpaths = ["freedom_ls","tests","claude_plugins/fls-content"]`, `addopts = "--strict-markers -m 'not
  ci_only and not weasyprint and not dev_tooling' --disable-socket --allow-hosts=127.0.0.1,::1
  --tracing=retain-on-failure --screenshot=only-on-failure --dist loadfile"`, `timeout = 300`, markers
  `playwright, ci_only, fls_internal, weasyprint, dev_tooling`. Note `--tracing` and `--screenshot` are
  pytest-playwright options, so a standalone run that does not load pytest-playwright must not inherit
  these `addopts` (they would be unknown arguments). `pytest-env` supplies `env`.
- `[tool.test_tiers]` (`pyproject.toml:108-155`): `none` globs, `escalation` globs (`config/**`,
  `freedom_ls/site_aware_models/**`, `freedom_ls/content_base/**`), `markers` expression,
  `[tool.test_tiers.memory]` (`max_workers = 4`, `per_worker_mb = 768`), and `[[tool.test_tiers.tooling]]`
  path-to-test mappings. There is **no concept of an additional named tier or a second pytest invocation**
  in `[tool.test_tiers]`; "tier" here means none/targeted/full per
  `claude_plugins/django-stack/resources/test_tiers.md`. `.claude/ds/scripts/run_tests.sh` only locates
  and `exec`s `claude_plugins/django-stack/scripts/run_tests.py` ("Do not add project steps here").
  `select_tests.sh` and `select_tests.py` map a changed file to a test set. So the new standalone run is
  not representable as a tier today; it would be a documented separate command (the answers file picks
  this) invoked by hand, by a fls-dev skill/doc, or by CI.
- Escalation note for this spec: the work touches `config/settings_base.py` (escalation glob `config/**`),
  so any targeted run after the resolver setting lands becomes a full run.
- `.claude/sdd/config.md`: "Test tiers" points at `claude_plugins/django-stack/resources/test_tiers.md`;
  "Testing Skills" are `ds:testing`, `fls-dev:testing`, `ds:playwright-tests`, `fls-dev:playwright-tests`;
  "Rule Files" include `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`. Per the repo CLAUDE.md,
  `claude_plugins/django-stack`, `sdd`, `productivity` are generic and may not carry FLS paths; a
  standalone-tier command that names `freedom_ls/panel_framework/tests` therefore lives in
  `claude_plugins/fls-dev` or `pyproject.toml`/`.claude` config, not in `django-stack` resources.
- CI definition: no `.github`, `.gitlab-ci.yml`, `tox.ini`, `setup.cfg` or `.importlinter` was found
  matching `panel_framework` (search of those names returned nothing). Not otherwise checked.
- Import-linter: `[dependency-groups] dev` and `[project.optional-dependencies] dev` both list
  `import-linter>=2.15`; `test_organisation/import_contracts.toml` has 36 `panel_framework` hits
  (per the audit) and `import_baseline.txt:76`, `mirroring_baseline.txt:64` carry a `# panel_framework`
  section, `mirroring_exemptions.txt:14-15` exempt `tests/components/` and `tests/invariants/`. New test
  files in the framework (import guard, settings, check, resolver) need mirroring (a test file per module)
  consideration under `[tool.test_organisation]` (`pyproject.toml:100-106`); the mirroring baseline would
  list any unmirrored file. The import contracts would also change: removing the `site_aware_models` and
  `base` imports shrinks the declared edges for `panel_framework` (they regenerate via `/ds:app_map` per
  the audit); `declared_edges = "test_organisation/declared_edges.toml"`.

## 9. pytest-django settings and conftest discovery for a separate config

- Single root config: `pyproject.toml [tool.pytest.ini_options]` only. No `pytest.ini`, `tox.ini` or
  `setup.cfg` exists in the repo root (glob returned none). No `pytest.ini` or `conftest.py` below
  `freedom_ls/panel_framework/tests/` other than `conftest.py` itself.
- Conftest chain for a test under `freedom_ls/panel_framework/tests/`: repo-root `conftest.py` (does
  `from freedom_ls.conftest import *`, deletes `playwright`, and defines `pytest_xdist_auto_num_workers`
  capping at 4), then `freedom_ls/conftest.py` (imports `freedom_ls.accounts.factories.UserFactory`,
  `freedom_ls.tests.factories.SiteFactory`, `freedom_ls.tests.playwright_fixtures`,
  `freedom_ls.tests.site_context`, `freedom_ls.tests.storages` at **module import time**, lines 16-32),
  then `freedom_ls/panel_framework/tests/conftest.py`. `freedom_ls/` has no `__init__.py` (glob: only
  `freedom_ls/panel_framework/__init__.py` and `tests/__init__.py` exist), which is why
  `tests/conftest.py:18-24` documents that pytest imports the tests as `panel_framework.tests.*`
  (the first directory without `__init__.py` upward becomes the sys.path root, which is `freedom_ls/`).
- Consequence for a standalone invocation: a plain `pytest freedom_ls/panel_framework/tests` from the
  repo root loads both parent conftests (they sit in ancestor directories under the rootdir) and the root
  `pyproject.toml` ini, so the standalone suite would not be standalone. Pytest stops looking for
  `conftest.py` above the `confcutdir`, which defaults to the rootdir (the directory of the ini-file
  found). Placing a `pytest.ini` inside `freedom_ls/panel_framework/tests/` and running
  `pytest -c freedom_ls/panel_framework/tests/pytest.ini` (or `--rootdir` / `--confcutdir=
  freedom_ls/panel_framework/tests`) makes that directory the rootdir so the two parent conftests are not
  collected. Verify with `--co`: the `-c` and `--confcutdir` behaviours are version-sensitive and this was
  not run. Importing `freedom_ls.panel_framework` as a namespace-package member never executes
  `freedom_ls/conftest.py` or any FLS app, so that part is fine for the guard.
- Standalone settings must also declare pytest-django options: `DJANGO_SETTINGS_MODULE` as a dotted
  module importable from `sys.path` (e.g. `freedom_ls.panel_framework.tests.settings`), `python_files`,
  `testpaths`, and its own `addopts` without the playwright flags, `--dist loadfile`, or FLS markers
  (`--strict-markers` would reject markers not declared in the new ini; the framework's playwright files
  use `pytest.mark.playwright`).
- Plugins the standalone suite needs: `pytest-django`, `pytest-mock` (`test_reference.py:21` imports
  `MockerFixture`), and `django-cotton` for the `cotton_helpers.py:10` import of
  `django_cotton.compiler_regex.CottonCompiler`. Whether `time-machine` is needed by `test_housekeeping.py`
  or `test_lazy_panels.py` was not checked. `pytest-randomly` is installed in the FLS env and runs by
  default (random order) in the same environment.
- The framework's invariant/component/playwright tests share the directory tree with the unit tests, so
  the standalone ini must select the unit files by path (for example `--ignore` for `components/`,
  `invariants/`, `playwright/`), because those files import FLS or FLS templates and would error on
  collection.

## 10. `lxml`

`freedom_ls/panel_framework/tests/invariants/test_templates.py:9` imports `lxml` (and `tests/test_tables.py`
around line 2190-2198 walks `element.tag`/`.attrib` in an lxml-shaped way; the import line there was not
read, check it). `lxml` is **not** in `pyproject.toml` `[project].dependencies`,
`[project.optional-dependencies].dev` or `[dependency-groups].dev`. It is in `uv.lock`
(`name = "lxml"`, version 6.1.0, cp313 wheels) as a transitive dependency (probably `premailer`, declared
at `pyproject.toml:20`; the lock's dependents were not read). The framework has no `pyproject.toml` yet
(spec 5), so "the framework's test dependencies declare it" has no home in this spec except (a) an FLS
`dev` entry (touches `pyproject.toml` and `uv.lock`, two places: `[project.optional-dependencies].dev`
and `[dependency-groups].dev`, which are duplicated lists) or (b) a requirements note beside the
standalone-tier ini.

## 11. Conflicts with in-progress specs

- **`extract_panels_framework-2-new-capabilities`** (`spec_dd/2. in progress`): only `idea.md` and an
  unticked `todo.md` exist (nothing implemented yet). Its idea says it adds framework tests, stub
  panels/actions "in the framework's test conftest", reference-page entries and Playwright tests for the
  reason dialog, the `as_of` stamp, expandable rows and compact density. Overlap with this spec:
  `tests/conftest.py` (both edit it; the roadmap notes "whichever lands second rebases"),
  `tests/stub_panels.py`, `tests/templates/panel_framework/*` (`test_row_detail.html` and
  `test_reason_dialog.html` already exist), `reference.py`/`_examples.html`, and `test_templates.py`
  (its `HAND_WRITTEN_TABLE_EXEMPTIONS` change). It states "Cutting FLS imports, theme-token and host-shell
  assumptions: specs 3 and 4" are out of its scope. It builds on `field_display` date formatting for
  `as_of`; if spec 2 adds a new import from `freedom_ls.base...` (for example `display_datetime` or a
  time-zone helper), it would break this spec's import guard when it lands second, and conversely the
  guard fails spec 2's branch on rebase. The spec should say the guard is the shared contract.
- Minimise the conflict: put the standalone settings, `pytest.ini` and the replacement fixtures (`site`,
  resolver fixture, `drop_ambient_request` replacement) in new files, importing them from
  `tests/conftest.py` with the smallest possible edit there.
- Other in-progress specs: `educator-interface-course-list-shows-too-much`,
  `learner-profile-use-panels-framework-1-file-upload-actions`, `apis-for-lead-monitoring-6-conversions`,
  `learner-interface-features-1-question-sections`. The first two may touch educator or learner panel
  code; none was read, so conflicts with them are unverified.
- Roadmap (`spec_dd/1. next/roadmap.md:76-99`): spec 4 is blocked on spec 2 only, spec 5 on 3 and 4.
  Decided: "A settings-declared site resolver defaults to `get_current_site`". Assumed: "no shared core
  package. If one turns out to be needed, stop and say so." Evidence for the stop condition: the FLS
  resolver `get_cached_site` is passed by dotted path in a setting, so the framework needs no import of
  `site_aware_models` internals; this supports "no core package" (the thread-local, `UnknownSite` and
  `FORCE_SITE_NAME` stay on the FLS side of the resolver).

## 12. Things the spec should resolve (not decided here)

1. Where the `date_display` constants go (finding 1).
2. How the import guard treats the component, invariant and Playwright tiers (section 1).
3. The size of the template stand-in set for the unit tier (finding 3), or scoping the tier to tests that
   do not render FLS-only components.
4. Whether `BulkActionRun`'s save still fills `site` when absent (finding 4) or the seven FLS call
   sites and the FLS fixtures pass `site=`. Passing `site` on create is the answers-file decision;
   it forces edits to FLS tests, which conflicts with "FLS's own suite stays green unchanged".
5. What a non-`Site` resolver result does (finding 5).
6. Whether the standalone settings need extra `INSTALLED_APPS` entries for apps the templates load
   (`{% load %}` is only `panel_tags`/`data_table_tags` per the audit, so likely none).
7. The `TASKS` check must not break FLS's `test_checks.py` (section 5).

## References

Local tree only; no web sources. Files read: `freedom_ls/panel_framework/{models,config,apps,checks,
tasks,bulk_runs,bulk_actions,views,housekeeping,field_display}.py`, `freedom_ls/panel_framework/tests/
{conftest,helpers,view_helpers,test_bulk_runs,test_models,test_tables,test_bulk_actions,
invariants/test_public_names,templates/panel_framework/test_interface.html}`, `freedom_ls/site_aware_models/
{models,middleware}.py`, `freedom_ls/base/{app_settings,csv_safety,csv_import,date_display}.py`,
`freedom_ls/base/tests/test_csv_safety.py`, `freedom_ls/conftest.py`, `freedom_ls/tests/site_context.py`,
`freedom_ls/tests/factories.py`, `conftest.py`, `pyproject.toml`, `config/settings_{base,dev}.py`,
`.claude/ds/scripts/run_tests.sh`, `.claude/sdd/config.md`, `.claude/ds/config.md`,
`claude_plugins/django-stack/resources/test_tiers.md`, `spec_dd/1. next/roadmap.md`,
`spec_dd/1. next/extract_panels_framework/research_coupling_audit.md`,
`spec_dd/2. in progress/extract_panels_framework-2-new-capabilities/{idea,todo}.md`.

status: ok
