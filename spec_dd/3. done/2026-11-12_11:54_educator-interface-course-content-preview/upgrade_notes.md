---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/form_engine/templates/form_engine/inputs/checkboxes.html
  - freedom_ls/form_engine/templates/form_engine/inputs/dropdown.html
  - freedom_ls/form_engine/templates/form_engine/inputs/file_upload.html
  - freedom_ls/form_engine/templates/form_engine/inputs/multiple_choice.html
  - freedom_ls/educator_interface/templates/educator_interface/_shell.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-course-content-preview

## Breaking changes

- **Learner course page context.** `learner_interface/course_detail.html` now renders its hero
  and body through two shared partials,
  `content_engine/partials/course_details_hero.html` and
  `content_engine/partials/course_details_body.html`, which the educator preview also uses. The
  view no longer passes `enrolment_summary`; the enrolment stat now arrives in an `extra_stats`
  list (`icon`, `label`, `value`). A downstream override of `course_detail.html` that reads
  `enrolment_summary` stops showing the enrolment stat. Re-base the override on the new template,
  or read `extra_stats`. `lesson_count`, `lesson_count_label`, `includes_assessments` and
  `organisation` are still in the context, now built by
  `freedom_ls.content_engine.course_details.course_details_context`.
- **Sidebar grid.** The `sidePanel` Alpine component no longer maintains `data-panel-open` on the
  grid, and `_base_interface.html` no longer has `x-ref="panelGrid"`. The desktop two-column rule
  is now `.side-panel-grid:has(> .side-panel-dialog[open])`. An override of
  `_base_interface.html` that keeps the old `[data-panel-open="false"]` CSS renders the desktop
  sidebar stacked above the content: copy the new `<style>` block.

## Manual steps

- Rebuild Tailwind: the new educator preview templates and the shared course-details partials
  add utility classes.
- If you override any template in `changed_template_paths`, diff it against the new version and
  re-apply your changes. The checkboxes, dropdown and multiple-choice inputs gain a
  `show_answer_key` branch that renders `<c-correct-answer-mark>`; `file_upload.html` shows
  "File upload question" when read-only with no file; `modal_host.html` gains the bottom fade and
  the `data-modal-size="wide"` rule; `table_toolbar.html` attaches `sidePanel` only when the
  table has filters.
- The cotton components `course-price`, `organisation-byline` and `organisation-mark` moved from
  `learner_interface` to `content_engine`. Their template names (`cotton/<name>.html`) did not
  change, so an override under your own `templates/cotton/` keeps working; no action needed.
