---
name: reference-learner-deadline-admin-fixtures
description: qa_create_learner_deadlines — the only fixture for the LearnerDeadline (individual registration) admin; which of the three deadline models each qa_ command actually writes, and the email-not-searchable trap
metadata:
  type: reference
---

## Three deadline models, three different qa_ commands

| Model | Hangs off | Seeded by |
|---|---|---|
| `CohortDeadline` | `CohortCourseRegistration` | `qa_create_soft_deadline` |
| `UserCohortDeadlineOverride` | `CohortCourseRegistration` + `user` | `qa_create_deadline_overrides` |
| `LearnerDeadline` | `UserCourseRegistration` (**field: `learner_course_registration`**) | `qa_create_learner_deadlines` (added Aug 2026) |

Testers repeatedly ask for "deadline overrides" and get `UserCohortDeadlineOverride`,
then find `LearnerDeadline.objects.count() == 0`. They are NOT interchangeable —
`qa_create_deadline_overrides` writes zero `LearnerDeadline` rows.

## `qa_create_learner_deadlines [SITE_NAME]` (positional, default DemoDev)

`freedom_ls/qa_helpers/management/commands/qa_create_learner_deadlines.py`. Idempotent
(matched on the unique `(learner_course_registration, content_type, object_id)` triple).

Seeds 7 rows: 4 for `demodev_s1@email.com`, 3 for `qa-eve.middle@example.com` (the latter
has a real first+last name, "Eve Middle"), across 3 courses (`functionality-demo-course-parts`,
`-show-end-with-topic`, `-show-end-with-quiz`), mixed hard/soft. Creates the missing
`UserCourseRegistration` rows via `UserCourseRegistrationFactory`; it never touches `User`
rows, so it cannot rotate a password or kill a tester's browser session.

All deadlines are FUTURE on purpose — an expired **hard** deadline marks the item BLOCKED
and makes the player redirect away from it, which would wreck concurrent course-player QA
on the same learner. See [[reference_learner_visible_deadlines]].

## TRAP — `LearnerDeadlineAdmin.search_fields` has no email

```
search_fields = [
    "learner_course_registration__user__first_name",
    "learner_course_registration__user__last_name",
    "learner_course_registration__collection__title",
]
```

No `__user__email`. `UserCourseRegistrationAdmin` (the autocomplete target) DOES have
`user__email`. So on the LearnerDeadline changelist, searching a full email returns 0 rows.
Verified pre-existing, not a rename regression: `git show f522ec06 -- freedom_ls/learner_management/admin.py`
shows the pre-rename list was the same three fields under `student_course_registration__`.

Searching the bare fragment `demodev_s1` DOES return rows — but only because that user's
`first_name` literally is `"demodev_s1"` (UserFactory derived it from the email), not because
email is searchable. Do not let a QA plan conclude "email search works".

`autocomplete_fields = ["learner_course_registration"]` -> `UserCourseRegistration` ->
`UserCourseRegistrationAdmin`, which has `search_fields` set, so the Add-form dropdown
populates. Django's admin.E040 system check would fail loudly otherwise, so a clean
`manage.py check` already proves the autocomplete target is valid.

Changelist URL: `/admin/freedom_ls_learner_management/learnerdeadline/`.

Verifying admin traversals without a browser: pull the ModelAdmin out of
`django.contrib.admin.site._registry[Model]` and call `get_search_results(request, qs, term)`
and `qs.select_related(*ma.list_select_related)` directly — this executes the exact string
paths and raises `FieldError` if a rename was missed.
