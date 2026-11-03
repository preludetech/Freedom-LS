---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # optional: add the five API apps to turn the API on
  - API_THROTTLE_RATE  # optional: default "600/min"
  - API_PAGE_SIZE  # optional: default 100
  - API_MAX_PAGE_SIZE  # optional: default 500
  - CACHES  # optional: freedom_ls_api.W001 warns when the default cache is per process
requires_package_upgrade: true
changed_packages:
  - djangorestframework==3.18.3
  - django-filter==26.2
  - drf-spectacular==0.30.0
  - pydantic==2.12.5
  - django-ninja  # removed
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: apis-for-lead-monitoring-1-foundation-and-users

FLS gains a read-only, API-key-authenticated REST API at `/api/v1/` (`freedom_ls.api`), an
admin for issuing and revoking API keys (`freedom_ls.api_admin`), and a first endpoint,
`/api/v1/users/`. Both apps are opt-in: a project that does not install them keeps working.

## Breaking changes

- `django-ninja` is no longer an FLS dependency. A project that imports `ninja` must add it to
  its own `pyproject.toml`.
- These modules are deleted: `freedom_ls/xapi_learning_record_store/api.py`,
  `freedom_ls/xapi_learning_record_store/api_urls.py` and `freedom_ls/learner_interface/apis.py`.
  Their URLs were already commented out, so only a project that imported them directly is
  affected.
- With `freedom_ls.api` installed, `freedom_ls/api/urls.py` runs `autodiscover_modules("api")`,
  which imports an `api.py` module from every installed app. A project app with its own `api.py`
  (for example an old `ninja` router) has it imported at URL load; make sure it imports cleanly.

## Manual steps

1. `uv sync` to pick up `djangorestframework`, `django-filter`, `drf-spectacular` and the now
   direct `pydantic` dependency, and to drop `django-ninja`.
2. `manage.py migrate`. New migrations: `freedom_ls_api` `0001_initial` (the `ApiKey` table) and
   `accounts` `0004_user_accounts_user_site_updated_idx` (an index on `site, updated_at, id`).
   The accounts migration runs whether or not the API is installed.
3. To turn the API on, add to `INSTALLED_APPS` (FLS's `config/settings_base.py` shows the
   order): `rest_framework`, `django_filters`, `drf_spectacular`, `freedom_ls.api` and
   `freedom_ls.api_admin`. `freedom_ls.api_admin` raises `ImproperlyConfigured` at startup if
   `freedom_ls.api` is not installed. No `REST_FRAMEWORK` setting is needed.
4. If the project has its own root URLconf, add
   `path("api/v1/", include("freedom_ls.api.urls"))` before the `freedom_ls.learner_interface.urls`
   catch-all, guarded by `apps.is_installed("freedom_ls.api")` as `config/urls.py` does.
5. Use a shared cache for `default` in production. The throttle counts requests in it, and the
   `freedom_ls_api.W001` system check warns when `DEBUG` is false and the backend is
   `LocMemCache` or `DummyCache`. `freedom_ls.deployment.settings_defaults.DATABASE_CACHES`
   passes (it needs `manage.py createcachetable`).
6. Optional settings, with their defaults: `API_THROTTLE_RATE = "600/min"`,
   `API_PAGE_SIZE = 100`, `API_MAX_PAGE_SIZE = 500`.
7. A project that adds its own endpoints registers each viewset with an `ApiScope` as
   `required_scope`; the `freedom_ls_api.E001` system check fails otherwise.

No template overrides, npm packages or Tailwind rebuild are involved. The admin stylesheet
`site_aware_models/css/admin.css` changed, so run `collectstatic` as part of the usual deploy.
