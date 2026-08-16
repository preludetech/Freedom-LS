---
name: quiz-progression-block-qa-command
description: qa_create_quiz_progression_block — 3-item course where a FAILED checkbox quiz blocks the NEXT item (QA 12.1)
metadata:
  type: reference
---

`uv run python manage.py qa_create_quiz_progression_block [--site-name DemoDev]`
Command file: `freedom_ls/qa_helpers/management/commands/qa_create_quiz_progression_block.py`. Idempotent.

Why it exists: `qa_create_form_question_types` / `qa_create_multiselect_quiz_scoring`
build SINGLE-ITEM courses, so a failed quiz has no successor to block. QA 12.1
needs a quiz with a following item.

Seeds on `qa-progression-block-course`:
1. Topic `qa-progression-block-topic-01` — pre-completed for the student (so the quiz is READY).
2. Form `qa-progression-block-quiz` — QUIZ, `quiz_pass_percentage=80`, `quiz_show_incorrect=True`,
   4 option-backed questions: 3 × multiple_choice (1 correct of 3) + 1 × checkboxes (3 opts, 2 correct).
3. Topic `qa-progression-block-topic-02` — the successor that must stay BLOCKED.

Arithmetic (all MC correct): checkbox right = 4/4 = 100% ≥ 80 → PASS → item 3 unlocks;
checkbox wrong = 3/4 = 75% < 80 → FAIL → item 3 BLOCKED. Pass mark 80 also matches the
hardcoded `0.8` threshold in `form_start_page_buttons`, so the start-page button
("Try Again" vs "Next") agrees with the TOC status.

Student: reuses `demodev_quizqa@email.com` (password == email), left with NO FormProgress.

## Gotchas confirmed
- **The player does NOT enforce sequential unlock at the URL level.** `view_course_item`
  gates on hidden/access-backend/hard-deadline only — a direct GET of a BLOCKED item
  index returns 200, creates its `TopicProgress` and moves `CourseProgress.last_accessed_item`.
  So (a) QA must verify blocking via the course index/TOC (locked icon, `url=None`), not by
  URL-guessing, and (b) a smoke test that GETs the "blocked" item POLLUTES the fixture —
  delete the stray TopicProgress and reset `last_accessed_item` afterwards, or don't GET it.
- Reused helpers instead of re-writing them: `_get_or_create_user`, `_register`,
  `_ensure_course_progress_row`, `_add_options` from `qa_create_multiselect_quiz_scoring`;
  `_lay_out_course` from `qa_create_report_course` (order-idempotent ContentCollectionItem layout).
- Topic completion: create `TopicProgress` first, THEN set `complete_time` and save — the
  save hook only fires on a None → set transition ([[reference_completing_a_course]]).

See [[reference_sequential_item_unlock]] and [[reference_multiselect_quiz_scoring_command]].
