---
name: multiselect-quiz-scoring-qa-command
description: qa_create_multiselect_quiz_scoring — dedicated learner + checkbox quiz + NULL-pass-percentage quiz for multi-select quiz scoring browser QA
metadata:
  type: reference
---

`uv run python manage.py qa_create_multiselect_quiz_scoring [--site-name DemoDev]`
Command file: `freedom_ls/qa_helpers/management/commands/qa_create_multiselect_quiz_scoring.py`. Idempotent.

Seeds:
- Learner `demodev_quizqa@email.com` (password == email, verified+primary allauth EmailAddress, active).
- Registration on `qa-question-types-course` (reuses the helper functions `_get_or_create_course`, `_build_form`, `_attach_form_to_course` imported from `qa_create_form_question_types`, so that course/form is created if missing). Form `qa-all-question-types-form`: QUIZ, pass % = 50, show_incorrect True, checkboxes q with 3 opts / 2 correct.
- New course `qa-quiz-no-pass-pct-course` (item 1 = form `qa-quiz-no-pass-pct-form`): QUIZ, `quiz_pass_percentage=None`, show_incorrect True, checkboxes q (3 opts/2 correct) + multiple_choice q (3 opts/1 correct). For "results page renders score with no pass/fail verdict".
- Cohort `QA Multi-Select Quiz Scoring Cohort` with `CohortCourseRegistration` for BOTH courses (so one educator panel exercises pass-mark + no-pass-mark), 3 members, and educator `demodev_quizqa_educator@email.com` granted guardian `view_cohort`.
- Two extra learners with genuinely scored COMPLETED attempts: `demodev_quizqa_pass@email.com` (all option-questions correct) and `demodev_quizqa_fail@email.com` (all wrong). The main QA learner is left with NO progress on purpose.

Both forms are item index 1 of their own course, so sequential item unlock ([[reference_sequential_item_unlock]]) never blocks them.

## Gotchas confirmed
- The `QuestionType` value is **`checkboxes`**, NOT `checkbox`. A QA query for `type='checkbox'` returns 0 rows even when checkbox questions exist. Discriminator field is `FormQuestion.type`; text field is `FormQuestion.question`; options related_name is `options` with `text`/`value`/`order`/nullable `correct`.
- The player's `.../fill_form/<page>` URL **302s back to the start screen** until the attempt is started. Starting is a POST to `/courses/<slug>/<index>/start_form` (url name `form_start`). A plain GET of fill_form is not a valid smoke test.
- Smoke-testing views: `Client.login()` blows up with `AxesBackendRequestParameterRequired` (django-axes). Use `client.force_login(user)` instead, and set `HTTP_HOST="127.0.0.1:8000"` because dev site resolution is by host header.
- To smoke-test a runner page without leaving FormProgress on the QA learner, wrap the client calls in `transaction.atomic()` and raise to roll back.

## Scoring / cohort-panel facts
- `score_quiz()` counts EVERY `FormQuestion` toward `max_score`, including `short_text`/`long_text`, and `is_quiz_answer_correct` returns False when a question has no `correct=True` option. So free-text questions are unscoreable: on `qa-all-question-types-form` (4 questions, 2 option-backed) the MAXIMUM achievable score is 2/4 = 50%. That is exactly why its pass mark is 50 — "all correct" lands on PASS and anything less FAILs.
- `FormProgress.passed()` **raises ValueError** when `form.quiz_pass_percentage is None`. Any surface that calls it must guard first — this is the crash risk QA 12.5 is checking.
- Scoring an attempt in a script: create `FormProgress`, create `QuestionAnswer` rows, `answer.selected_options.set([...])`, then `FormProgress.complete()` (sets completed_time + runs `score_quiz()` + saves). Pre-create `CourseProgress` WITH `site=` first or the completion save-hook raises NotNullViolation on site_id ([[reference_completing_a_course]]).
- Educator cohort panel: `/educator/cohorts/<cohort_uuid>` and tab `/educator/cohorts/<uuid>/__tabs/course_progress`; the HTMX sub-panel is `.../__tabs/course_progress/__panels/course_progress`. A cohort renders "No course registrations found for this cohort." until a `CohortCourseRegistration` exists. Access is via guardian `get_objects_for_user(user, "view_cohort", ...)`, so grant `assign_perm("view_cohort", educator, cohort)` (superusers see everything).
