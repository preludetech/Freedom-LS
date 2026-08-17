---
name: reference-report-fixture-commands
description: qa_create_report_course / qa_create_report_cohort / qa_create_report_fixtures — the ten-fixture cohort-progress-report QA matrix, and the four gotchas that make scored fixtures work
metadata:
  type: reference
---

Three commands build the browser-QA data for the cohort progress report
(`spec_dd/.../basic_reports/3a. report_generation_qa/frontend_qa_report_generation.md`).
All idempotent, all default to
`--site-name DemoDev`, all logins follow password == email.

## `qa_create_report_fixtures` — the one you normally run

`uv run manage.py qa_create_report_fixtures [--reset] [--only <key>] [--long-course-quizzes N]`

Builds the whole matrix in one process by importing `build_report_course` and
`build_report_cohort` from the two builders (it does not shell out).

Fixture keys → cohort names: `empty-cohort` (0 students), `no-registrations` (5, no
`CohortCourseRegistration`), `tiny-cohort-short-course` (3), `small-cohort-medium-course` (9),
`standard-cohort-medium-course` (9), `large-cohort-medium-course` (25),
`xl-cohort-long-course` (40, 18 flagged), `two-course-cohort` (9, one inactive registration),
`no-progress-cohort` (9, zero rows), `no-pass-mark-cohort` (9). Cohort names are
`QA Report <Something> Cohort`; students are `qa-report-<prefix>-NN@email.com`.

Courses: `qa-report-{short,medium,long,nopass,second}-course` — 4/12/30/12/8 items with
1/4/12/4/2 quizzes. `--reset` deletes only the fixture cohorts and their `qa-report-*` students.

Also seeds `qa-report-educator@email.com` (guardian `view_cohort` on every fixture cohort) and
`qa-report-restricted@email.com` (`is_staff`, all `GeneratedReport` model perms, `view_cohort` on
*QA Report Standard Cohort* only — cohort A for the permission checks). Model-level
`student_management.view_cohort` is deliberately NOT granted: guardian returns every object to a
user holding the global perm, which would defeat object-level scoping.

## `qa_create_report_course`

`--course-key <key> --num-items N --num-quizzes Q [--questions-per-quiz n] [--big-quiz-questions n]
[--pass-percentage 50] [--no-pass-mark-quiz]`

Standalone course; quizzes evenly interleaved among topics. Additive — raising `--num-quizzes`
appends quizzes and re-lays the course out, which is how the QA 7 landscape column budget is dialled
up. `--no-pass-mark-quiz` unsets the **first** quiz's pass mark (first, not last, so most of the
cohort actually reaches it). `--big-quiz-questions >10` on the first quiz is what makes the report's
"showing worst 10 of N" confusion cap disclosure appear.

## `qa_create_report_cohort`

`--cohort-name "<name>" --num-students N [--course-slug ...] [--inactive-course-slug ...]
[--num-flagged F] [--no-progress] [--email-prefix ...] [--educator-email ...]`

Students are spread across a completion ladder stretched across the *unflagged* students
(opened-nothing-completed / 20 / 40 / 60 / 80 / 100%). `--num-flagged` cycles the three base at-risk
rules: no rows at all (`no_activity`), stopping on a failed pass-marked quiz (`failed_latest_quiz`),
and activity backdated 30 days (`inactive`). The highest-progress student gets **three** completed
attempts at the first quiz, all wrong on the same question — the QA 5.6 per-attempt vs first-attempt
cross-check.

## Gotchas confirmed

- **Auto timestamps.** `FormProgress.start_time` is `auto_now_add` and `complete()` stamps
  `completed_time` with `now()`. Backdating must be a follow-up
  `FormProgress.objects.filter(pk=...).update(start_time=..., completed_time=...)`; assigning before
  save is silently overwritten. Same for `TopicProgress.complete_time` if you rely on `save()`.
- **CourseProgress site NOT NULL.** Completing a Topic or Form fires
  `update_course_progress_on_completion`, which calls `CourseProgress.objects.update_or_create()`
  *without* a site → `NotNullViolation`. Pre-create the row with `site=` first. See
  [[reference_completing_a_course]].
- **`children()` memoization.** Write every `ContentCollectionItem` link before the first
  `viewable_items()` read on that Course instance, or the count comes back stale. See
  [[reference_course_access_types_command]].
- **`TopicProgress` is `unique_together(user, topic)`.** A Topic shared between two fixture courses
  leaks one course's completion into the other's percentages, so each QA course owns its own topics
  (slugs carry the course key).

## Report-data facts these fixtures are tuned to (`freedom_ls/reports/gather.py`)

- Completion is recomputed from `TopicProgress.complete_time` / `FormProgress.completed_time`;
  `CourseProgress.progress_percentage` is never read by the report.
- A quiz cell needs `completed_time` AND `scores` — a bare `completed_time` renders nothing.
- `MIN_RESPONDENTS_FOR_PERCENTAGE = 10` (first-attempt respondents per question), so ≥10 students
  must actually complete a quiz before confusion percentages replace plain counts.
- `CONFUSIONS_PER_QUIZ_MAX = 10`, `ATTENTION_LIST_MAX = 12`.
- Scored quizzes are built from option-backed questions only: `score_quiz()` counts every question
  toward `max_score`, so one free-text question puts a permanent ceiling under 100%. See
  [[reference_multiselect_quiz_scoring_command]].
