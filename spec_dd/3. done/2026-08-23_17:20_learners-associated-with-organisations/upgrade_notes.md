---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/user_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: learners-associated-with-organisations

A new `Learner` model records a user's association with an organisation. Enrolment records now hang
off `Learner` instead of `User`, so an enrolment with no organisation can no longer be represented.
A user may hold a `Learner` row in more than one organisation.

## Breaking changes

**`learner_management`'s `0001_initial` was regenerated, not added to.** The field swap is destructive
and there is no backfill, no repair command and no data migration. An install carrying data it wants
to keep is **not supported by this release** — the database must be dropped and recreated.
`freedom_ls/reports/migrations/0001_initial.py` still depends on
`("freedom_ls_learner_management", "0001_initial")`; the name and the `Cohort` dependency are unchanged,
so that dependency still resolves.

**Model renames and field swaps** (`freedom_ls.learner_management.models`):

- `UserCourseRegistration` → `LearnerCourseRegistration`. Its `user` and `organisation` fields are
  replaced by a single `learner` FK. Reach the person as `registration.learner.user` and the
  organisation as `registration.learner.organisation`.
- `Course.user_registrations` → `Course.learner_registrations`. The reverse accessor on the
  registration is `learnercourseregistration_set`, not `usercourseregistration_set`.
- `CohortMembership.user` → `CohortMembership.learner`.
- `UserCohortDeadlineOverride.user` → `UserCohortDeadlineOverride.learner`.
- Unique constraints renamed accordingly: `unique_learner_cohort_membership` and
  `unique_learner_course_registration` (now `site_id, learner, collection` — the `organisation` column
  is gone). `Learner` adds `unique_learner_per_organisation` on `(user, organisation)`.
- `CohortMembership.clean()` now rejects a learner whose organisation differs from the cohort's.

**Creating either enrolment record now requires a `Learner`.** Use
`freedom_ls.learner_management.utils.ensure_learner(user, organisation)` — idempotent, and it
reactivates a previously removed learner.

**Behaviour change: deactivating a `Learner` revokes that person's access to course content held
through that organisation.** Registrations, memberships and progress rows are untouched — only the
access gate changes — and reactivating restores access.

`is_registered_for_course`, `is_registered_for_course_expression` and `get_course_registrations` keep
their names and signatures but now additionally require an active `Learner`. A downstream project that
reimplemented any of them must add the same condition. Note that the two cohort conditions must sit in
a single `filter()` call, or a cohort holding both a removed and an active `Learner` for the same user
will leak access.

**`users_visible_to` is removed.** Use `learners_visible_to(user, organisation)`, which returns
`Learner` rows (already filtered to `is_active=True`). A project that needs the people instead can
wrap it: `User.objects.filter(pk__in=learners_visible_to(u, o).values("user_id"))`.

**Educator interface path change.** `organisations/<slug>/users/…` is now
`organisations/<slug>/learners/…`, the section is labelled "Learners", and it lists `Learner` rows —
so the instance pk in that path is a `Learner` pk, not a `User` pk. Any downstream link, bookmark or
test that builds that URL must be updated.

**The educator interface's Interested Learners panel is removed.** `CourseInterest` is now read in the
Django admin via the new `CourseInterestAdmin`. The Courses list keeps its interest count.

**Factories** (`freedom_ls.learner_management.factories`): `UserCourseRegistrationFactory` →
`LearnerCourseRegistrationFactory`, and a new `LearnerFactory`. `CohortMembershipFactory` and
`LearnerCourseRegistrationFactory` take `learner` in place of `user`/`organisation`. There is no
back-compat `user=` / `organisation=` shim — rewrite call sites as
`learner__user=u, learner__organisation=o`.

**Not** breaking: the `course.registered` webhook payload is unchanged. Its `user_id` and `user_email`
are now resolved through `self.learner.user` inside `LearnerCourseRegistration.save()`.

## Manual steps

1. **Drop and recreate the database, then run `uv run manage.py migrate`.** There is no upgrade path
   from an existing `learner_management` schema.
2. Repoint your own code at the renamed models, fields and helpers listed above, and create `Learner`
   rows via `ensure_learner(user, organisation)` before creating any enrolment record.
3. Review and re-apply any customisation to
   `freedom_ls/educator_interface/templates/educator_interface/data-table-cells/user_courses.html` —
   it has been renamed to `learner_courses.html` in the same directory, and its loop now reads
   `object.learnercourseregistration_set.all`. An override still sitting at the old path will be dead
   and silently ignored.
4. If you extend the role permission registry, note that four `*_learner` permissions
   (`view/add/change/delete_learner`) are present but commented out, and the
   `*_usercourseregistration` entries are now `*_learnercourseregistration`.
5. No settings change, no package upgrade, no npm install, and no Tailwind rebuild are needed.
