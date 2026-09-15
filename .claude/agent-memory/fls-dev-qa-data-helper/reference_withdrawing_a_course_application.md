---
name: reference-withdrawing-a-course-application
description: qa_reset_course_application — withdrawing a QA applicant's CourseApplication plus the FormProgress it named, in the RESTRICT-safe order, so an application-gated QA plan can be re-walked from scratch
metadata:
  type: reference
---

`qa_reset_course_application --learner EMAIL --course-slug SLUG [--site-name DemoDev] [--dry-run]`
(`freedom_ls/qa_helpers/management/commands/qa_reset_course_application.py`). Deletes the
learner's application to that course, then the sitting that application named. Idempotent: no
application -> "No application to withdraw" and exit 0.

## It gets RE-WRITTEN per worktree — check before assuming it exists

Written twice now (first on `simple-application-forms`, again on `form_engine_data_field`
Sep 2026). The first one **never merged**, and `git log --all --diff-filter=A` in the second
worktree found nothing. A memory note saying "this is a command" is not evidence the file is on
*this* branch — `ls freedom_ls/qa_helpers/management/commands/ | grep -i reset` first. Same
applies to any command these notes name. `qa_clear_form_sittings` *did* exist on both.

## This is a recurring QA-plan step, not a one-off

Every re-run of an application-gated plan needs it: the account from the previous run already
holds an application + sitting. Its sibling ask is §"clear the other courses' FormProgress"
([[reference_clearing_form_sittings_around_an_application]]). Expect BOTH together.

## Order is forced by RESTRICT — and so is the *preview*

`CourseApplication.form_progress` is `OneToOneField(on_delete=RESTRICT)`. Application first,
sitting second, always. The command re-fetches the sitting **by pk after** the application row
is gone, so it never reasons about the RESTRICT.

TRAP that cost a round-trip: building a `Collector` over the sitting to preview the blast radius
**raises `RestrictedError` itself** while the application still stands —

```
RestrictedError: Cannot delete some instances of model 'FormProgress' because they are
referenced through restricted foreign keys: 'CourseApplication.form_progress'.
```

It fails safe (nothing was deleted, the exception precedes the delete calls), but a
`Collector`-based preview simply cannot run in this order. Preview with direct `.count()`
queries instead, which is what the command does.

Observed cascades, Sep 2026 (`qa.applicant.a@email.com` pk 71, gated course, 12 answers):

```
CourseApplication : (1, {CourseApplication: 1})            # zero cascade, nothing FKs to it
FormProgress      : (17, {QuestionAnswer_selected_options: 3, QuestionAnswerFile: 1,
                          QuestionAnswer: 12, FormProgress: 1})
applicant B, 4 answers, never completed:
FormProgress      : (6, {QuestionAnswer_selected_options: 1, QuestionAnswer: 4, FormProgress: 1})
```

An application sitting is started **outside** the player, so it has no `CourseFormAttempt` even
when the persona has several from other courses. Check `form_progress=` rather than
`course_progress__learner__user=` before reporting.

The `QuestionAnswerFile` post_delete receiver really sweeps storage: grab
`(pk, file.name, file.storage)` BEFORE the delete and assert `storage.exists(name)` flips
True -> False (`user_uploads/71/form_answers/<qaf pk>.pdf`).

## Deleting the application does NOT touch course progress

`LearnerCourseRegistration`, `CourseProgress` and `TopicProgress` all survive untouched — worth
stating explicitly when the ask says "keep the registration so item N stays unlocked".

## Field names that bite

- `FormProgress` has **no** `is_complete`; it is `completed_time` (nullable datetime).
- `QuestionAnswerFile`'s FK to the answer is **`answer`**, not `question_answer` — the filter is
  `QuestionAnswerFile.objects.filter(answer__form_progress=fp)`.
- `CourseApplication` filters on **`user`**, not `applicant`, and has no `status` field.
- `CourseApplication.__str__` is `CourseApplication(<user pk>, <course pk>)` — two opaque ids, no
  email or slug, so always print `user.email` / `course.slug` alongside it.
- `FormQuestion`'s FK to its page is **`form_page`**, not `page`, and the type field is **`type`**,
  not `question_type`. `filter(page__form=form)` raises `FieldError` (choices: category,
  created_at, decimal_places, file_path, form_page, id, max, meta, min, options, order, question,
  required, site, tags, type). The text is in **`question`**.

## Testing a destructive command without spending the fixture

The target rows are gone by the time the command exists, so exercise it against a row that must
SURVIVE, inside `transaction.atomic()` + a raised sentinel ([[reference_shell_savepoint_does_not_roll_back]]).
Proved the delete branch against applicant B's live application and confirmed
`(pk, form_progress_id)` identical after rollback.

**djclick commands need CLI-style args through `call_command`**:
`call_command("qa_reset_course_application", "--learner", email, "--course-slug", slug)`.
Kwargs (`learner=..., course_slug=...`) raise `click.exceptions.MissingParameter: learner`,
because djclick's adapter builds a click context from `args` only.
