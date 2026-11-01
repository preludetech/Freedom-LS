---
name: legacy-checkbox-score-qa-command
description: qa_create_legacy_checkbox_score — crafts a pre-fix checkbox attempt whose stored score disagrees with exact-match rescoring, in a report-ready cohort
metadata:
  type: reference
---

`uv run python manage.py qa_create_legacy_checkbox_score [--site-name DemoDev]`
Command file: `freedom_ls/qa_helpers/management/commands/qa_create_legacy_checkbox_score.py`.
Idempotent and self-healing (re-running re-stamps the legacy score).

Seeds course `qa-legacy-score-course` (item 1 = quiz `qa-legacy-score-quiz-form`, item 2 = topic
`qa-legacy-score-topic`), quiz pass mark 80 / `quiz_show_incorrect=True`, Q1 `checkboxes` 3 opts /
2 correct, Q2 `multiple_choice` 3 opts / 1 correct. Cohort *QA Legacy Score Discrepancy Cohort*
registered for the course, 3 members (all password == email):
`demodev_legacyscore@email.com` (legacy attempt), `demodev_legacyscore_current@email.com`
(honest attempt, stored == recomputed), `demodev_legacyscore_idle@email.com` (no activity).

## How to craft a "stored score disagrees" attempt

`FormProgress.complete()` always scores with **today's** rule, so there is no UI or factory route to
a stale score. Recipe: create the answers (checkbox answer = *every* option), call `complete()`,
then overwrite with `FormProgress.objects.filter(pk=...).update(scores={...})` — `update()` not
`save()`, so nothing rescores, the completion hook cannot re-fire and `last_updated_time`
(`auto_now`) is left alone. The pre-fix rule was "any correct option selected counts as correct".

Result with this fixture: stored `{"score": 2, "max_score": 2}` = 100% → PASS; exact-match
recompute = 1/2 = 50% → FAIL.

## What each surface then shows (verified)

- Results page `/courses/qa-legacy-score-course/1/complete`: "Quiz passed!" + 100% ring (both read
  the **stored** `scores` via `passed()` / `quiz_percentage()`) **and** "Review incorrect answers"
  listing Q1 (`get_incorrect_quiz_answers()` recomputes with `is_quiz_answer_correct`).
- Cohort report (`gather_cohort_report_data`): summary-table cell 2/2 100% PASS from stored scores;
  the same learner's *Wrong answers* detail lists Q1 with the three selected options; the confusion
  block counts it wrong for 1 of 2 first-attempt respondents. `reports/partials/methodology.html`
  already carries the sentence explaining the discrepancy. PDF renders fine (~260 KB).

## Re-verified 2026-08-17 for QA 2.11 (report generation)

Requested a second time (first for QA 12.6, then for the report-generation plan QA 2.11) — the
existing command needed **no changes**; just re-run it. It does not touch the
`qa_create_report_fixtures` matrix, so it is safe to run after `--reset` of those.

Current values on DemoDev (site id 3): cohort uuid `831ca50d-6e8a-4841-a87f-f43a5ae85c57`,
FormProgress `8ee2cf10-34f5-4e73-ad7e-a175e168cf1e`.

Still correct after the report redesign (`dc439f86`): the rendered PDF (~371 KB, 9 pages) shows
the learner's QUIZ ATTEMPTS row as `✓ 100% 2/2` with the
`INCORRECT ANSWERS — QA LEGACY CHECKBOX SCORE QUIZ` block listing Q1 immediately underneath.

### Gotchas when writing a verification script against this data

- `FormProgress.completed_time`, **not** `complete_time` (TopicProgress *does* use `complete_time`).
- `FormProgress.get_incorrect_quiz_answers()` returns a list of **dicts**
  (`question` / `learner_selected` / `correct_options`), not model objects.
- `gather.CourseSection` has `learner_rows` + `summary_tables` + `confusions_by_quiz`; the
  per-learner detail sections (with `wrong_answers`) hang off `CohortReportData.learners`, not off
  the course section. `SummaryRow.cells` is a positional list aligned to `SummaryTable.quizzes`.
- `gather_cohort_report_data(cohort_id, site_id, *, requested_by_name="")` — **two** positional args;
  passing a `Cohort` instance alone raises `TypeError`. DemoDev site_id is 3.
- `CohortMembership.user` (**not** `.learner`). `FormProgress.answers` is the `QuestionAnswer`
  related_name (not `question_answers`). `FormQuestion.question` holds the text (not
  `question_text`) and the option label is `QuestionOption.text`.
- `LearnerDetail.flags` (**not** `at_risk_flags`); `Form.quiz_pass_percentage` (not
  `pass_percentage` — that name only exists on `gather.QuizColumn`).
- `accounts.User` has **no** `get_full_name()`; the report uses its own name formatting.
- Smoke-testing the render without creating a `GeneratedReport` row: call
  `reports.render.build_report_html(data)` / `render_report_pdf(data)` directly.

## Re-verified 2026-08-17 (third request, QA 2.11 again)

Checked, did **not** rebuild — the leftover cohort was already correct, and still correct after the
later report commits (`714e730c` "Count a blank answer and a failed quiz honestly in the report",
`a1467d8f`, `be491470`). Gather output for cohort `831ca50d-…`: Lena Legacy summary cell
`latest_score=2 / latest_max_score=2 / latest_percentage=100 / passed=True / attempt_count=1`,
while her `LearnerDetail.wrong_answers` lists Q1 with all three options selected. Rendered PDF
371,594 bytes. Cari Current (exact-match control) has an empty `wrong_answers`.
**Lesson: inspect before re-running** — a "leftover from an earlier QA run" cohort is often still
valid, and re-running would have re-stamped identical data for nothing.
