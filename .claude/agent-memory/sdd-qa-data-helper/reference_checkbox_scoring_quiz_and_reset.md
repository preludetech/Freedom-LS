---
name: checkbox-scoring-quiz-and-progress-reset
description: qa_create_checkbox_scoring_quiz (clean option-backed scored quiz, optional checkbox question) + qa_reset_learner_progress (re-walkable fixtures); quiz retake mechanics
metadata:
  type: reference
---

Two commands added for the quiz-marking browser QA plan
(`spec_dd/.../3b. quiz_marking_qa/frontend_qa_quiz_marking.md`).

## `qa_create_checkbox_scoring_quiz [--site-name DemoDev]`

`freedom_ls/qa_helpers/management/commands/qa_create_checkbox_scoring_quiz.py`. Idempotent.

Single-item course `qa-checkbox-scoring-course` (item 1) -> quiz `qa-checkbox-scoring-quiz`:
QUIZ, `quiz_show_incorrect=True`, pass mark 80, **option-backed questions only** so 100% is
reachable (unlike `qa-all-question-types-form`, whose free-text questions cap it at 2/4 = 50%):

1. `multiple_choice`, **required**, 3 opts / 1 correct
2. `checkboxes`, **NOT required**, 3 opts / 2 correct

max_score = 2. MC right + checkbox exact -> 2/2 = 100% PASS; MC right + anything else -> 1/2 = 50%
FAIL. Registers `demodev_quizqa@email.com` and adds the course to
*QA Multi-Select Quiz Scoring Cohort* (reuses that command's helpers).

**Why the checkbox question is optional:** `form_fill_page` re-renders with **422** when a
`required` question has no submitted answer, so the "tick nothing" row of the scoring matrix is
un-submittable while the question is required. Every other checkbox fixture in the repo marks it
required.

## `qa_reset_learner_progress --learner EMAIL [--course-slug SLUG]... [--include-topics]`

`freedom_ls/qa_helpers/management/commands/qa_reset_learner_progress.py`.

Deletes `FormProgress` (cascades `QuestionAnswer`), optionally `TopicProgress`, and *resets* (never
deletes) `CourseProgress` to a freshly-registered state (`completed_time=None`,
`progress_percentage=0`, `last_accessed_*=None`). Browser QA leaves a pile of attempts behind and
there is no UI route to clear them; `demodev_quizqa@email.com` had 21 stale `FormProgress` rows
after one earlier pass, which turned "Start Form" into "Continue Form"/"Next" and left the
progression-block course's item 3 unlocked.

Default is **forms only on purpose**: topic completions are what make a mid-course quiz reachable
under sequential unlocking (demo `functionality-demo-course-parts` knowledge-check is item 5). Use
`--include-topics` only when the topics should be re-walked, then re-run the fixture command to
restore any pre-completed topic.

## Quiz retake / attempt mechanics (verified)

- Retaking is always possible: `form_start` calls
  `learner_progress.attempts.get_or_create_incomplete`, which makes a **new** attempt when every
  existing one is completed. The URL is a plain **GET** of
  `/courses/<slug>/<index>/start_form`.
- The results page only renders the "Retry quiz" button when `quiz_verdict == "failed"`; the start
  screen's button logic (`form_start_page_buttons`) uses a **hardcoded 0.8** threshold, not the
  form's pass mark. After a PASS the only route to another attempt is typing the `start_form` URL.
- `course_form_complete` shows the **latest completed** attempt (`-completed_time`), so earlier
  attempts stay in the DB but are invisible in the player.
- **Unanswered != incorrect.** `save_answers` stores no `QuestionAnswer` row for a question with no
  submitted answer (and deletes any earlier row), and `get_incorrect_quiz_answers()` `continue`s on
  `QuestionAnswer.DoesNotExist`. So leaving an optional checkbox question blank scores 0 but the
  question is **omitted** from the incorrect-answers list — score and list disagree by design, and
  it is pre-existing behaviour, unrelated to the exact-match checkbox fix.
- `get_course_index(user, course, can_access_content=True)` is the read-only way to check TOC
  statuses (READY / BLOCKED / COMPLETE) without GETting player URLs, which pollutes fixtures.

## DemoDev demo-content facts (QA 13)

`mid-course-quiz` (item 2 of `functionality-demo-show-end-with-quiz`, pass 80, 6 questions),
`end-course-quiz` (item 4, pass 50, `show_incorrect=False`, 6 questions) and `knowledge-check`
(item 5 of `functionality-demo-course-parts`, pass 80, 3 questions) are **all single-select
`multiple_choice`, exactly one correct option each** — no checkboxes and no free-text in any scored
demo quiz, and no multi-correct `multiple_choice` anywhere on DemoDev.
