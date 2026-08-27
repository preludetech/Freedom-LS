---
name: seeding-form-attempts-around-the-formprogress-site-bug
description: How to seed completed, scored, answered course form sittings when CourseFormAttemptFactory's FormProgress sub-factory drops site= (the qa_complete_form / qa_create_report_cohort IntegrityError)
metadata:
  type: reference
---

## The bug (better_course_progress_tracking branch, Aug 2026)

> **FIXED as of commit 2c2b5e35** — `CourseFormAttemptFactory.form_progress` /
> `.collection_item` and `TopicProgressFactory.collection_item` now carry
> `site=factory.SelfAttribute("..site")`, so an explicit `site=` reaches the nested rows.
> Re-verified from a management command (site 2 / Demo) in Aug 2026. The workaround below
> still works and does no harm, but is no longer required on this branch.

`qa_complete_form` and `qa_create_report_cohort` both die with

```
null value in column "site_id" of relation "freedom_ls_form_engine_formprogress"
```

`CourseFormAttemptFactory` (`freedom_ls/learner_progress/factories.py:70`) takes `site=` for
its own row but its `form_progress = factory.SubFactory(FormProgressFactory, form=..., user=...)`
never forwards it, so `SiteAwareFactory.site` falls back to the thread-local request — absent in a
management command — and inserts NULL.

## The one-line workaround (no product change)

factory_boy's double-underscore param passing reaches the sub-factory:

```python
CourseFormAttemptFactory(
    course_progress=record,
    form=form,
    collection_item=placement,
    site=site,
    form_progress__site=site,   # <-- the whole fix
)
```

Same trick works for any SiteAwareFactory whose SubFactory forgets `site=`.

## Shape of a realistic completed sitting

1. `CourseFormAttemptFactory(...)` as above -> creates the join row + an empty `FormProgress`.
2. `QuestionAnswerFactory(form_progress=fp, question=q, site=site)` per question, then
   `answer.selected_options.set([option])`. Pass real objects so no SubFactory fires.
3. `fp.complete()` — scores via the form's own strategy AND sends `form_attempt_completed`,
   which `learner_progress.signals.recalculate_course_progress_on_form_attempt` turns into a
   recalculation of *that attempt's* `course_progress` (it looks the record up through
   `CourseFormAttempt.objects.filter(form_progress=attempt)`, so the per-grant record is exact —
   no `update_or_create` on (user, course) any more).
4. Then stamp `fp.completed_time = now - timedelta(hours=i)` and `fp.save()` (`complete()`
   early-returns once completed_time is set, so it must be stamped *after*).

Never hand-write the `scores` dict; `complete()` writes the shape the strategy really produces.

## Routing an attempt through the COHORT grant specifically

`reports/indexes.py` reaches attempts through
`course_attempt__course_progress__cohort_registration`, so a sitting hung off an *individual*
grant is invisible to a cohort report by design. Select the record explicitly:

```python
CourseProgress._base_manager.get(learner=membership.learner, cohort_registration_id=REG_PK)
```

Do NOT use `course_progress_for(user, course)` for this — it resolves cohort-beats-individual and
will silently pick the other grant for a dual-granted learner.

## DemoDev `knowledge-check` facts

3 single-select `multiple_choice` questions, one correct option each, `quiz_pass_percentage=80`.
max_score is 3, so **only 3/3 (100%) passes**; 2/3 = 67% and 1/3 = 33% both fail. A failing quiz
attempt does not count the placement as complete, so it moves no percentage.

## GOTCHA: `recalculate_progress_percentages` will surface unrelated drift

`functionality-demo-course-parts` had a SECOND Knowledge Check placement
(`e6b8fd18-...`, order=3) added by the tester, taking its completable placements from 7 to 8.
Every stored percentage computed under the old denominator was stale, so the recalculation
rewrote 8 records DB-wide (2 in the target cohort, 6 in `QA Progress Demo Cohort`:
14->12, 43->38, 43->38, 71->62, 86->75, 100->88). One of them (`qa-report-learner-08`) jumped
0 -> 50 because its 4 completed TopicProgress rows had never triggered a recalculation.

Lesson: before running `recalculate_progress_percentages`, snapshot the percentages of every
record for the affected course, not just the ones you touched, and re-run it afterwards to prove
`updated 0`. Report the collateral moves — a tester who chose a fixture for its 0% display will
otherwise think you broke it.

See [[reference_qa_complete_form_now_recalculates]] and [[reference_dual_grant_course_progress_fixture]].
