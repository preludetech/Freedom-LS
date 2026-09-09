---
name: reference-withdrawing-a-course-application
description: qa_reset_course_application — withdrawing a QA applicant's CourseApplication plus the FormProgress it named, in the RESTRICT-safe order, so the application-forms QA plan can be re-walked from §2
metadata:
  type: reference
---

`qa_reset_course_application --learner EMAIL --course-slug SLUG [--site-name DemoDev]`
(`freedom_ls/qa_helpers/management/commands/`). Deletes the learner's application to that
course, then the sitting that application named. Idempotent: no application -> prints
"No application to withdraw" and exits 0.

## This is QA-plan step §0.2.3, not a one-off

`spec_dd/2. in progress/simple-application-forms/3. frontend_qa.md` §0.2.3 says in so many
words: "On a second run of this plan the account from the first run already holds an
application and its form sitting: clear them in that order". §0.2.7 is the sibling ask for
the three free courses' `FormProgress` ([[reference_clearing_form_sittings_around_an_application]]).
So expect BOTH every time the plan is re-run, not just the first time.

## Order is forced by RESTRICT, and only the application end can be deferred

`CourseApplication.form_progress` is `OneToOneField(..., on_delete=RESTRICT)`. Application
first, sitting second, always. The command re-fetches the sitting **by pk after** the
application row is gone, which is also why it never has to reason about the RESTRICT itself.

Observed cascade for `qa_applicant@email.com` (pk 73) on the gated course, Sep 2026:

```
CourseApplication : (1, {CourseApplication: 1})            # zero cascade, nothing FKs to it
FormProgress      : (7, {QuestionAnswer_selected_options: 1, QuestionAnswerFile: 1,
                         QuestionAnswer: 4, FormProgress: 1})
```

`Collector.fast_deletes` also listed `CourseFormAttempt: 0` — an application sitting is
started outside the player, so it never has a join row even when the applicant has 8 of them
from other courses. Check `form_progress=` (0 here) rather than
`course_progress__learner__user=` (8 here) before reporting.

The `QuestionAnswerFile` post_delete receiver really does sweep storage: grab
`(pk, file.name, file.storage)` BEFORE the delete and assert `storage.exists(name)` flips
True -> False (`user_uploads/73/form_answers/<qaf pk>.png`).

## Field names that bite

- `FormProgress` has **no** `is_complete`; it is `completed_time` (nullable datetime).
- `QuestionAnswerFile`'s FK to the answer is **`answer`**, not `question_answer` — so the
  filter is `QuestionAnswerFile.objects.filter(answer__form_progress=fp)`.
- `CourseApplication.__str__` is `CourseApplication(<user pk>, <course pk>)` — two opaque
  ids, no email or slug, so always print `user.email` / `course.slug` alongside it or the
  "here is what I deleted" line is unreadable.

## A parallel worker's unmigrated model field will break every ORM read mid-session

Halfway through this run `FormProgress` SELECTs started failing with
`ProgrammingError: column ...furthest_page_reached does not exist` — another agent had added
a model field in the shared worktree without a migration. Do **not** write the migration
(it lands an unrequested file in someone else's in-progress diff) and do not bake a
`.only()`/`defer()` workaround into a committed command. Work around it *in the scratch
script only*:

```python
FormProgress._base_manager.only("id", "site", "form", "user", "completed_time").get(pk=...)
```

Re-check before assuming it is still broken: the same worker's migration landed ~20 minutes
later and the plain query started working again. `showmigrations` said everything was applied
both times — the mismatch is model-vs-DB, not migration-vs-DB, so `showmigrations` cannot see it.

## Testing a destructive command without spending the fixture

The target rows are gone by the time the command exists, so exercise it against a row that
must SURVIVE, inside `transaction.atomic()` + a raised sentinel. Per
[[reference_shell_savepoint_does_not_roll_back]] `transaction.atomic()` (not
`transaction.savepoint()`) genuinely rolls back in `manage.py shell`. This proved the
sitting-delete branch against `qa_bystander`'s live application and left it byte-identical.
Postgres DDL is transactional too, so a temporary `ALTER TABLE ... ADD COLUMN` inside the
same block rolls back — a legitimate way to test around a missing column, if it is still missing.
