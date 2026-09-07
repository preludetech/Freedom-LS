---
name: standalone-course-less-form-sitting
description: qa_create_standalone_form_sitting — the only FormProgress in the dev DB with no CourseFormAttempt, so FormProgressAdmin's "In course" empty-value dash is browser-reachable
metadata:
  type: reference
---

`uv run python manage.py qa_create_standalone_form_sitting [--site-name DemoDev]
[--email ...] [--form-slug ...]`
Command: `freedom_ls/qa_helpers/management/commands/qa_create_standalone_form_sitting.py`.
Idempotent (reuses any existing course-less sitting of the same user+form).

## Why it exists

`FormProgressAdmin.in_course` (`freedom_ls/form_engine/admin.py:253`) reads the reverse
one-to-one `FormProgress.course_attempt` and returns `None` when absent — the docstring says
the dash means "sat standalone", not "unknown". Every one of the dev DB's 406 FormProgress rows
was seeded through `CourseFormAttemptFactory`, which ALWAYS mints the join row, so the branch
had zero fixtures. Baseline before this command: 406 FormProgress / 406 CourseFormAttempt /
**0** standalone.

## The shape

A standalone sitting is not a special case in the model — it is simply
`FormProgressFactory(user=, form=, site=)` with **no** `CourseFormAttemptFactory` call.
`FormProgress` FKs `user` and `form` directly; the course link lives entirely in
`learner_progress.CourseFormAttempt`. Do NOT reach for `CourseFormAttemptFactory` and then
delete the join row.

Completing one is safe: `recalculate_course_progress_on_form_attempt`
(`learner_progress/signals.py:96`) does `CourseFormAttempt.objects.filter(form_progress=attempt)
.first()` and early-returns on `None`, so no `CourseProgress` percentage moves. Its docstring
explicitly names "a standalone survey, an application form" as the supported case.

## Seeded row (Sep 2026, misc-small-fixes-manual)

- pk `28ad0126-7247-42a6-874d-1f88d7d91996`, site DemoDev (3)
- user `qa-standalone-form@example.com` (created; password == email, verified EmailAddress)
- form `qa-form-first-form` / "QA Form First Form" (QUIZ), scores `{'score': 1, 'max_score': 1}`
- start_time / completed_time backdated 3h / 2h

## Gotchas

- `start_time` is `auto_now_add` and `complete()` stamps `completed_time = now()`, so backdating
  must be a post-save `FormProgress._base_manager.filter(pk=...).update(...)` +
  `refresh_from_db()`. Same pattern as `qa_create_report_cohort._sit`.
- Do NOT reuse `qa_create_form_question_types._get_learner` when the ask is "additive only": it
  **resets the password** of `demodev@email.com` and rewrites its `EmailAddress`. Write a
  non-mutating `_get_or_create_user` instead.
- Verifying the render: the naive "find the `<tr>` containing the email" regex matches the
  **header** row, because every column's sort link carries `?q=<the email>`. Anchor on
  `field-in_course` (data cells) instead of the search term. Confirmed render:
  standalone row `in_course == '-'`, the demodev row on the same form `== 'QA Form First Course'` —
  searching the changelist for `QA Form First Form` puts both side by side, which is the
  strongest single screenshot for this check.
