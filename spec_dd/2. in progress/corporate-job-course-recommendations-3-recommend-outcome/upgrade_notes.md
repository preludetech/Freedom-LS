---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/registration_rules/templates/admin/registration_rules/preview.html
  - freedom_ls/registration_rules/templates/admin/registration_rules/preview_list.html
  - freedom_ls/registration_rules/templates/admin/registration_rules/preview_reasons.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # hard: registration_rules raises ImproperlyConfigured at startup without freedom_ls.course_recommendations
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: corporate-job-course-recommendations-3-recommend-outcome

Registration rules gain a second outcome, `recommend`: a matching rule puts the course in the
learner's Recommended courses instead of registering them. Each rule that recommends a course is
recorded in the new `RuleRecommendation` model (`freedom_ls.registration_rules.models`).

## Breaking changes

- **`freedom_ls.registration_rules` now requires `freedom_ls.course_recommendations`.** If
  `registration_rules` is in `INSTALLED_APPS` and `course_recommendations` is not, startup fails
  with `ImproperlyConfigured` while models load. This is not a system check, so it cannot be
  silenced. The existing requirement on `freedom_ls.hr_attributes` still applies.
- **`RecommendedCourse` is now unique per site, user and course** (constraint
  `unique_recommended_course`). Code that creates a second row for the same user and course now
  raises `IntegrityError`; use `get_or_create` instead. The admin form reports the duplicate as a
  validation error.
- **Any registration now clears a recommendation, not just self-registration.** Receivers in
  `freedom_ls/course_recommendations/signals.py` delete a user's `RecommendedCourse` for a course
  when the user is registered for it by any path: a learner registration, a cohort registration,
  joining a registered cohort, or reactivating a learner, cohort or registration. The delete
  `initiate_course_access` used to do in `freedom_ls/learner_interface/views.py` is gone. If your
  project deleted recommendations on registration itself, that code is now redundant.
- New app dependencies: `course_recommendations` imports `learner_management`, and
  `registration_rules` imports `course_recommendations` (see `docs/app_structure.md`).

## Manual steps

- Make sure `"freedom_ls.course_recommendations"` is in `INSTALLED_APPS` if you use
  `freedom_ls.registration_rules`.
- Run `manage.py migrate`. The new migrations are:
  - `freedom_ls_course_recommendations.0002_remove_duplicate_recommendations` deletes duplicate
    `RecommendedCourse` rows, keeping the oldest per site, user and course. It cannot be
    reversed. Check for duplicates before you migrate if your project gave those rows any meaning.
  - `freedom_ls_course_recommendations.0003_recommendedcourse_unique_recommended_course` adds the
    unique constraint.
  - `freedom_ls_registration_rules.0004_alter_registrationrule_outcome_rulerecommendation` adds the
    `recommend` choice to `RegistrationRule.outcome` and creates `RuleRecommendation`.
- If you override the registration-rule preview templates under
  `freedom_ls/registration_rules/templates/admin/registration_rules/` (`preview.html`,
  `preview_list.html`), re-apply your changes on top of the new versions. They now show the
  recommend outcome, and `preview.html` includes the new partial `preview_reasons.html`.
