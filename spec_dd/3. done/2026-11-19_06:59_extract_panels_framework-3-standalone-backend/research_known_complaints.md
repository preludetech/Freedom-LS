# Research: known complaints

Question: what do developers commonly complain about with this kind of work (a Django app made standalone: site handling, request state, settings helper, checks, test setup, CSV escaping)?

Method: web searches only. Several results were documentation, Django tickets or blog posts rather than first-hand complaints, and the notes below say so. Nothing here was verified against Django 6 source.

## 1. Reusable apps and `django.contrib.sites` / `SITE_ID`

- Django's docs set the contract. `get_current_site(request)` returns a `Site` if the sites framework is installed and a `RequestSite` if it is not. `SITE_ID` is optional for that helper, which falls back to matching the request host. `Site.objects.get_current()` and `CurrentSiteManager` need `SITE_ID`. https://docs.djangoproject.com/en/4.2/ref/contrib/sites and https://django.readthedocs.io/en/6.0.x/ref/contrib/sites.html
- Complaint pattern: apps that call `Site.objects.get_current()` or use `CurrentSiteManager` force every host to install sites and define `SITE_ID`. A request-taking resolver avoids this.
- Fit with the idea: the framework keeps a required `site` FK to `django.contrib.sites`, so the host must install sites regardless. The default `get_current_site` returning a `RequestSite` would NOT be a saveable FK target. The settings-declared callable must return a real `Site`, and the docs for it should say so. (This is my inference from the docs, not a quoted complaint.)
- Caching: Django's `Site` objects are cached in a module-level `SITE_CACHE`. The cache is cleared on `Site` save and delete, and via `Site.objects.clear_cache()`. Tests that change `SITE_ID` or the host have to clear it. Source: Django sites models source, e.g. https://docs.djangoproject.com/en/5.0/_modules/django/contrib/sites/models/. I did not find a current first-hand complaint thread on this, so treat it as a known hazard rather than a measured pain point.
- Fit: if the resolver result is cached on the request, the test stand-ins must not cache across tests (see `clear_cache()`).

## 2. Thread-local request or tenant state

- django-multitenant's docs warn that its tenant is a thread-local. Failing to unset it at the end of the request can leak data to the next request on the same server thread. https://django-multitenant.readthedocs.io/en/v4.1.0/usage.html
- Forum material says thread-locals do not work under async, and suggests asgiref `Local`. Django core developers have long resisted storing the request in thread-locals. https://forum.djangoproject.com/t/django-and-multi-tenancy-issue/18730 and https://groups.google.com/g/django-developers/c/ORo_28B_VIA/m/__i8ciT7B0IJ
- Middleware instance attributes and module-level state are shared across requests in a worker. https://www.djangotricks.com/blog/2026/06/understanding-memory-usage-in-django-webserver-workers/
- Fit: this supports the audit's recommendation of an explicit request-taking queryset method over an ambient request. Background workers have no request, so the worker must be handed the site id (already settled). Any manager that silently returns unfiltered or empty results when no ambient request is set is the usual failure mode.

## 3. Settings read at import time vs `override_settings`

- Django ticket #21330 flagged the `SETTING = getattr(settings, "SETTING", default)` idiom in a reusable app's defaults module. The value is evaluated once at import, so `@override_settings` has no effect. https://code.djangoproject.com/ticket/21330 and https://code.djangoproject.com/ticket/22071
- Forum and blog write-ups describe the workarounds: read lazily through a wrapper that checks `django.conf.settings` on each access, or reload the module and patch in tests. https://forum.djangoproject.com/t/how-should-django-packages-handle-default-settings/30636 and https://dev.to/pomidoroshev/why-djangos-overridesettings-sometimes-fails-and-how-reload-patch-saved-me-3el9
- Fit: the copied `AppSettings` must resolve on attribute access. Any module-level constant derived from it (for example a threshold used in a default argument or decorator) reintroduces the problem. The new resolver setting and `BULK_BACKGROUND_THRESHOLD` should be read at call time.

## 4. Noisy system checks

