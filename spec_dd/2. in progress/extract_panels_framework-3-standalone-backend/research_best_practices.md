# Best practices: decoupling a reusable Django app from its host

Written from established Django and ecosystem practice. I did not re-fetch the pages, so check the URLs before quoting them.

## 1. Pluggable site/tenant resolution via a settings dotted path
- Declare one setting, for example `PANELS_SITE_RESOLVER = "django.contrib.sites.shortcuts.get_current_site"`. Read it lazily with `getattr(settings, NAME, DEFAULT)`, not at import time. This keeps `override_settings` working in tests.
- Load it with `django.utils.module_loading.import_string`. Cache the loaded callable with `functools.cache`, and clear the cache on the `setting_changed` signal. Django's own `get_storage_class` and `AUTHENTICATION_BACKENDS` follow the same pattern.
- Signature: `def resolver(request: HttpRequest) -> Site`. Keep it one argument. Document what it returns and what it raises (`Site.DoesNotExist`, `ImproperlyConfigured`).
- Cache the resolved value on the request, for example `request._panels_site`. Check with `hasattr` first, so each request resolves once. `get_current_site` already caches per `SITE_ID` or host in `SITE_CACHE`, but a per-request attribute also protects custom resolvers that hit the database.
- Fail loudly. If the setting is unresolvable, raise `ImproperlyConfigured` with the setting name, and add a system check. Do not fall back silently to "no site", because that leaks data across tenants.
- Default to `get_current_site`. It needs `django.contrib.sites` installed. If it isn't, it returns a `RequestSite`, which has no pk. Document this, and add a check if the app's models foreign-key to `Site`.

## 2. Explicit request-scoped querysets vs thread-local ambient request
- Preferred: explicit scoping. Use `Model.objects.for_site(site)` or a `SiteScopedQuerySet`, and pass `request` or `site` into service functions. It is testable, it is safe under ASGI and async, and a reviewer can see the scoping.
- Thread-local or `contextvars` ambient state is what `django-multitenant` and `django-tenant-schemas` use. It makes auto-filtering ergonomic, but it leaks between requests if cleanup is skipped. It breaks in Celery and `django.tasks` workers, where there is no request. It also hides bugs in tests and shell sessions. If you must use it, use `contextvars` (not `threading.local`), set and reset it in middleware with `try/finally`, and have the manager raise when no tenant is set.
- Hybrid that works for libraries: the default manager does not filter. A scoped manager is opt-in and explicit. Views call `for_site(resolve_site(request))`. Background tasks take `site_id` as an argument and rebuild the scope themselves.
- Also test that two sites cannot see each other's rows, for every view and every task entry point.

## 3. System checks for `django.tasks` (Django 6)
- Register with `@register(Tags.compatibility)` or a custom tag, and return `Warning` or `Error` objects with a stable `id` (for example `panels.W001`) and a `hint`.
- Read `settings.TASKS["default"]["BACKEND"]`, or use `django.tasks.task_backends`. Compare the dotted path against `django.tasks.backends.immediate.ImmediateBackend` and `django.tasks.backends.dummy.DummyBackend`.
  - `ImmediateBackend` runs tasks inline in the request, which is fine for dev and tests but blocks requests in production.
  - `DummyBackend` stores tasks and never runs them, so exports and imports would silently never finish.
- Gate on `settings.DEBUG`: warn only when `not DEBUG`. Tests normally run with `DEBUG=False`, so do not make the check an `Error`, or `manage.py test` and `check --deploy` will fail. Use `Warning`. Consider `deploy=True` (`register(..., deploy=True)`) so it runs only under `check --deploy`.
- Never import the backend class at module import time. Compare strings, so the app still imports when `django.tasks` is absent. Silence per project with `SILENCED_SYSTEM_CHECKS`.
- Unit-test the check with `override_settings(TASKS=..., DEBUG=...)` and by calling the check function directly.

## 4. Testing a reusable app standalone
- Ship a minimal settings module inside the test tree, for example `tests/settings.py`. It should contain `SECRET_KEY`, `INSTALLED_APPS` (only the app and its true dependencies), `DATABASES`, `ROOT_URLCONF`, `USE_TZ`, `DEFAULT_AUTO_FIELD`, templates, middleware, and the `TASKS` backend.
- pytest-django: select it with `--ds=tests.settings` or `DJANGO_SETTINGS_MODULE` in `pyproject [tool.pytest.ini_options]`. Use a dedicated config (`-c path/pytest.ini`) or `--rootdir` for the standalone run.
- Pitfall: when the app lives inside a host repo, pytest finds the parent `pyproject.toml` and `conftest.py` files, which pulls in host fixtures and host settings. Mitigations:
  - Give the app directory its own `pytest.ini` or `pyproject.toml` with `[tool.pytest.ini_options]`. The nearest ini file defines the rootdir.
  - Pass `--confcutdir=<app dir>`, so no `conftest.py` above that dir is loaded. Also pass `-p no:cacheprovider` if the cache dir is a problem.
  - Add `--import-mode=importlib`, or set `pythonpath`, so the app is imported as an installed package and not via cwd. Ideally run against a wheel built from the app.
  - Run the standalone suite in CI as a separate job and a separate venv that does not install the host.
