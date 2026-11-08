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

# Upgrade notes: apis-for-lead-monitoring-5-course-progress

## Breaking changes

None for a project that uses FLS as shipped.

`CourseProgress` gains an `updated_at` field. A save with a non-empty `update_fields` writes
`updated_at` too, so every save moves it. `QuerySet.update()` and `bulk_update()` skip it. Project
code that changes `CourseProgress` through either must set `updated_at` itself, or the API's
incremental sync misses the change.

A background recalculation of `progress_percentage` now saves only when the percentage differs from
the value in the database.

## Manual steps

Run `manage.py migrate`. `freedom_ls/learner_progress/migrations/0003_courseprogress_updated_at.py`
adds `updated_at` to `CourseProgress`, backfills it with the latest of each row's `created_at`,
`started_at`, `last_accessed_time` and `completed_time`, and adds an index on
`(site, updated_at, id)`. The backfill updates every course progress row in one transaction. Allow
for that on a site with many learners.

A new read-only endpoint, `/api/v1/course-progress/`, serves course progress under the existing
`registrations_and_progress` scope, including each learner's user id, email, first and last name
and organisation. A key that already holds `registrations_and_progress` can read it as soon as the
upgrade is deployed. Before deploying, check which keys hold that scope in the admin and revoke any
that should not read this data.
