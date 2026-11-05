---
name: branching-survey-command
description: qa_create_branching_survey - CATEGORY_VALUE_SUM 3-page form with page 2 gated (FormPage.condition_option) on want_extra=yes, for qa.branch@email.com
metadata:
  type: reference
---

`uv run python manage.py qa_create_branching_survey [--site-name DemoDev]` (form-engine-branch-logic, Nov 2026).
Idempotent by slug: course `branching-survey-course`, form `branching-survey`, learner `qa.branch@email.com` (pw == email).
Page 2 "Extra" has `condition_option` = Yes option of question slug `want_extra`. QuestionOptionFactory defaults
`correct=False`; pass `correct=None` for survey options. Course home `/courses/branching-survey-course/` 302s to
`/1/` (single-item course). Fresh attempt: `qa_reset_learner_progress --learner qa.branch@email.com --course-slug branching-survey-course`.
