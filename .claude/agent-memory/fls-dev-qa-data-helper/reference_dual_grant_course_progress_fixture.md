---
name: dual-grant-course-progress-fixture
description: Giving one learner TWO grants (cohort + individual) on one course so deactivating one falls through to the other; how the mint-on-registration signals behave outside a request
metadata:
  type: reference
---

## The request (better_course_progress_tracking branch, Aug 2026)

Cara Learner (`cohort.learner@example.com`, DemoDev/site 3) needed a cohort grant AND an
individual grant on the *same* course, so QA can deactivate one and watch course-progress
resolution fall through to the other. Two registrations only -- the `CourseProgress` rows
must be minted by the signals, never by hand.

## The shape

```python
site = Site.objects.get(name="DemoDev")
course = Course._base_manager.get(slug="functionality-demo-show-end-with-quiz")
CohortCourseRegistrationFactory(site=site, cohort=cohort, collection=course, is_active=True)
LearnerCourseRegistrationFactory(site=site, learner=learner, collection=course, is_active=True)
```

Both factories live in `freedom_ls/learner_management/factories.py`. Pass `site=` explicitly:
`SiteAwareFactory` reads the site off a thread-local *request*, and a shell script / management
command has none, so the field would come out NULL and trip NOT NULL.

## Why two rows can coexist

`CourseProgress` on this branch has TWO nullable grant FKs, `learner_registration` and
`cohort_registration`, and exactly one is set. The unique constraints are
`(learner_registration, learner)` and `(cohort_registration, learner)`; PostgreSQL treats NULLs
as distinct, so a cohort-granted row and an individually-granted row for the same
(learner, course) never collide. `ensure_course_progress_record` is idempotent on the
*registration*, not on (learner, course) -- "a second grant is a second enrolment".

A learner may hold several `Learner` rows (one per organisation). The cohort grant lands on the
Learner in the cohort's org; the individual grant lands on whichever Learner row you name. They
are different `learner_id`s, which is a second reason the two rows coexist happily.

## Signals DO fire from `manage.py shell` / a command

`freedom_ls/learner_progress/signals.py` mints on `post_save` of both registration models via
`transaction.on_commit`. Under autocommit (plain shell script, no wrapping `atomic`) the callback
runs immediately, so the records exist before the next statement. If you ever wrap the creation in
`transaction.atomic()` and then inspect inside the block, the rows will look missing -- inspect
after the block, or don't wrap.

Records come out `progress_percentage=0`, `started_at=None`, `completed_time=None`,
`site` copied from `learner.site` (not from the ambient site).

## GOTCHA: the cohort registration fans out to the whole cohort

`ensure_course_progress_records_for_cohort_registration` bulk-creates one record per *active*
member of the cohort. Registering a cohort to give ONE persona a grant also gives every other
member one. Count the memberships first and report the extra rows -- on this run "Year 9 Maths"
had 3 members, so one requested row came with 2 collateral ones. Harmless, but the QA tester will
see them in the educator progress table.

The individual registration additionally fires a `course.registered` webhook event (announce
happens only when `created=True`). No configured endpoints in dev, so it is silent.
