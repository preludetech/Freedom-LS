---
name: reference-clearing-form-sittings-around-an-application
description: Clearing a persona's stale FormProgress rows so every form start screen reads "Start Form" WITHOUT tripping the RESTRICT that a live CourseApplication holds on its own sitting; plus the self-registration shape for free courses
metadata:
  type: reference
---

Asked on `simple-application-forms`, Sep 2026, for `qa_applicant@email.com` (pk 73), site
DemoDev (**id 3, domain `127.0.0.1:8324`**). Two jobs in one pass: clear the QA-run form
residue, then enrol the persona in three free courses.

## The start-screen button is decided by `FormProgress` ALONE

`learner_interface/utils.py::form_start_page_buttons(form, incomplete_form_progress,
completed_form_progress, is_last_item)` looks at nothing else:

- an incomplete sitting -> "Continue Form"
- a completed sitting whose `quiz_verdict(...) is False` -> "Try Again"
- otherwise completed -> "Next" / "Finish Course"
- no sitting -> "Start Form"

`CourseFormAttempt` never enters it. So "make the placement read Start Form" is exactly
"delete the learner's `FormProgress` for that form" — deleting the join row alone would do
nothing, and there may not even be one (see below).

## `qa_reset_learner_progress` is now UNSAFE as a blunt tool on this branch

Run without `--course-slug` it does `FormProgress.objects.filter(user=...).delete()` across
every course. `CourseApplication.form_progress` is **RESTRICT**, so the moment a persona holds
a submitted application the whole reset aborts with `RestrictedError` (it fails safe, but it
fails). For an applicant persona, delete an explicit **pk list** and assert
`not CourseApplication._base_manager.filter(form_progress=fp).exists()` on each one.

RESTRICT vs PROTECT here is deliberate and documented on the model: deleting the *applicant*
must still take application + sitting away together, but the sitting can never be removed on
its own while the application stands.

## A duplicate "Application form" sitting is usually ORPHANED, not a second application

The ask assumed the older `Application form` sitting might still be referenced and that a stale
`CourseApplication` would have to go first. It was not: the apply flow re-mints a sitting and
re-points the one application at the new one (`unique_application_per_site_user_course` allows
only one row per user+course anyway). **Query before assuming a chained delete** —
`CourseApplication._base_manager.filter(form_progress=fp)` came back empty and no application
had to be touched. The `Collector` confirms it: no `CourseApplication` appeared in `c.data`.

## Blast radius of one `FormProgress.delete()`

```
survey, never answered : (1, {FormProgress: 1})
quiz, 3 answers        : (7, {QuestionAnswer_selected_options: 3, QuestionAnswer: 3, FormProgress: 1})
application, 4 answers : (7, {QuestionAnswer_selected_options: 1, QuestionAnswerFile: 1,
                              QuestionAnswer: 4, FormProgress: 1})
```

`QuestionAnswerFile` has a `post_delete` receiver
(`form_engine/receivers.py::delete_question_answer_file`) that calls `instance.file.delete()`.
Because it *has* a receiver Django cannot fast-delete it, so it shows up in `c.data` and the
stored object really is swept — verify with `af.file.storage.exists(af.file.name)` before and
after (`user_uploads/<user pk>/form_answers/<answer-file pk>.<ext>`). Grab the storage key
*before* the delete; afterwards there is no row to ask.

## No `CourseProgress` => no `CourseFormAttempt`, so "delete the join rows too" can be a no-op

This persona had 4 `FormProgress` rows and **zero** `CourseFormAttempt`, because
`CourseFormAttempt.course_progress` is non-null and the persona held no registration and
therefore no `CourseProgress` at all. Check both directions before reporting
(`form_progress__user=` and `course_progress__learner__user=`) and say plainly that the count
was already 0 — a QA plan naming rows to delete is describing what it saw in the admin, not a
guarantee they exist.

## The "ordinary self-registration shape" for a free course

`learner_interface/views.py::initiate_course_access` is the only self-service path, and it does:

```python
learner = ensure_learner(user, get_default_organisation(site))
LearnerCourseRegistration.objects.update_or_create(
    learner=learner, course=course, defaults={"is_active": True})
```

Reproduce it with `LearnerFactory(user=..., organisation=get_default_organisation(site), site=site)`
(it delegates to `ensure_learner`) + `LearnerCourseRegistrationFactory(learner=..., course=...,
site=site, is_active=True)`. Explicit `site=` on both — `SiteAwareFactory`'s site LazyFunction
returns None outside a request. The default organisation on DemoDev is named `DemoDev`
(`Organisation._base_manager.get(site=site, is_default=True)`), and the persona's existing
`Learner` row is already in it, so `LearnerFactory` returns that row rather than a second one.

The `post_save` receiver mints one `CourseProgress` per registration at
`progress_percentage=0`, `learner_registration=<reg>`, `cohort_registration=None`. It fires on
`transaction.on_commit`, which in `manage.py shell` (autocommit) runs immediately. It also
announces `course.registered`; check `WebhookEndpoint._base_manager.filter(site=..., is_active=True)`
first (0 on DemoDev) so nothing fires at an endpoint mid-QA.
