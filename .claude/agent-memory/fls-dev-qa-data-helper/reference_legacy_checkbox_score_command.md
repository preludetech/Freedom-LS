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
  the same student's *Wrong answers* detail lists Q1 with the three selected options; the confusion
  block counts it wrong for 1 of 2 first-attempt respondents. `reports/partials/methodology.html`
  already carries the sentence explaining the discrepancy. PDF renders fine (~260 KB).
