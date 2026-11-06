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

# Upgrade notes: apis-for-lead-monitoring-4-registrations-and-interest

## Breaking changes

None for a project that uses FLS as shipped.

`LearnerCourseRegistration`, `CohortCourseRegistration` and `CourseInterest` gain an
`updated_at` field. A save with `update_fields` on either registration model writes `updated_at`
too, so it moves on every `is_active` flip. `QuerySet.update()` and `bulk_update()` skip it.
Project code that changes these models through either must set `updated_at` itself, or the API's
incremental sync misses the change.

## Manual steps

Run `manage.py migrate`. Two migrations ship:

- `freedom_ls/learner_management/migrations/0011_registration_updated_at.py` adds `updated_at` to
  both registration models, backfills it from `registered_at`, and adds an index on
  `(site, updated_at, id)` to each.
- `freedom_ls/course_interest/migrations/0002_courseinterest_updated_at.py` does the same for
  `CourseInterest`, backfilling from `created_at`.

Each backfill updates every row of its tables in one transaction. Allow for that on a site with
many registrations.

Three new read-only endpoints serve data under the existing `registrations_and_progress` scope:
`/api/v1/learner-course-registrations/`, `/api/v1/cohort-course-registrations/` and
`/api/v1/course-interests/`. A key that already holds `registrations_and_progress` can read them
as soon as the upgrade is deployed, including each registered or interested user's id, email,
first and last name. Before deploying, check which keys hold that scope in the admin and revoke any
that should not read this data.
