---
requires_migrations: true
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

# Upgrade notes: apis-for-lead-monitoring-6-conversions

## Breaking changes

None. The change adds two read-only API endpoints, `attribution-touches` and `conversions`, under
the existing `referral_data` scope. API keys that already hold that scope can read them with no
change. Nothing existing was renamed or removed.

## Manual steps

- Run `manage.py migrate`. Migration
  `freedom_ls/referral_tracking/migrations/0008_referral_code_upper_indexes.py` adds three
  expression indexes on `UPPER(...)` of the referral code columns of `AttributionTouch` and
  `Conversion`. On a large table, schedule it for a quiet period: `AddIndex` builds each index in
  one pass and locks writes to the table while it runs.
- A downstream project that pins the OpenAPI schema, or generates a client from it, should
  regenerate it to pick up the two new endpoints and their filters.