- Complaints are mostly about third-party warnings that cannot be fixed by the user. The remedy is `SILENCED_SYSTEM_CHECKS`, which since ticket #25318 silences errors as well as warnings. Per-field silencing was requested in #26472 and did not appear to have shipped. Some commands (such as `migrate`) still run checks. https://code.djangoproject.com/ticket/25318 , https://groups.google.com/g/django-updates/c/XyhkGZcbmrs/m/jrk14k5qAAAJ , https://djangotricks.com/tricks/4rKszP3Ww7nL
- Also: a warning makes `makemigrations --check` exit non-zero (#34436). https://groups.google.com/g/django-updates/c/nalAArT_Gcs/m/1vwsOgvVCwAJ
- Fit: a `TASKS` check that fires in dev or test (immediate or dummy backend) will be exactly this kind of nuisance. Prefer a Warning with a stable id (silenceable), apply it only when the threshold could be crossed, and make sure it does not trip `makemigrations --check` in CI.

## 5. pytest-django config and conftest selection

- Precedence of the settings module is `--ds`, then the `DJANGO_SETTINGS_MODULE` env var, then the ini option. A `--ds` in `addopts` or a stray env var in a shell or CI overrides the ini file. Without `pythonpath`, the settings module may fail to import. pytest-django searches parent directories for `manage.py` unless `django_find_project = false`. https://pytest-django.readthedocs.io/en/stable/configuring_django.html and https://pytest-django.readthedocs.io/en/stable/managing_python_path.html
- A worked example of a reusable app tested with its own settings: https://til.simonwillison.net/django/pytest-django
- Fit: pytest picks the nearest ini file by rootdir rules, and conftest files at ancestor directories load for tests below them. A framework `tests/conftest.py` under `freedom_ls/panel_framework/` will still load the FLS `freedom_ls/conftest.py` above it when run from the FLS tree. "No FLS root conftest" therefore needs `--confcutdir`, `--rootdir` or a separate ini file, and the env var must be unset. I did not find a first-hand complaint thread; this follows from the documented rules.

## 6. SQLite vs PostgreSQL test divergence

- Documented differences: default ordering without `order_by`, boolean ordering (#19726), JSONField `__in` filtering (#31936), case-sensitive and collation-dependent sorting, regex behaviour. Advice: give explicit `order_by`, use `Lower()`, and run those tests on PostgreSQL. https://code.djangoproject.com/ticket/19726 , https://groups.google.com/g/django-updates/c/C4hFGFJE7jQ/m/F_P06KfuBgAJ , https://www.djangotricks.com/tricks/Wh5nnwkZvyZg/ , https://dev.to/valasek/moving-from-postgresql-to-sqlite-in-django-handling-locale-aware-sorting-48e2
- Fit: before picking SQLite for the standalone unit tier, grep the unit tests and framework code for ordering assumptions, JSON lookups, `iexact` or collation use, `select_for_update` and constraint behaviour. A third option is to run the standalone tier on PostgreSQL via an environment variable.

## 7. CSV formula injection

- OWASP's current trigger list: `=`, `+`, `-`, `@`, tab (0x09), carriage return (0x0D), line feed (0x0A) and full-width variants. Fix: prefix a single quote, wrap in double quotes, double embedded quotes. Caveat: Excel may strip the protection when the file is saved and reopened. https://owasp.org/www-community/attacks/CSV_Injection and https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection
- Symfony moved from a tab prefix to a single-quote prefix after OWASP added tab and CR. Symfony 4.4.34 and 5.3.12 and later. https://symfony.com/cve-2021-41270
- Gaps people hit: the tab prefix stays in the data and breaks programmatic imports (OWASP page). I found no source specifically on leading whitespace before a trigger, so that gap rests on the idea's own widened spec.
- Complaints about corrupted legitimate data: Oracle Analytics users saw a single quote added to negative numbers (https://community.oracle.com/products/oracleanalytics/discussion/comment/43055). DevExpress warns that encoding may alter data such as negative numbers (https://docs.devexpress.com/AspNet/405106/security-considerations/prevent-csv-injection?f=blazor). A Jackson discussion found the negative-number case hard to solve without inspecting the whole string (https://github.com/FasterXML/jackson-dataformats-text/issues/326). Phone numbers starting with `+` are affected (https://www.bennadel.com/blog/4330-remediating-csv-injection-attacks-in-coldfusion.htm). The apostrophe also persists when a downstream job re-parses the CSV (https://techblog.smc.it/en/2021-01-04/beware-of-formula).
- Fit: widening the trigger set (leading whitespace, line feed, full-width) increases the false-positive surface. The framework's copy should be tested against real values (negative numbers, `+44` phone numbers, text with a leading space) and the behaviour documented, since a host reusing the framework cannot see FLS's policy. Two copies of a security helper must be kept in step, so add a test that checks both copies against one shared list of cases.

## Summary of risks for this spec

1. Default resolver `get_current_site` can return `RequestSite`, which cannot be stored in the FK. Require a real `Site` and document it.
2. Avoid ambient request state. Keep request-taking filtering, and keep the worker on the site id.
3. Read settings lazily, including the new resolver setting.
4. Make the `TASKS` check silenceable and quiet in dev and test.
5. Standalone pytest needs explicit confcutdir, rootdir and settings, and the env var must not override them.
6. Audit the unit tests for SQLite/PostgreSQL divergence before choosing.
7. Test the widened CSV escaper for both the gaps and the false positives.

status: ok
