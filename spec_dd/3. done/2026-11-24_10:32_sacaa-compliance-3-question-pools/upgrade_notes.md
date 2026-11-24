---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/modal/content_preview.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-compliance-3-question-pools

A page of a QUIZ form can now set `draw: N` in its content file. Each sitting is then served N of
that page's questions or groups, drawn at random when the sitting starts and kept for that sitting.
Pages without `draw` behave as before.

## Breaking changes

None. The new `FormPage.draw` field is nullable and defaults to empty, so existing forms are
unchanged.

The `question_count` that the learner form start screen (`learner_interface.views.view_form`) and
the educator content preview put in their template context now comes from
`freedom_ls.form_engine.queries.count_sitting_questions`. On a form with a drawing page it is the
number of questions one sitting is served, not the number in the content files. A project that
overrides either template and shows `question_count` gets the new number with no change.
`count_form_questions` is still there and still counts every question.

## Manual steps

- Run `uv run manage.py migrate` to apply `freedom_ls_form_engine` migration `0014_formpage_draw`.
- If your project overrides
  `freedom_ls/educator_interface/templates/educator_interface/modal/content_preview.html`, add the
  new block that follows the page heading: when `entry.drawing` is set, it prints
  `{{ entry.drawing.summary }}` (for example "Draws 3 of 6 questions per attempt") in a
  `text-muted` paragraph.
- Course authors in your project can now use `draw:` on quiz pages. `manage.py content_validate`
  reports a bad `draw` before `content_save` runs: a `draw:` with no value or that is not a whole
  number, a `draw` on a form that is not QUIZ, a `draw` larger than the number of questions and
  groups on the page, and a drawing page whose questions and groups do not all hold the same
  number of questions.
