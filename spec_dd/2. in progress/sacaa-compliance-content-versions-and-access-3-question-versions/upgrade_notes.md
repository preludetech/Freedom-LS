---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/course_applications/templates/course_applications/check_your_answers.html
  - freedom_ls/form_engine/templates/admin/form_engine/_answers.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/quiz_attempt_paper_region.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-compliance-content-versions-and-access-3-question-versions

## Breaking changes

- **Form questions are versioned.** A new model, `freedom_ls.form_engine.models.FormQuestionVersion`,
  holds an immutable snapshot of each question's wording and options. `QuestionAnswer` gains a
  nullable `question_version` foreign key (`on_delete=PROTECT`). Versions refuse ORM `update()`,
  `bulk_update()` and `delete()`, and a database trigger (`form_question_version_immutable`)
  refuses `UPDATE` and `DELETE` on the table.
- **Deleting a question that has versions is refused** by the `PROTECT` foreign key. Downstream
  code or management commands that delete `FormQuestion` rows must delete the pinned answers, then
  call `freedom_ls.form_engine.models.delete_question_versions(questions)` (development commands
  only), then delete the questions.
- **Helper signatures changed.** `freedom_ls.form_engine.queries.answer_value(answer, question)`
  and `freedom_ls.form_engine.exports.answer_cell(answer, question, *, is_asked=True)` now take the
  question the answer was given on. Build it with
  `freedom_ls.form_engine.models.answered_questions(answers)`, which maps question id to the
  answered (version-backed) question.
- **Course application export has new columns.** Each question column is followed by a
  `<header> (version)` column. Anything that parses the export by column position must be updated.
- **Course application API.** `question_text`, `question_type` and `value` now read from the
  answered version rather than the live question. The response shape is unchanged.

## Manual steps

- Run `manage.py migrate`. It applies `freedom_ls_form_engine` migrations
  `0020_formquestionversion`, `0021_backfill_question_versions` and
  `0022_question_version_trigger`.
  - `0021_backfill_question_versions` writes version 1 of every existing question (its content at
    migration time, not its original wording) and pins every `QuestionAnswer` and served quiz paper
    to it, in chunks of 500. On a large `QuestionAnswer` table this takes a while; plan the deploy
    window for it.
  - `0022_question_version_trigger` creates a PL/pgSQL function and trigger on
    `freedom_ls_form_engine_formquestionversion`. The role that runs migrations must own that table.
- If you override any template in `changed_template_paths`, re-apply your changes:
  - `check_your_answers.html` and `admin/form_engine/_answers.html` loop over `row.selected_options`
    (the answered version's options) instead of `row.answer.selected_options.all`.
  - `quiz_attempt_paper_region.html` drops the "Question and option wording is the quiz's current
    wording." note, since the paper now shows the version the learner answered.
- `content_save` now prints `Question versions: N new, M revised, K unchanged` (plus one line per
  revised question) on a run that saves questions. Update any script that parses its output.
