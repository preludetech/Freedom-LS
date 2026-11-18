---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - PANEL_FRAMEWORK_SITE_RESOLVER  # optional: defaults to freedom_ls.panel_framework.sites.current_site_or_none
  - SILENCED_SYSTEM_CHECKS  # optional: new warnings freedom_ls_panel_framework.W001 and W002
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: extract_panels_framework-3-standalone-backend

## Breaking changes

`BulkActionRun` (`freedom_ls.panel_framework.models`) is no longer a `SiteAwareModel`. It keeps
its `site` foreign key and UUID primary key, so the table is unchanged. Migration
`freedom_ls_panel_framework.0002` changes model state only: `site` has `related_name="+"`, so
`site.bulkactionrun_set` no longer exists. But `BulkActionRun.objects` no longer filters by the current site. Downstream code that reads runs
must scope the read itself with `BulkActionRun.objects.for_request(request)` or
`BulkActionRun.objects.for_site(site_id)`, and code that creates a run must pass `site=`.
A project that never touches `BulkActionRun` directly has nothing to change.

A recorded bulk action on a request that resolves to no `Site` row now answers 422 before the
preview and records nothing.

A custom `PANEL_FRAMEWORK_SITE_RESOLVER` that raises `Site.DoesNotExist` now has that exception
propagate; return `None` to say a request belongs to no site.

## Manual steps

- A project whose settings inherit `config/settings_base.py` already gets
  `PANEL_FRAMEWORK_SITE_RESOLVER = "freedom_ls.site_aware_models.models.get_cached_site"`; no
  action needed. A project with its own settings module should set
  `PANEL_FRAMEWORK_SITE_RESOLVER` to the same value (or its own resolver) so bulk-action runs use
  FLS's site resolution, including `FORCE_SITE_NAME`. Left unset, it falls back to
  `freedom_ls.panel_framework.sites.current_site_or_none`, where `SITE_ID` wins over the request's host.
- Run `uv run manage.py check` with production settings. The new warning
  `freedom_ls_panel_framework.W001` fires when `DEBUG` is off and `TASKS['default']` uses Django's
  `ImmediateBackend` or `DummyBackend`: large bulk actions run as background tasks and need a
  durable backend with a worker. Switch the backend, or add the id to `SILENCED_SYSTEM_CHECKS` if
  that is intended.
- A project with its own settings module that keeps `SITE_ID` and the default resolver, on a
  database holding several sites, gets `freedom_ls_panel_framework.W002` from `migrate` or
  `manage.py check --database default`. Set `PANEL_FRAMEWORK_SITE_RESOLVER`, or silence W002 if
  every request really is one site.
