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

# Upgrade notes: apis-for-lead-monitoring-2-course-applications

## Breaking changes

None.

New read-only API endpoint `course-applications`, registered on the existing API router from
`freedom_ls/course_applications/api.py` and gated by the existing `course_applications` API scope.
An API key already granted that scope can read applicants' names, email addresses and answers once
this lands; review which keys hold it.

`CourseApplication.updated_at` now also moves when the application's form sitting, its answers,
an answer's uploaded file, its anonymous applicant or its user changes (receivers in
`freedom_ls/course_applications/receivers.py`). A `User` save that touches none of `email`,
`first_name` or `last_name` (`last_login` on sign-in, a password change), and an
`AnonymousApplicant` save of only `claim_email_sent_at`/`updated_at`, do not move it. Downstream
code or reports that treated `CourseApplication.updated_at` as "the application row itself was
edited" will see it move more often.

## Manual steps

- Run `uv run manage.py migrate` to apply
  `freedom_ls_course_applications.0008_courseapplication_courseapp_site_updated_idx` (adds an
  index on `site, updated_at, id`; no data change).
