---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_outline_actions.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: reference-material-content-3-educator-reference

## Breaking changes

None. The educator course page gains a "Reference" panel after "Course content". It lists the
course's reference parts and previews their topics read-only. No model, URL pattern, setting or
package changed.

A downstream project that replaces `CoursePanelStack.children` in
`freedom_ls/educator_interface/panels/course/instance_view.py` with its own dict will not show the
new panel until it adds `"reference": CourseReferencePanel` (from
`freedom_ls.educator_interface.panels.course.content_preview`).

## Manual steps

- Rebuild Tailwind (`npm run tailwind_build`). The course outline table's columns now use fixed
  width utilities (`w-16`, `w-36`, `w-28` with matching `min-w-*` and `max-w-*`) set in
  `freedom_ls/educator_interface/panels/course/content_preview.py`. A stale bundle leaves the
  columns unsized.
- If you override
  `freedom_ls/educator_interface/templates/educator_interface/partials/course_outline_actions.html`,
  re-apply your changes to the new version. The Preview trigger now shows only when the panel
  provides a `preview_content` action URL (`{% elif object.preview_query and row_action_urls.preview_content %}`).
  The partial is shared by the "Course content" and "Reference" panels.
- The new panel template `educator_interface/panels/course_reference.html` extends
  `educator_interface/panels/course_content.html`. An override of `course_content.html` now also
  styles the Reference panel. Check that it still reads right there.
