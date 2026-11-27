---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_name.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/learner_badges.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html
  - freedom_ls/panel_framework/templates/cotton/modal-footer.html
  - freedom_ls/panel_framework/templates/cotton/modal-header.html
  - freedom_ls/panel_framework/templates/cotton/panel-close-button.html
  - freedom_ls/panel_framework/templates/cotton/panel-progress-bar.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_form.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-page-polish

## Breaking changes

- The `educator_tags` template tag `learner_course_summaries` is renamed to `learner_course_cell`,
  and it now returns a `LearnerCourseCell` (the courses the learner list's Courses cell shows),
  not a list of summaries. A project template that calls
  `{% learner_course_summaries object as summaries %}` fails to render. Switch to
  `{% learner_course_cell object as cell %}` and compare against the new
  `educator_interface/data-table-cells/learner_courses.html`.
- `<c-modal-footer>`'s Cancel button and `<c-panel-close-button>` now bind `disabled` to the host
  Alpine component's `running`. FLS's own hosts (`appModal`, `quickView`, `sidePanel`) declare it.
  A project Alpine component that renders either of these components must declare
  `running: false`, because the CSP Alpine build throws on an undeclared name.

## Manual steps

- Rebuild Tailwind: dialog footer buttons are now small below `md` (the 44px minimum height is
  gone), and templates use new utility classes.
- If the project overrides any template listed in `changed_template_paths`, re-apply its
  customisations on top of the new FLS version. The learner Courses tab
  (`panels/learner_courses.html`) is now a table followed by one section per course, and the bulk
  confirmation dialog gained a run status line and a request-error holder.
