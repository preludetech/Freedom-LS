---
name: detaching-a-cohort-membership
description: Deleting one CohortMembership to force grant resolution to fall through to the individual registration; why the cohort-granted CourseProgress survives and what that means for the tester
metadata:
  type: reference
---

## The request (better_course_progress_tracking, Aug 2026)

`qa-report-learner-demodev-01@email.com` held BOTH grants on `functionality-demo-course-parts`
(the [[reference_dual_grant_course_progress_fixture]] shape). QA wanted them to stop resolving
through the cohort route, so exactly one `CohortMembership` row had to go.
`CohortMembership` is **not registered in the Django admin** as a standalone ModelAdmin — it is
only a `TabularInline` on `CohortAdmin` (`freedom_ls/learner_management/admin.py:152`), so a
pk-targeted delete has to happen from the shell.

## The delete is safe and cascades to NOTHING

```python
CohortMembership.objects.filter(pk=MEM_PK).delete()
# -> (1, {'freedom_ls_learner_management.CohortMembership': 1})
```

`CohortMembership._meta.get_fields()` yields **no reverse relations at all** — no model FKs to it.
Its own two FKs (`cohort`, `learner`) point outward. So there is no `ProtectedError` risk and no
cascade. Introspecting reverse rels first is the cheap way to prove that before deleting.

## No post_delete receiver exists, deliberately

`freedom_ls/learner_progress/signals.py` carries an explicit comment: *"There is deliberately no
post_delete counterpart: removing a membership, withdrawing a registration and deactivating a
learner are access decisions, and none of them retires work already recorded."*
So the cohort-granted `CourseProgress` (and its `CourseFormAttempt` / `FormProgress`) **survive**
the membership delete untouched. That is the product's intent, not a leak.

`CourseProgress.clean()` guards the membership check with `self._state.adding`, precisely so an
ex-member's surviving record stays saveable.

## What actually changes: the resolver join

`freedom_ls/learner_progress/queries.py` resolves the winning grant with

```python
CohortCourseRegistration.objects.filter(
    collection_id__in=course_ids,
    cohort__cohortmembership__learner__user=user,
    cohort__cohortmembership__learner__is_active=True,
    is_active=True,
)
```

A cohort grant beats an individual one, but only via a live `CohortMembership` join. Drop the
membership and the cohort row stops matching, so `LearnerCourseRegistration` wins and the learner
resolves to the individually-granted `CourseProgress`.

**Tell the tester both rows still exist.** Deleting the membership does not delete the cohort-granted
progress row; it only makes it unreachable through resolution. It stays visible in the admin and in
raw counts, and the educator cohort-progress table drops the learner because that table iterates
`CohortMembership`, not `CourseProgress`.

## Method that worked

`transaction.atomic()` + `delete()` + assert `total == 1` and the per-model dict has exactly the one
key, raising (and so rolling back) otherwise. Cheap insurance against a mis-typed filter, and it
prints the cascade counts the report needs. A dev server running against the DB is irrelevant —
no restart needed.
