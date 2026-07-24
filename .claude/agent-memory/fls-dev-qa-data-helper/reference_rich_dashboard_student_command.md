---
name: rich-dashboard-student-command
description: qa_create_rich_dashboard_student command seeds demodev_s1 with all 3 dashboard sections + a real scored/passing quiz attempt + completed course
metadata:
  type: reference
---

`uv run python manage.py qa_create_rich_dashboard_student [SITE_NAME]` (default `DemoDev`). Command file: `freedom_ls/qa_helpers/management/commands/qa_create_rich_dashboard_student.py`. Idempotent.

PREREQUISITE (fails otherwise with `Course '...' not found on site 'DemoDev'. Available: []`): the 3 demo courses must first be loaded via `content_save` (see [[reference_demo_content_loader]]). On a fresh DB run all three:
`content_save "demo_content/functionality_demo_end_with_topic" DemoDev`
`content_save "demo_content/functionality_demo_end_with_quiz" DemoDev`
`content_save "demo_content/functionality_demo_content_widgets" DemoDev`
(dir→slug: `_end_with_topic`→`functionality-demo-show-end-with-topic`, `_end_with_quiz`→`functionality-demo-show-end-with-quiz`, `_content_widgets`→`content-widgets-demo-reference`). Demo `course.md` files have no `slug:` field — slug derives from title.

Shell import gotcha: models live under `freedom_ls.*` (e.g. `from freedom_ls.accounts.models import User`), NOT bare `accounts.*`. `RecommendedCourse` and `UserCourseRegistration` FK to the course is named `collection`, not `course` (CourseProgress uses `course`).

Seeds login-ready student `demodev_s1@email.com` (password == email, verified+primary EmailAddress) so the student dashboard shows all three sections populated:
- In progress: `functionality-demo-show-end-with-topic` at 43% (items 1-3 of 7 complete, no completed_time).
- Completed: `functionality-demo-show-end-with-quiz` at 100% with completed_time set (every topic + both QUIZ forms done). The course-finish page is reachable.
- Recommended: a `RecommendedCourse` row for `content-widgets-demo-reference`.

The completed course also gives a genuinely-scored, PASSING quiz attempt for screenshotting quiz feedback. Approach for a real scored quiz: create `FormProgress`, create `QuestionAnswer` rows with `selected_options.set([opt])` (some correct, optionally one wrong), then call `FormProgress.complete()` — it sets `completed_time`, runs `score_quiz()`, and saves. The mid-course quiz has 6 questions, pass threshold 80%; answering 5/6 correct => 83% PASS (imperfect, still passing). See [[reference_form_question_types_command]].

Critical gotcha (cost a re-run): `FormProgress.complete()` -> `save()` fires the `CourseItemProgress` save hook -> `update_course_progress_on_completion`, which creates a `CourseProgress` WITHOUT `site` (NotNullViolation on site_id). Pre-create the `CourseProgress` row with `site=site` via `get_or_create` BEFORE completing any forms in that course. The command does this in `_ensure_course_progress_row`. See [[reference_completing_a_course]].

`calculate_course_progress_percentage` (in `freedom_ls/student_management/utils.py`) signature is `(course, completed_topic_ids: set[UUID], completed_form_ids: set[UUID])` — NOT `(user, course)`.

For item 3 (educator + cohort progress matrix) the existing `qa_create_cohort_progress <SITE> --course-slug ... --cohort-name ...` command does the heavy lifting (educator `qa-educator-progress@example.com` / testpass123 with guardian `view_cohort`, 9 students at varying progress). It does NOT score quizzes or add deadlines — do that separately (FormProgress.complete() for a couple students + `CohortDeadlineFactory(cohort_course_registration=reg, site=site, deadline=..., is_hard_deadline=True)`). See [[reference_course_progress_pagination]].
