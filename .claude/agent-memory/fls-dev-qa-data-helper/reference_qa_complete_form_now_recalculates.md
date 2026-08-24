---
name: reference-qa-complete-form-now-recalculates
description: qa_complete_form DOES fire a course-progress recalculation on this branch (it calls complete()); why the resulting percentages still don't move, and how to actually detect the write
metadata:
  type: reference
---

## The B4 QA assertion, and why it is not the test it looks like

QA plan asked: prove `qa_complete_form` "fires no recalculation" by checking that no
`CourseProgress.progress_percentage` moves. It doesn't move — but **a recalculation
DOES fire**. The percentage-only check cannot see it.

## What actually happens now

Commit `7a78c4f6` changed the command's create path from
`FormProgressFactory(..., completed_time=now - timedelta(hours=i))` (a plain factory
write: no `complete()`, no signal, genuinely no recalculation) to:

```
progress = FormProgress.objects.create(form=form, user=user, site=site)
progress.complete()                    # <-- sends form_attempt_completed
progress.completed_time = now - timedelta(hours=i)
progress.save()                        # plain save, does NOT re-send
```

`FormProgress.complete()` (`form_engine/models.py`) ends with
`form_attempt_completed.send(...)`. `learner_progress/signals.py`
`recalculate_course_progress_on_form_attempt` receives it and calls
`update_course_progress_on_completion`, which ends in
`CourseProgress.objects.update_or_create(user=..., course=..., defaults={"progress_percentage": ...})`.
So one CourseProgress **write** per created row. Note `update_or_create` will CREATE a
CourseProgress row for a learner who had none — a real side effect on any course
containing the form.

## Why the percentage still doesn't move

`qa_complete_form` submits NO answers, so `complete()` scores `{'score': 0, 'max_score': N}`.
`form_engine/queries.attempt_completes_form` says a **scored QUIZ with a non-null
`quiz_pass_percentage` only counts as done if the attempt PASSED**. 0/6 against
`end-course-quiz`'s pass mark of 50 is a fail, so the form is not a completed item and
the recomputed percentage equals the old one. Same reason
`recalculate_progress_percentages` reports `updated 0` right after the command.

Corollary for fixture-building: **`qa_complete_form` on a scored quiz does NOT advance
course progress.** It makes the learner *look* like they sat the quiz (row exists,
completed_time set) while the TOC/percentage still treat the item as unfinished. For a
quiz that should count, seed a passing attempt (see
[[reference_rich_dashboard_learner_command]]), or use a survey/unscored form.

## How to actually detect the write (the discriminating check)

`CourseProgress.last_accessed_time` is `auto_now=True`, so any save stamps it. After the
run, the 6 touched learners had `last_accessed_time` == the command's run instant, while
the 3 skipped learners still carried their old value. That is the check to use when a QA
plan asks "did anything recalculate?" — percentages alone are a false negative.

## Second trap: "already has a row" != "already completed"

The skip is `FormProgress.objects.filter(form=..., user=..., site=...).exists()` —
existence, not completion. In `QA Progress Demo Cohort` (9 learners) only ivy had a
*completed* row, but grace and hank each had an `end-course-quiz` row with
`completed_time=None` (an abandoned attempt), so **6, not 8, were created**. When
reporting a BEFORE table, print row-exists and completed_time as SEPARATE columns;
printing `completed_time` alone reads as "no row" and makes the created-count look wrong.
The staggered `now - timedelta(hours=i)` timestamps are also a free audit trail: `i` is
the *membership* index, so gaps in the hour sequence tell you exactly who was skipped.

## Live-tester interference

While auditing, `demodev_quizqa@email.com`'s FormProgress count went 1 -> 2 between two
snapshots. That was the QA tester walking the app in the browser at that moment, not a
command. Before reporting a count change as a bug, check `start_time` against wall clock
and against which commands could even reach that user (`qa_complete_form` is
cohort-scoped, and quizqa has no memberships — see [[reference_qa_command_site_arg_styles]]).

See [[reference_form_engine_branch_qa_baseline]] for the branch's baseline recipe.
