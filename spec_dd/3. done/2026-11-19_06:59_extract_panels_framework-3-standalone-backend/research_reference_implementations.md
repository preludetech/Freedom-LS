# Research: reference implementations

Question: how do well-known reusable Django packages solve the problems spec 3 faces? Findings come from fetched sources. Items marked "(memory)" are from background knowledge and were not re-verified.

## 1. Settings-declared callable resolving the site/tenant from a request

- **Django `get_current_site(request)`** is a plain function: if `django.contrib.sites` is installed it returns `Site.objects.get_current(request)`, otherwise a `RequestSite(request)`. It does not cache on the request itself (`Site.objects.get_current` caches in a module-level `SITE_CACHE`, keyed by `SITE_ID` or host). It is therefore a valid default for `PANEL_FRAMEWORK_SITE_RESOLVER`. Caution: without `django.contrib.sites` it returns a `RequestSite`, not a `Site`, so the framework's required `site` FK needs `contrib.sites` installed (a check on this is cheap). https://raw.githubusercontent.com/django/django/main/django/contrib/sites/shortcuts.py
- **Wagtail `Site.find_for_request(request)`** caches on the request under `request._wagtail_site`, using the `hasattr` guard: look up once, then return the stored value. `None` request returns `None` without caching. This is the closest precedent for "result cached on the request". Use a private, package-prefixed attribute (for example `request._panel_framework_site`). https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/models/sites.py
- **django-tenants** resolves in a middleware (`process_request`): hostname from `request.get_host()`, a domain-model lookup with `select_related('tenant')`, then sets `request.tenant`. A `no_tenant_found` hook handles misses. Downstream code reads `request.tenant`; it never re-resolves. Lesson: resolution in one place, with an explicit miss behaviour. https://raw.githubusercontent.com/django-tenants/django-tenants/master/django_tenants/middleware/main.py
- **allauth** uses settings-declared classes (`ACCOUNT_ADAPTER` etc., a dotted path to a class deriving from a default adapter), loaded through a `get_adapter` helper (loader detail not verified). The pattern is "dotted path in settings, default shipped by the package". https://docs.allauth.org/en/latest/account/adapter.html
- **Takeaway:** a dotted-path callable setting with a Django-provided default, imported with `django.utils.module_loading.import_string`, plus a request-attribute cache, matches all of these. No reference package sets a thread-local for this.

## 2. Site FK with request-scoped querysets

- Wagtail's `SiteManager` only changes ordering and natural keys; site scoping is done by explicit lookups (`find_for_request`), not an ambient manager. (same wagtail source)
- Django's own `CurrentSiteManager` filters on the settings `SITE_ID`, not on a request, so it does not fit a multi-site-per-request host. (memory)
- The common `for_request(request)` / `for_site(site)` queryset-method pattern (explicit, chainable, via `QuerySet.as_manager()` or `Manager.from_queryset`) is the idiom used in many third-party apps (memory). It matches the user's decision: framework-owned manager with `for_request()`, worker passes `site_id`, site passed on create.
- Design implications for the spec: the default manager should not hide rows implicitly if `_base_manager` use must stay unambiguous; expose `for_site(site_id)` as the primitive and `for_request(request)` as `for_site(resolve_site(request).pk)`. Give the worker `for_site(site_id)` so one path covers every read.

## 3. Per-app settings objects with defaults

- **DRF `api_settings`**: `DEFAULTS` dict, `IMPORT_STRINGS` set of names whose values are dotted paths resolved by `perform_import` (error names the setting), lazy `__getattr__` that caches each resolved value with `setattr` and records it in `_cached_attrs`, and a `setting_changed` receiver that calls `reload()` for the `REST_FRAMEWORK` setting. Its docstring warns that `override_settings` may not behave as expected. https://raw.githubusercontent.com/encode/django-rest-framework/master/rest_framework/settings.py
- **allauth `app_settings`**: an `AppSettings(prefix)` class with typed properties that call `_setting(name, default)`, instantiated once (`_app_settings = AppSettings("ALLAUTH_")`) and exposed through a module-level `__getattr__` (PEP 562). Setting names are flat Django settings with a package prefix. https://raw.githubusercontent.com/pennersr/django-allauth/main/allauth/app_settings.py
- **django-appconf** (memory): class-based `AppConf` with `Meta.prefix`, defaults declared as class attributes, merged into `django.conf.settings`.
- **Takeaways for spec 3:**
  - The flat `PANEL_FRAMEWORK_SITE_RESOLVER` name fits the allauth/appconf prefix convention.
  - If the resolved callable is cached (DRF style), tests that use `override_settings` need a `setting_changed` reset, or the resolver should be imported on each call (cheap, `import_string` is cached by `sys.modules`). Importing per call avoids DRF's documented `override_settings` pitfall.

## 4. System checks for required infrastructure

- Django check API: `Warning`/`Error`/`Critical`; `Error` and above block management commands, `Warning` only prints and can be silenced with `SILENCED_SYSTEM_CHECKS`. IDs follow `applabel.X001` with `C/E/W/I/D`. Messages stay under 80 characters, with a one-line hint. https://docs.djangoproject.com/en/stable/ref/checks/
- `@register(Tags.x, deploy=True)` runs only under `check --deploy`; Django's own `mail.E001` and security checks use it. (Docs page mentions the deploy-only behaviour; the `register` signature is from memory.) For the user's decision ("warn only when `DEBUG` is False"), the alternative to an in-check `settings.DEBUG` test is `deploy=True`. The two differ: `deploy=True` never fires on `runserver` or `migrate`, whereas a DEBUG test fires on every check run in production. The user's answer asks for the DEBUG form, so keep that, and note `deploy=True` as the closer-to-Django option for the spec to weigh.
- Check ids: spec 5 owns id prefixes; use the existing `freedom_ls_panel_framework.` prefix style in `checks.py` for now.

