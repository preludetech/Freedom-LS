---
name: free-text-survey-qa-command
description: qa_create_free_text_survey — a NON-scored (CATEGORY_VALUE_SUM) two-page questionnaire of short_text/long_text questions, for free-text QA
metadata:
  type: reference
---

`uv run python manage.py qa_create_free_text_survey [--site-name DemoDev]`
Command file: `freedom_ls/qa_helpers/management/commands/qa_create_free_text_survey.py`. Idempotent.

Seeds course `qa-free-text-survey-course` (single item = the form, index 1) + form
`qa-free-text-survey-form` (**CATEGORY_VALUE_SUM**, `quiz_pass_percentage=None`,
`quiz_show_incorrect=None`), 2 pages × (1 `short_text` + 1 `long_text`); page 1 required,
page 2 optional. Registers `demodev_quizqa@email.com` (creates it if absent, password == email).

## Strategy facts (why CATEGORY_VALUE_SUM is "the survey strategy")

- `FormStrategy` has exactly **two** members: `QUIZ` and `CATEGORY_VALUE_SUM`. There is no third
  "survey" strategy, so CATEGORY_VALUE_SUM *is* the questionnaire/survey one (it is what the demo
  `course-feedback` and `functionality_demo_end_with_topic/4. survey` forms use).
- `score_category_value_sum()` skips every question whose `type != "multiple_choice"`. A
  CATEGORY_VALUE_SUM form built only from free-text questions completes with `scores == {}`.
- `course_form_complete.html` puts **all** pass/fail + incorrect-answer markup inside
  `{% if form.strategy == "QUIZ" %}`; the else-branch is just a "Form complete!" banner plus a
  category-score block guarded by `{% if show_scores and scores %}` (empty dict → nothing).
  Verified: no "Quiz passed"/"Quiz not passed"/"Review incorrect answers" in the response.

## Runner facts confirmed

- Free-text inputs are `name="question_<uuid>"` for both `short_text` (input) and `long_text`
  (textarea); saved values are re-rendered from `existing_answers` on GET, so a **multi-page** form
  lets QA submit page 1, hit the runner's "Previous" link on page 2 and see the answers shown back.
- Flow that works headlessly: `POST /courses/<slug>/<i>/start_form` →
  `POST .../fill_form/1` → `POST .../fill_form/2` → 302 to `.../complete`.
