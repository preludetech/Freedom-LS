---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/form_engine/templates/form_engine/inputs/checkboxes.html
  - freedom_ls/form_engine/templates/form_engine/inputs/dropdown.html
  - freedom_ls/form_engine/templates/form_engine/inputs/multiple_choice.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-compliance-1-served-paper-record

Each quiz sitting now records the paper it was served (pages, questions and option order) in the
new nullable `FormProgress.served_paper` field. Navigation, option rendering and quiz scoring read
it. A `FormProgress` with no served paper (every existing row) behaves as before; there is no
backfill.

## Breaking changes

- `FormProgress.record_page_reached(page_number, path)` now takes the sitting's `SittingPath` as a
  required second argument. Downstream code that calls it with only a page number raises
  `TypeError`; pass the path the view already built (for example from
  `freedom_ls.form_engine.conditions.sitting_path`).
- The option input templates no longer loop over `question.options.all`. They load
  `form_engine_tags` and call `{% question_options as options %}`, which returns the options in
  the served order. An override that still loops over `question.options.all` keeps rendering, but
  ignores the served order once later specs start shuffling.

## Manual steps

1. Run `uv run manage.py migrate` to apply
   `freedom_ls/form_engine/migrations/0010_formprogress_served_paper.py`.
2. If you override any of these templates, re-apply your changes on top of the new versions:
   - `form_engine/inputs/checkboxes.html`, `form_engine/inputs/dropdown.html` and
     `form_engine/inputs/multiple_choice.html`: replace `question.options.all` with the
     `question_options` tag shown above.
   - `learner_interface/course_form_page.html`: the runner's top bar and footer are no longer
     `sticky ... z-20`, so the exit dialog's backdrop covers the footer.
3. Code that calls `compute_quiz_scores()`, `score_quiz()` or `get_incorrect_quiz_answers()` on
   `FormProgress` needs no change: the new `path` argument is optional and defaults to the stored
   served paper.
