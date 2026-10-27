---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/reregister_confirmation.html
  - freedom_ls/learner_interface/templates/cotton/organisation-byline.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: organisation courses

A course can now belong to one or more organisations. Two new course frontmatter keys control
this: `organisations` (a list of organisation slugs) and `audience` (`organisation_learners`, the
default, or `public`). Existing courses get no organisations, so they behave exactly as before.

## Breaking changes

- `freedom_ls.course_access.visibility.raise_404_if_hidden_unregistered` is renamed to
  `raise_404_if_unavailable`. It now also returns a 404 when the user is not in the course's
  audience. Update any import or call in your own views.
- A course frontmatter that names an organisation slug the site does not have fails
  `content_save` with an error that lists the valid slugs. Before loading content that uses
  `organisations`, create those organisations on each site.
- `LearnerCourseRegistration.clean()` and `CohortCourseRegistration.clean()` now raise a
  `ValidationError` on `course` when a registration is created or reactivated for an
  `organisation_learners` organisation course that is not open to the learner's or cohort's
  organisation. `RegistrationRule.clean()` raises the same when a rule is created, enabled, or
  moved to such a course or organisation. Other edits of an existing row, deactivating or
  disabling it included, are not checked. Code that registers learners through forms or
  `full_clean()` will now see this error for such courses.
- `register_for_course` and `register_cohort_for_course` raise
  `freedom_ls.learner_management.queries.CourseNotOpenError`, a `ValueError` subclass, for such
  a course. Code catching `ValueError` keeps working; catch the subclass to be specific.
- `freedom_ls.organisations.utils.ensure_organisation` with `slug_base` returns the organisation
  already holding that slug, whatever its name, before falling back to the lookup by name.

## Manual steps

- Run `manage.py migrate`. This applies
  `freedom_ls/content_engine/migrations/0008_course_audience_course_organisations.py`, which adds
  `Course.organisations` and `Course.audience`.
- If you override `learner_interface/partials/course_card.html`, add
  `<c-organisation-byline :organisation="course.card_organisation" />` below the title so
  dashboard cards name the organisation a course is studied through. The new cotton component is
  `freedom_ls/learner_interface/templates/cotton/organisation-byline.html`.
- If you override `educator_interface/modal/reregister_confirmation.html`, render the new
  `refusal` context variable. The 422 re-render uses it to explain why a re-registration was
  refused.
