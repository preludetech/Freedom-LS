---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/course_title.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_course_completion.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/course_content.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_registrations.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_shared_by.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/cohort.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: educator-interface-course-list-shows-too-much

## Breaking changes

Educators no longer see another organisation's courses by default. A course whose `course.md`
lists `organisations:` is now listed, previewed and registerable in the educator interface only for
its owning organisations and for organisations named in its new `shared_with:` key. This applies
whatever the course's `audience:` is, and it applies to superusers too. A course with no
`organisations:` is unaffected.

An educator whose organisation already holds a registration on an unshared course still sees that
course in its list and on its detail page, but cannot preview its content, register anyone new on
it or reactivate a registration on it.

Learners are unaffected: learner self-join of a public course works as before.

## Manual steps

1. Run `manage.py migrate`. It applies `freedom_ls_content_engine` migration
   `0013_course_shared_with`, which adds the `Course.shared_with` many-to-many to `Organisation`.
2. If any of your organisations' educators register learners on another organisation's course,
   add a share to that course's `course.md` before you deploy, then re-run `content_save`:

   ```yaml
   organisations:
     - northwind-logistics
   shared_with:
     - harbour-college
   ```

   `shared_with` takes organisation slugs. `content_save` rejects it on a course with no
   `organisations:`, an owning organisation listed in it, a slug listed twice, and an unknown slug.
3. If you override any template in `changed_template_paths`, compare it with the new version. Most
   now name the owning organisation of a shared course (a "Shared by …" line from the new
   `partials/course_shared_by.html`, or the `course_label` and `course_shared_by` template tags in
   `educator_tags`). `panels/course_content.html` also renders a message instead of the outline when
   the content preview isn't shared with the organisation.
