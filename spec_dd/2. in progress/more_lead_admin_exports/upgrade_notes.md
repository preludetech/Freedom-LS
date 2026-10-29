---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: more_lead_admin_exports

## Breaking changes

None.

Two admin classes now have a different base. `freedom_ls.accounts.admin.UserAdmin` and
`freedom_ls.course_applications.admin.CourseApplicationAdmin` now extend
`SiteAwareExportModelAdmin` instead of `SiteAwareModelAdmin`, and set `resource_classes` to
`UserResource` and `CourseApplicationResource`. A project that subclasses either admin, or
unregisters and re-registers it, gets the CSV export action unless it overrides
`resource_classes` or uses a different base.

`FormulaSafeCSV` (in `freedom_ls.site_aware_models.admin_exports`) now formula-escapes header
cells as well as data cells. A custom resource whose column header starts with `=`, `+`, `-`, `@`,
tab or carriage return will see that header escaped in its exports.

## Manual steps

None.
