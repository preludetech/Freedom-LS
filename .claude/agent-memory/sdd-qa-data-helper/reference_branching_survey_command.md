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

**Second sitting while keeping the first (Nov 2026):** needs NO data change. There is no
max-attempts/retake field on Form, ContentCollectionItem or CourseProgress; the start screen shows
"Finish Course" after a non-quiz completion (`form_start_page_buttons`), but a plain GET of
`/courses/branching-survey-course/1/start_form` mints a fresh FormProgress+CourseFormAttempt and
302s to `/1/fill_form/1`. Verified with an atomic+raise Client probe (HTTP_HOST 127.0.0.1:8000).
Do NOT run qa_reset_learner_progress for this ask — it deletes the first sitting.

**Rebuild after a content wipe (Nov 2026):** after `danger_clear_all_course_progress` + `danger_content_delete`
+ `content_save demo_content DemoDev`, just re-run the command; the learner (pk 73) is reused, course/form are
recreated. Inspection traps: `LearnerCourseRegistration` filters by `learner__user=` and `course__slug`
(no `user`/`collection` field); `CourseFormAttempt` is NOT in `form_engine.models` - check `FormProgress` count.
