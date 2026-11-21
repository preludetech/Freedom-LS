---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-compliance-2-shuffle

QUIZ forms can now shuffle their pages, page children and answer options once per sitting. Three
opt-in front-matter knobs control this: `shuffle_pages`, `shuffle_questions` and `shuffle_options`.
An option can set `locked: true`, and a form question or content block can set `group:`. Every
knob is off by default, so existing forms serve in authored order, as before.

## Breaking changes

`FormProgress.furthest_page_reached`, an authored page number, is replaced by
`FormProgress.furthest_page`, a nullable foreign key to `FormPage`. Project code that reads or
writes the old field must change: read the number with `form_progress.furthest_page_number(path)`
and write through `form_progress.record_page_reached(page_number, path)`, whose signature has not
changed. Resume and the page-jump nav now follow the page a learner was shown when an author adds
or removes a page during a sitting.

A project that overrides `learner_interface/course_form_complete.html` keeps working, but its
results page labels each wrong answer with the authored question number. On a shuffled quiz that
is not the number the learner saw. Each dict `FormProgress.get_incorrect_quiz_answers()` returns
now has a `number` key holding the number the learner saw.

## Manual steps

- Run `manage.py migrate`. Migration `freedom_ls_form_engine.0011_shuffle` adds the three shuffle
  fields to `Form`, `group` to `FormQuestion` and `FormContent`, and `locked` to `QuestionOption`.
  Every new column has a default, so no data is backfilled.
  `0012_formprogress_furthest_page` adds `FormProgress.furthest_page` and fills it from each
  sitting's stored page number, and `0013_remove_formprogress_furthest_page_reached` drops the old
  column. Both run on their own; a sitting whose number is past its form's last page gets the last
  page.
- If your project overrides
  `freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html`, change
  `Question {{ item.question.question_number }}` to `Question {{ item.number }}` in your copy.
- Content that uses the new keys is checked by `content_validate`. The knobs are allowed only on
  QUIZ forms, and so is `group`. A keep-together group must sit on one page, in one unbroken run. A `locked` option
  needs `shuffle_options: true` on its form.
