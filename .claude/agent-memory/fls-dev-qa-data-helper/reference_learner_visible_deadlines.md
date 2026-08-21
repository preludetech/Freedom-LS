---
name: reference-learner-visible-deadlines
description: How to make a deadline actually render in the learner UI (which model, which template, and the course-level fallback trick that makes it visible without expanding CourseParts)
metadata:
  type: reference
---

# Making deadlines visible to a learner

## The only learner-facing render point

`student_interface/partials/course_minimal_toc.html`, `{% partialdef deadline-badges %}`
— a `<span class="text-xs text-warning ..." title="{{ dl.source }}">` (soft) or
`text-error` (hard) with a `deadline` icon and `{{ dl.deadline|date:"d M" }}`.

That partial is included from exactly two templates:

- `student_interface/course_detail.html` -> `/courses/<slug>/detail/`
  (only when `course.table_of_contents_in_development` is **False**)
- `student_interface/_course_base.html` (player sidebar) -> `/courses/<slug>/<index>/`

**The dashboard `/` renders NO deadlines** — it has no TOC. Don't look for them there.

## Data path

`get_course_index()` (`student_interface/utils.py`) fills `deadlines_map` via
`student_management.deadline_utils.get_course_deadlines(user, course)`, gated on
`user.is_authenticated and config.DEADLINES_ACTIVE`
(`freedom_ls/student_management/config.py`, default **True**, no project override).

Resolution per active registration:

- Cohort reg: `UserCohortDeadlineOverride` > `CohortDeadline` (item) >
  course-level override > course-level `CohortDeadline`
- Individual `UserCourseRegistration`: `StudentDeadline` item > `StudentDeadline` course-level

## KEY TRICK — use a course-level deadline for visibility

`_get_deadlines_for_item()` falls back to the `(None, None)` course-level entry
when an item has no item-level deadline. So **one course-level `CohortDeadline`
puts a badge on every TOC row, including the top-level CoursePart rows.**

This matters because CoursePart children live inside a collapsed
`<ul x-show="expanded">`: an *item-level* deadline on a topic/form nested in a
CoursePart is **invisible until the QA tester expands that part**. Always add the
course-level one too if the point is "prove deadlines render".

## Command — already exists, no code change needed

`freedom_ls/qa_helpers/management/commands/qa_create_soft_deadline.py` (djclick).
Idempotent (`update_or_create`-style on the unique constraint). Uses
`CohortDeadlineFactory`. Works for cohort registrations only.

```
uv run python manage.py qa_create_soft_deadline DemoDev \
  --cohort-name "Year 9 Maths" --course-slug functionality-demo-course-parts \
  --days-from-now 30                       # course-level, soft, future
uv run python manage.py qa_create_soft_deadline DemoDev \
  --cohort-name "Year 9 Maths" --course-slug functionality-demo-course-parts \
  --item-slug knowledge-check --days-from-now 14
```

`--days-from-now` is **negative by default (-7 = overdue)**. Pass a positive value
for an upcoming deadline. `--hard` flips to a hard deadline.

Caveat: it does `.get(cohort__name=..., collection__slug=..., site=...)`. Two orgs
on Site 3 both own a cohort named "Year 9 Maths", so this raises
`MultipleObjectsReturned` if both ever register the same course. Currently only
RPAS Training's does.

For an individual `UserCourseRegistration` there is **no** qa command — you'd need
`StudentDeadlineFactory(student_course_registration=reg, deadline=..., site=site)`.
`qa_create_deadline_overrides` covers `UserCohortDeadlineOverride`.

## Hard-deadline side effect

Expired **hard** deadlines set the row to `BLOCKED`, drop its URL, and
`view_course_item` redirects to `/detail/` (`student_interface/views.py`,
`is_item_locked_by_deadline`). Soft deadlines never lock. Use soft for
"deadlines render" checks so you don't disturb live progress QA.

## Verifying without a browser

`Client.login()` blows up under django-axes
(`AxesBackendRequestParameterRequired`). Use `client.force_login(user)` with
`Client(SERVER_NAME="127.0.0.1", SERVER_PORT="8000")`.
