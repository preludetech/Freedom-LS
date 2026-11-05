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

# Upgrade notes: apis-for-lead-monitoring-3-referral-data

## Breaking changes

None for a project that uses the API as shipped.

A project that subclasses `freedom_ls.api.pagination.ApiKeysetPagination` and sets its `ordering`
attribute must move to the viewset instead: `ordering` is gone. The paginator now orders and pages
on the viewset's `cursor_field` (default `"updated_at"`) and then `id`. Set `cursor_field` on a
`freedom_ls.api.viewsets.ReadOnlyApiViewSet` subclass to a `DateTimeField` or `DateField` of the
model. Any other field type raises `ImproperlyConfigured` on the first list request.

## Manual steps

No action is needed to upgrade.

Four new read-only endpoints serve data under the existing `referral_data` scope:
`/api/v1/referral-codes/`, `/api/v1/referral-code-hits/`, `/api/v1/signup-attributions/` and
`/api/v1/first-touch-counts/`. An API key that already holds `referral_data` can read them as soon
as the upgrade is deployed. Before deploying, check which keys hold that scope in the admin and
revoke any that should not read referral and signup-attribution data. Signup attributions include
each user's id and email.
