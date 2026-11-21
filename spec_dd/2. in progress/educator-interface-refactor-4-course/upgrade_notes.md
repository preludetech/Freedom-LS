---
requires_migrations: false
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

# Upgrade notes: educator-interface-refactor-4-course

## Breaking changes

The educator course area moved out of `freedom_ls.educator_interface.views` into the
`freedom_ls.educator_interface.panels.course` package. No behaviour, URL, template path, stored value or app label
changed, and there is no re-export shim. A downstream project that imports one of these names from `views` must
switch to the new module.

From `freedom_ls.educator_interface.views` to `freedom_ls.educator_interface.panels.course.data_tables`:

- `CourseDataTable`, `CourseCohortRegistrationDataTable`, `CourseLearnerRegistrationDataTable`

To `freedom_ls.educator_interface.panels.course.panels`:

- `CourseDetailsPanel`

To `freedom_ls.educator_interface.panels.course.content_preview`:

- `OutlineRow`, `outline_rows`, `CourseOutlineTable`, `CourseContentPanel`
- `PreviewContentAction`, `PreviewCourseDetailsAction`
- private helpers `_form_page_rows`, `_outline_item_rows`, `_all_collection_items`, `_preview_available`,
  `_outline_content_count`, `_condition_question_text`, `_form_preview_context`

To `freedom_ls.educator_interface.panels.course.data_table_panels`:

- `CourseCohortRegistrationsPanel`, `CourseLearnerRegistrationsPanel`

To `freedom_ls.educator_interface.panels.course.instance_view`:

- `CoursePanelStack`, `CourseInstanceView`

To `freedom_ls.educator_interface.panels.course.config`:

- `CourseConfig`

To `freedom_ls.educator_interface.panels.common.tables`:

- private column helpers `_course_title_column`, `_cohort_links_column`

`views.py` still imports `CourseConfig`, `_course_title_column` and `_cohort_links_column` for its own use, so
importing them from `views` keeps working for now. Don't rely on it: a later cleanup trims those imports. Import
from the new modules.

Underscore-prefixed names are not public API. They moved with the same spelling, but may change without notice.

## Manual steps

- Grep your project for `freedom_ls.educator_interface.views` followed by each name above, including strings
  passed to `mock.patch`. A patch target must name the module that looks the name up. A stale string on `views`
  can still resolve and then patch nothing, so tests pass without patching what they meant to.
- No migrations, settings, packages or Tailwind rebuild are needed.
