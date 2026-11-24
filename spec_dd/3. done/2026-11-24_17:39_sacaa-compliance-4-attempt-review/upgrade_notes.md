---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_details_value.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: sacaa-compliance-4-attempt-review

Educators can now open a learner's quiz attempt from the Courses tab of the learner page. The
attempt number opens a quick view, and from there the full attempt review page at
`quiz-attempts/<form_progress_id>` in the educator interface. That page shows the paper the
learner was served, their answers and how each one was marked.

## Breaking changes

- `freedom_ls.reports.report_data.QuizAttempt` has a new required first field,
  `form_progress_id: UUID`. Code that builds a `QuizAttempt` itself, positionally or by keyword,
  must pass it.
- `freedom_ls.panel_framework.views.build_breadcrumbs` takes a new `request` argument, placed after
  `url_name` and before `current_instance`. Code that calls it directly must pass the request.
- In the panel framework, a list path to a `ListViewConfig` section with no `list_view` now returns
  404. Before this change it raised `ValueError`.

Code that only extends FLS through panel configs and templates needs no changes. The new
`SectionConfigBase.in_menu` attribute, `SectionConfigBase.is_in_menu()`,
`ListViewConfig.get_back_link()` and the `"datetime"` kind of `InstanceDetailsPanel.detail_row`
are additions with defaults that keep the old behaviour.

## Manual steps

- Rebuild Tailwind. The new educator and `form_engine/answers/` templates use utility classes that
  your CSS bundle must include.
- If you override any of these templates, re-apply your customisations on top of the new versions:
  - `educator_interface/panels/learner_courses.html`: the attempt number is now a quick-view link
    when the attempt can be opened, driven by a new `openable_sitting_ids` context value. The table
    also shows as cards on narrow screens.
  - `learner_interface/course_form_complete.html`: the "This quiz has changed since you sat it" note
    is now a `<c-callout tone="info">`, not a hand-built left-border box.
  - `panel_framework/panels/_details_value.html`: handles the new `"datetime"` row kind with
    `<c-panel-datetime>`.
