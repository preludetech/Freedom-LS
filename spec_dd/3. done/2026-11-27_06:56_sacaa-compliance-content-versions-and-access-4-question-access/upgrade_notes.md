---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_report_body_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/quiz_attempt_paper.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_outline_actions.html
  - freedom_ls/form_engine/templates/admin/form_engine/answers_change_form.html
  - freedom_ls/reports/templates/reports/partials/confusions.html
  - freedom_ls/reports/templates/reports/partials/contents.html
  - freedom_ls/reports/templates/reports/partials/learner_detail.html
  - freedom_ls/reports/templates/reports/partials/methodology.html
  - freedom_ls/reports/templates/reports/partials/quiz_confusion.html
  - freedom_ls/reports/templates/reports/report.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-compliance-content-versions-and-access-4-question-access

Quiz question detail (questions, options and correct answers) is now limited to holders of a new
organisation-scoped role, `question_bank_viewer`, and every view of it writes a `question.viewed`
audit entry. The role grants the new permission
`freedom_ls_content_engine.view_course_questions`. Organisation admins can grant it from the Staff
section; the base role config gives `organisation_admin` and `site_admin` the new
`freedom_ls_role_based_permissions.assign_question_bank_viewer` permission to do so.

## Breaking changes

- **Educators lose quiz question detail until they are granted the role.** Without
  `question_bank_viewer` in the organisation, an educator sees a disabled Preview on quiz rows of the
  course outline (a direct preview request is refused), a note in place of the Report tab's quiz
  confusions, and a note in place of the Paper panel on a learner's quiz attempt. Grant the role to
  everyone who still needs that detail.
- **The cohort report PDF no longer carries question detail.** The "Quiz confusions across the
  cohort" section and each learner's "Incorrect answers" tables are gone, along with their contents
  entries and the methodology paragraphs that described them. `reports/partials/confusions.html`
  and `reports/partials/quiz_confusion.html` are deleted, and the `confusions` empty-state slot and
  `data-subhead="wrong-answers"` hook no longer render. A theme that styles them can drop those
  rules.
- **Removed report data.** `SelectedOption`, `WrongAnswer` and `QuizWrongAnswers` are gone from
  `freedom_ls.reports.report_data`, `LearnerDetail.wrong_answers` is gone, and
  `build_wrong_answers_by_learner_quiz` is gone from `freedom_ls.reports.gather`. Downstream code
  that read them must stop. The report screen cache's `SCHEMA_VERSION` moved to 5, so cached screen
  data from before the upgrade is ignored rather than unpickled.
- **The Django admin no longer shows quiz answers.** A quiz `FormProgress` change page shows "Answers
  to quizzes are not shown in the admin." in place of its answers, the `QuestionAnswer` admin list
  excludes quiz answers, and the answer-file download view returns 404 for a file attached to a quiz
  answer.
- **The Paper panel template moved.** `educator_interface/panels/quiz_attempt_paper.html` is deleted
  and replaced by the lazily loaded
  `educator_interface/panels/quiz_attempt_paper_region.html`. Move any override to the new path.
- **Custom role modules need the new role.** A site whose role config comes from its own module
  through `FREEDOMLS_PERMISSIONS_MODULES` does not pick up the base roles. Add a
  `question_bank_viewer` role (organisation scoped, with
  `freedom_ls_content_engine.view_course_questions`) and give
  `freedom_ls_role_based_permissions.assign_question_bank_viewer` to the roles that should grant it,
  mirroring `freedom_ls/role_based_permissions/roles.py`. Without it nobody on that site can see
  question detail, superusers aside.

## Manual steps

1. Run `uv run manage.py migrate`. This applies `content_engine/0018_alter_course_options` and
   `role_based_permissions/0005_alter_objectroleassignment_options`. Both only change model
   permissions; no table or column changes.
2. Grant `question_bank_viewer` in each organisation to the staff who review quiz questions, answers
   and attempts.
3. If you use your own role module (see Breaking changes), add the role and the assign permission
   to it.
4. If you override any template in `changed_template_paths`, merge the change: the gated Report tab
   confusions, the disabled quiz Preview with its reason, the admin's hidden-quiz-answers note, the
   removed PDF sections, and the Paper panel's new region template. If your theme overrides
   `freedom_ls/reports/static/reports/print.css`, its confusion and wrong-answer rules are no longer
   used.
