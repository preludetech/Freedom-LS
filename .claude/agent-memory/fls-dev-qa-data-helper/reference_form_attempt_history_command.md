---
name: form-attempt-history-qa-command
description: qa_create_form_attempt_history — N genuinely scored completed sittings at one form, on consecutive days, so the start page's "Previous attempts" list and its 5-row slice are browser-checkable
metadata:
  type: reference
---

`uv run python manage.py qa_create_form_attempt_history [--site-name DemoDev]
[--email ...] [--course-slug ...] [--form-slug ...] [--scores 0,1,2,3,4,2] [--keep-existing]`
Command: `freedom_ls/qa_helpers/management/commands/qa_create_form_attempt_history.py`.
Re-runnable: it deletes the learner's existing attempts at the form first unless
`--keep-existing`.

## Why it exists

`view_form_start` hands the template `completed_attempts(course_progress, collection_item)[:5]`
and `partials/exam_previous_attempts.html` renders one row per attempt
(`completed_time|date:"j M Y"` + `scores.score`/`scores.max_score` + a `widthratio` percentage).
Every other fixture command seeds **at most one sitting per learner per form**
(`qa_complete_form` guards on `CourseFormAttempt.objects.filter(...).exists()`), so neither the
multi-row list nor the five-row cap had any browser data. pytest equivalents:
`test_view_form_previous_attempts_shows_multiple_newest_first` /
`..._capped_at_five` in `learner_interface/tests/test_form_runner_views.py`.

## How it produces an exact score

`--scores` is the intended raw score of each attempt, **oldest first**. Score N = answer the
first N questions correctly and the rest with a real distractor, then `FormProgress.complete()`.
Reused wholesale from `qa_create_report_cohort`: `_complete_attempt` (answers -> `complete()` ->
backdate via `FormProgress.objects.filter(pk=...).update(...)`) and `_quiz_questions`; plus
`_course_placing` from `qa_complete_form`. The command asserts the earned score equals the
requested one, so a scoring change breaks the fixture loudly instead of silently.

- `_complete_attempt` addresses right/wrong by **`question.order`**, which restarts per page, so
  the command refuses a form whose question orders are not distinct (`_check_orders_are_distinct`).
- `compute_quiz_scores()` counts **every** question on the form toward `max_score`, answered or
  not, and `complete()` writes the strategy's own dict — never hand-write `scores`.
- Timestamps are stamped at **12:00 UTC** minus N days, not `now() - N days`: a midnight-adjacent
  stamp can render on a neighbouring date. `start_time` is `auto_now_add`, so both times are
  backdated post-save through the queryset.

## Seeded run (Sep 2026, better-form-start-page)

`demodev_quizqa@email.com` on `qa-progression-block-quiz` (QUIZ, pass 80, 4 questions, 1 page),
placed at index 2 of `qa-progression-block-course` — 6 attempts, 3-8 Sep 2026, scores
0/1/2/3/4/2 oldest-first. Oldest (3 Sep, 0/4) is the one the slice drops; giving it the only
**unique** score makes "the slice worked" a one-glance check.

## Blast radius on the progression-block fixture

`completed_form_item_ids` (`learner_progress/queries.py`) lets the **latest** completed attempt
decide the placement, so an older passing attempt does NOT unlock the next item. Ending the run
on a failing score (2/4 = 50 < 80) leaves `CourseProgress.progress_percentage` at 33 and item 3
BLOCKED — the [[reference_quiz_progression_block_command]] fixture survives intact, and
`form_start_page_buttons` still returns "Try Again". Ending on 4/4 would have flipped both.
Note `_is_content_item_completed` (views.py) is the looser `completed_attempts(...).exists()`,
so pass/fail matters for the percentage but any completion satisfies the hard-deadline check.

## Verifying without dirtying the fixture

Do not GET the player (it stamps `CourseProgress.last_accessed_time`/`last_accessed_item`).
Call `completed_attempts(record, item)[:5]` + `form_start_page_buttons(...)` and
`render_to_string("learner_interface/partials/exam_previous_attempts.html", {...})`, then regex
the `data-testid="previous-submission-score"` blocks. Gotcha: asserting `"0%" not in html` is a
**false positive** — `100%` contains `0%`. Assert on the extracted row texts instead.

See [[reference_seeding_form_attempts_around_the_site_bug]] for the sitting shape and
[[reference_form_count_edge_cases_command]] for the other start-page render branches.
