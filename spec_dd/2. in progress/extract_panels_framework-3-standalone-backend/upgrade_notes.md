---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - PANEL_FRAMEWORK_SITE_RESOLVER  # optional: defaults to django.contrib.sites.shortcuts.get_current_site
  - SILENCED_SYSTEM_CHECKS  # optional: new warning freedom_ls_panel_framework.W001
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: extract_panels_framework-3-standalone-backend

## Breaking changes

`BulkActionRun` (`freedom_ls.panel_framework.models`) is no longer a `SiteAwareModel`. It keeps
its `site` foreign key and UUID primary key, so the table is unchanged and there is no migration,
but `BulkActionRun.objects` no longer filters by the current site. Downstream code that reads runs
must scope the read itself with `BulkActionRun.objects.for_request(request)` or
`BulkActionRun.objects.for_site(site_id)`, and code that creates a run must pass `site=`.
A project that never touches `BulkActionRun` directly has nothing to change.

Confirming a recorded bulk action on a request that resolves to no `Site` row now raises
`PermissionDenied` and records nothing.

## Manual steps

- A project whose settings inherit `config/settings_base.py` already gets
  `PANEL_FRAMEWORK_SITE_RESOLVER = "freedom_ls.site_aware_models.models.get_cached_site"`; no
  action needed. A project with its own settings module should set
  `PANEL_FRAMEWORK_SITE_RESOLVER` to the same value (or its own resolver) so bulk-action runs use
  FLS's site resolution, including `FORCE_SITE_NAME`. Left unset, it falls back to
  `django.contrib.sites.shortcuts.get_current_site`, where `SITE_ID` wins over the request's host.
- Run `uv run manage.py check` with production settings. The new warning
  `freedom_ls_panel_framework.W001` fires when `DEBUG` is off and `TASKS['default']` uses Django's
  `ImmediateBackend` or `DummyBackend`: large bulk actions run as background tasks and need a
  durable backend with a worker. Switch the backend, or add the id to `SILENCED_SYSTEM_CHECKS` if
  that is intended.