## 5. Standalone test setups in package repos

| Package | Approach | Source |
|---|---|---|
| django-filter | `tests/settings.py`: SQLite `:memory:`, minimal `INSTALLED_APPS` (contenttypes, auth, staticfiles, package, `tests`), `MIDDLEWARE = []`, `ROOT_URLCONF = "tests.urls"`, `TEMPLATES` with `APP_DIRS` | https://raw.githubusercontent.com/carltongibson/django-filter/main/tests/settings.py |
| django-tables2 | `tests/app/settings.py`: SQLite `:memory:`, auth and contenttypes, `tests.app` as test app, `tests.app.urls`, request context processor; default `auth.User` (no custom user seen in settings excerpt) | https://raw.githubusercontent.com/jieter/django-tables2/master/tests/app/settings.py |
| DRF | `tests/conftest.py` `pytest_configure` calls `settings.configure()` (no settings file): `SITE_ID=1`, `sites` installed, MD5 hasher, `DEBUG_PROPAGATE_EXCEPTIONS`, SQLite in-memory unless `DATABASE_URL`; PostgreSQL-only tests gated by a `requires_postgres` marker and skipped on SQLite | https://raw.githubusercontent.com/encode/django-rest-framework/master/tests/conftest.py |
| Wagtail | `wagtail/test/settings.py`: DB engine from `DATABASE_ENGINE`, default SQLite `:memory:`; custom user models `customuser.CustomUser` (default) or `emailuser.EmailUser` (no username field, switched by env var `USE_EMAIL_USER_MODEL`); MD5 hasher; DatabaseCache; no `TASKS` | https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/test/settings.py |

- Common shape: settings live in the tests tree, the test-only app lives beside them (`tests` is itself an installed app, carrying the stand-in models), SQLite in memory is the default, and PostgreSQL is opt-in through an environment variable, with PostgreSQL-only tests marked and skipped (DRF's `requires_postgres`).
- Custom user in tests: Wagtail is the only one here that ships a test user model, and it has an email-only variant. That is the precedent for the spec's "small custom user model with email login" as a test-app model inside `tests/`.
- Wagtail and DRF install `django.contrib.sites` in tests (DRF with `SITE_ID=1`); the panel framework should do the same so the default `get_current_site` resolver works.
- Runner: all four are run by a command pointed at the test settings (pytest `--ds`/ini or `runtests.py`/`tox`), separate from any host project, matching the user's "separate command" answer. (pytest-django config detail from memory.)

## 6. CSV formula injection and streaming

- **django-import-export**: opt-in setting `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` (default `False`), which strips a leading `=`. Narrower than OWASP's trigger list (`= + - @ \t \r`). Documented under Installation and configuration. https://django-import-export.readthedocs.io/en/latest/installation.html (confirmed via search summary; the source file fetch 404ed, so implementation detail is not verified). Lesson: the widened trigger set in FLS's `escape_csv_formula` is stricter than this reference, and the reference's default-off posture is a weakness the framework should not copy; keep escaping always on.
- **django-tables2** export: `TableExport` goes through tablib; `as_values()` output is written without any escaping, and the whole dataset is built and written at once with `response.write(self.export())`. No streaming and no formula protection. https://raw.githubusercontent.com/jieter/django-tables2/master/django_tables2/export/export.py
- **Django docs, Echo pattern**: `Echo` implements only `write()` and returns the value; `csv.writer(Echo())`'s `writerow` then returns the encoded line; a generator (batched with `itertools.batched`, Python 3.12+) is passed to `StreamingHttpResponse`. https://docs.djangoproject.com/en/stable/howto/outputting-csv/
- **Takeaway:** neither reference package solves both problems, so the framework's own pair (`escape_csv_formula` plus `EchoWriter`, plus the BOM) is ahead of them and is not copied from them; the copy from FLS is correct. The tests for the copied helper should cover the widened triggers, because no reference test suite does.

## Recommendations for the spec

1. Setting `PANEL_FRAMEWORK_SITE_RESOLVER`: dotted path, `import_string`, default `django.contrib.sites.shortcuts.get_current_site`; cache on a private request attribute with the `hasattr` guard (Wagtail). Resolve per call rather than caching the imported callable, to stay compatible with `override_settings` (DRF pitfall).
2. Add a check or startup assertion that `django.contrib.sites` is installed, because the default returns `RequestSite` otherwise.
3. Manager: queryset methods `for_site(site_id)` and `for_request(request)`; the worker and `bulk_runs.py` use `for_site`.
4. TASKS check: `Warning` with `id`, hint, under the DEBUG-False condition the user chose (note `deploy=True` as an alternative).
5. Test layout: `tests/` holds settings (SQLite `:memory:`, `sites` installed with `SITE_ID`, MD5 hasher, `MIDDLEWARE = []` plus what views need), a test email-user model in a test app, and a `requires_postgres` style marker for any PostgreSQL-only test.

status: ok