- Custom user model: if the app uses `settings.AUTH_USER_MODEL`, the test settings need a user model. Either use `django.contrib.auth.User`, or define a tiny `tests.testapp.User` and set `AUTH_USER_MODEL = "testapp.User"` (needs migrations, or `MIGRATION_MODULES` disabled). Test with the stock user too if the app claims to support it. Never import the host's user model in the app.
- Databases: SQLite in-memory is fast, but it differs from PostgreSQL. It has no `select_for_update` semantics, a different `JSONField` and `ArrayField` situation, and different case sensitivity and collation. If the app uses PG-only features, run the matrix on both. Make PG the CI gate and SQLite the quick local default. Choose with `DATABASE_URL`.
- Test migrations. Run `makemigrations --check --dry-run` in the standalone settings, so the app ships migrations that don't depend on host apps. Use `swappable_dependency(settings.AUTH_USER_MODEL)`.

## 5. Import-boundary tests
- import-linter: add `[tool.importlinter]` with `root_package = "panels"` and a `forbidden` contract (`source_modules = ["panels"]`, `forbidden_modules = ["freedom_ls"]`), or a `layers` contract. Add `include_external_packages = true` for third-party bans. Run `lint-imports` in CI and pre-commit. Note that it analyses static imports only, so `import_string` and string app labels are not caught.
- AST scan test: a pytest test that walks `ast.parse` over every `.py` file in the package, collects `Import` and `ImportFrom` nodes, and asserts that none starts with the host package. It is dependency-free and easy to extend to a grep for host-specific strings in settings and templates (`"freedom_ls"`). Also scan templates and migrations for host app labels in `dependencies` and `ForeignKey("hostapp.X")` strings, which import-linter misses.
- Complement the static tests with a runtime test. Install the app alone in the minimal settings and `import` every module, via `pkgutil.walk_packages`. This catches hidden host imports.
- Fail on unexpected imports in tests too, or allowlist them explicitly.

## 6. Vendoring small security helpers vs sharing
- A CSV formula-injection escaper is about 10 lines: prefix cells that start with `=`, `+`, `-`, `@`, tab or CR with `'`. OWASP's guidance is to prefix and quote.
- Vendoring is the better choice for a standalone package. It avoids a dependency on the host and avoids a shared micro-package to maintain. Keep it in one module (`panels/_csv.py`), with a docstring that cites the source and the OWASP rule, and with its own tests (including leading whitespace, negative numbers, and non-strings).
- Trade-off: the copies can drift, and a fix must be applied in both. Mitigate with identical test vectors in both repos and a comment pointing to the sibling copy. Extract a shared package only when there are 3 or more consumers, or when the logic is non-trivial (a crypto or parsing library).
- The host should depend on the extracted app's helper, not the reverse. If the host already has a copy, either re-export from the package or leave the host copy alone. Do not make the package import the host.

## References
- https://docs.djangoproject.com/en/stable/ref/utils/#module-django.utils.module_loading
- https://docs.djangoproject.com/en/stable/ref/contrib/sites/#django.contrib.sites.shortcuts.get_current_site
- https://docs.djangoproject.com/en/stable/topics/checks/
- https://docs.djangoproject.com/en/6.0/topics/tasks/
- https://docs.djangoproject.com/en/stable/ref/signals/#setting-changed
- https://docs.pytest.org/en/stable/reference/reference.html#confval-confcutdir
- https://docs.pytest.org/en/stable/explanation/pythonpath.html
- https://pytest-django.readthedocs.io/en/latest/configuring_django.html
- https://docs.djangoproject.com/en/stable/topics/testing/advanced/#testing-reusable-applications
- https://docs.djangoproject.com/en/stable/topics/auth/customizing/#reusable-apps-and-auth-user-model
- https://import-linter.readthedocs.io/en/stable/contract_types.html
- https://owasp.org/www-community/attacks/CSV_Injection
- https://docs.python.org/3/library/contextvars.html

status: ok
