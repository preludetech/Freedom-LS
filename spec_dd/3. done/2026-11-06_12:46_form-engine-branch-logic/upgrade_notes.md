---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/form_engine/templates/admin/form_engine/_answers.html
  - freedom_ls/form_engine/templates/form_engine/partials/page_children.html
  - freedom_ls/form_engine/templates/form_engine/question.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: form-engine-branch-logic

Forms can now show a page, question or content block only when an earlier answer matches
(`when:` in form content YAML, stored as `condition_option` on `FormPage`, `FormQuestion` and
`FormContent`). Forms without any `when:` behave as before.

## Breaking changes

- `FormProgress.score()`, `FormProgress.score_category_value_sum()` and
  `FormProgress.get_current_page_number()` now take the sitting's path as a required argument:
  `score(path)`, `score_category_value_sum(path)` and
  `get_current_page_number(path, answered_ids)`. Code that calls them directly must pass a
  `SittingPath`, built with `freedom_ls.form_engine.conditions.sitting_path(form_progress)`.
  Code that only calls `FormProgress.complete()` needs no change.
- `condition_option` uses `on_delete=RESTRICT`, so deleting a `QuestionOption` that gates a page,
  question or content block raises `django.db.models.RestrictedError` unless the gated rows are
  deleted in the same operation (as deleting the whole form does).

## Manual steps

- Run `manage.py migrate`. It applies `freedom_ls_form_engine.0009_formcontent_condition_option_and_more`,
  which adds `condition_option` to `FormPage`, `FormQuestion` and `FormContent`, `slug` to
  `FormQuestion` and `asked` to `FormProgress`.
- If you override any of the templates listed above, re-apply your changes to the new versions.
  Otherwise a branching form shows the wrong numbers and off-path content:
  - `form_engine/partials/page_children.html` now loops over the `page_children` context variable
    (only the children on the sitting's path) instead of `form_page.children`.
  - `form_engine/question.html` numbers a question from `question_positions` (its position on the
    path) instead of `question.question_number`.
  - `learner_interface/course_form_page.html` shows `page_position` (the page's position on the
    path) in "Page N of M" instead of `current_page_num`, which is still in the context as the
    authored page number and still posts as `page_number`. `total_pages` now counts only on-path
    pages.
  - `admin/form_engine/_answers.html` shows "Not asked" for an off-path question, from the row's
    `is_asked`.
