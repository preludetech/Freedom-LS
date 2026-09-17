---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/form_engine/templates/form_engine/question.html
  - freedom_ls/form_engine/templates/form_engine/inputs/short_text.html  # deleted
  - freedom_ls/form_engine/templates/form_engine/inputs/number.html  # deleted
  - freedom_ls/form_engine/templates/form_engine/inputs/text_input.html  # new
  - freedom_ls/form_engine/templates/form_engine/inputs/dropdown.html  # new
  - freedom_ls/form_engine/templates/form_engine/partials/answer_errors.html  # new
  - freedom_ls/form_engine/templates/form_engine/partials/page_children.html  # new
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
  - freedom_ls/course_applications/templates/course_applications/form_page.html
  - freedom_ls/course_applications/templates/course_applications/check_your_answers.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: form_engine data field

`QuestionType` gains six types: `date`, `time`, `email`, `url`, `phone` and `dropdown`.
`FormQuestion` gains `min`, `max` and `decimal_places`. `form_engine` now checks an answer
against its question's type on the server. An answer that fails the check is not stored, and the
page comes back with a 422 that names the question.

## Breaking changes

- **`inputs/short_text.html` and `inputs/number.html` are deleted.** Both are replaced by
  `form_engine/inputs/text_input.html`, which renders every single-line input. If your theme
  overrides either deleted file, Django stops loading it and your changes disappear without an
  error. Move them into an override of `text_input.html`, which now styles every single-line input
  at once.
- **`FormProgress.save_answers()` returns a `dict[UUID, RejectedAnswer]` instead of `None`.** An
  answer that fails its type's check is left out of the save, and any row saved earlier for that
  question is left as it was. If your own code calls `save_answers()` and assumes every posted
  answer was stored, it must now check the return value.
- **Form page templates get new context keys.** Both the course runner and the application form
  now pass `rejected_answers`, `rejected_answers_error` and `next_page_url`. `has_next_page` is
  now a boolean. Before, the runner set it to the next page's URL, so an override that used
  `{{ has_next_page }}` as a link must switch to `{{ next_page_url }}`.
- **The `form-content` partial is removed from `learner_interface/course_form_page.html`.**
  Question and content rendering now comes from `form_engine/partials/page_children.html`, and
  the error callouts come from `form_engine/partials/answer_errors.html`. The runner no longer
  loads `content_tags` or `fls_base_filters` in this template.
- **Submit-and-exit can now refuse.** If the page the learner leaves from has an answer that fails
  its type's check, `form_submit_and_exit` re-renders that page with a 422 and leaves the attempt
  open. Blank required questions still don't block leaving.

## Manual steps

1. Run `manage.py migrate`. Three migrations land in `freedom_ls_form_engine`:
   `0005_alter_formquestion_type`, `0006_formquestion_max_formquestion_min` and
   `0007_formquestion_decimal_places`. All three only add fields or change choices, and the new
   fields have defaults.
2. Run `collectstatic`. `learner_interface/js/alpine-components.js` changed so the runner's answered
   count also counts `<select>` (dropdown) questions.
3. If you override `form_engine/question.html`, `learner_interface/course_form_page.html`,
   `course_applications/form_page.html` or `course_applications/check_your_answers.html`, compare
   your copy with the new FLS version and bring your changes across. In particular:
   - A form page override must include `form_engine/partials/answer_errors.html`, or a rejected
     answer returns a 422 with no page-level message.
   - A `question.html` override must add branches for the six new types. Otherwise they render the
     "UNHANDLED FORM TYPE" callout.
   - A `check_your_answers.html` override should render text answers through
     `{{ row.answer.text_answer|answer_display:row.question.type }}` (from `form_engine_tags`), so
     dates and times show in the site's locale format instead of as ISO strings.
4. Optional, for content authors: form question YAML now accepts the new `type` values plus
   `min`, `max` (for `date`, `time` and `number`; inclusive) and `decimal_places` (for `number`;
   default `0`). `content_save` rejects a bound that doesn't parse for its type, and so does the
   admin through `FormQuestion.clean()`. Quote time bounds (`min: "10:20"`). YAML can read an unquoted
   time as a number (`10:20` becomes `620`), and `content_save` rejects it.
