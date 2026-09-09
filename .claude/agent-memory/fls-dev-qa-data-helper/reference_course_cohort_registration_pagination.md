---
name: Educator course page — the two registration tables and their paginators
description: CourseCohortRegistrationDataTable paginates COHORTS not learners; DataTable.page_size is 5; qa_create_course_cohort_registrations; the CourseProgress fan-out that decides which cohort is safe to register
metadata:
  type: reference
---

## The trap: "add more learners so the table pages" is wrong

The educator course page
(`/educator/organisations/<org-slug>/courses/<course-pk>`,
`CourseInstanceView` in `freedom_ls/educator_interface/views.py`) renders two
`DataTablePanel`s:

| Panel | title | rows are | filter |
|---|---|---|---|
| `CourseCohortRegistrationsPanel` | "Cohort Registrations" | `CohortCourseRegistration` — **one row per registered cohort** | `{"course": instance}` only |
| `CourseLearnerRegistrationsPanel` | "Direct Registrations" | `LearnerCourseRegistration` | `{"course": instance}` + `learner__organisation=request.organisation` in `get_queryset` |

**A cohort of 500 learners is still ONE row** in the cohort table. Its columns are
Cohort / Active / Registered — no learner is rendered at all. So paging it needs
many *cohorts registered to the course*, never more members in one cohort. A QA
plan phrased as "add enough learners to the cohort that the table pages" is
describing the cohort *progress* panel, not this one — say so before seeding.

Note the cohort table does **not** filter by organisation (the learner one does),
so a cohort from any organisation on the site appears. Keep new cohorts in the
org whose slug is in the URL anyway, or the row's `cohorts/{cohort.pk}` link 404s.

## Page size lives on the base class

`freedom_ls/panel_framework/tables.py` — `DataTable.page_size = 5`. Neither
registration table overrides it, so **both are 5**. This is a different family
from the course-*progress* panel's own `COLUMN_PAGE_SIZE = 15` /
`LEARNER_PAGE_SIZE = 20` (see [[reference_course_progress_pagination]]) — do not
carry a number across from that note. Read it off the class:
`CourseCohortRegistrationDataTable.page_size`.

`DataTable.get_rows()` also only renders a search box when `search_fields` is
non-empty; neither registration table sets it.

## Which cohort is safe to register — the CourseProgress fan-out

`post_save` on `CohortCourseRegistration` calls
`ensure_course_progress_records_for_cohort_registration`, which bulk-creates one
`CourseProgress` per **active member** of the cohort. Registering a cohort to make
a *table* page therefore writes a progress row for every one of its members, which
puts that course on each of their dashboards.

DemoDev cohort inventory (Sep 2026):

- `Cohort 2025.03.04` — 50 members, **includes `demodev_s1@email.com`**. Never
  register this one when the brief protects demodev_s1's progress/recommendations.
- `QA Pagination Cohort` — 32 members, all `qa_pagmatrix_learner_NN@example.com`.
  Safe, and gives one registration that clicks through to something populated.
- `Cohort 2025.04.06` — 0 members. Zero fan-out.

Pad with **empty** cohorts. They render identically in this table and touch no
progress row.

## The command

`freedom_ls/qa_helpers/management/commands/qa_create_course_cohort_registrations.py`

```
uv run python manage.py qa_create_course_cohort_registrations \
    [--site-name DemoDev] [--organisation-slug demodev] \
    [--course-slug functionality-demo-show-end-with-topic] \
    [--num-registrations 8] [--name-prefix "QA Course Reg Cohort"] \
    [--reuse-cohort NAME ...]
```

Registers each `--reuse-cohort` then pads with zero-padded empty
`QA Course Reg Cohort NN` cohorts until the course has `--num-registrations`
rows. Refuses a count `<= page_size`. Idempotent on
`unique_cohort_course_registration` and `unique_cohort_name_per_organisation`.
Prints the rows in table order with the page breaks marked, and the
before/after `CourseProgress` count so the fan-out is never silent.

Default result on DemoDev: 8 rows / 2 pages, boundary falling inside the padded
block (…Cohort 04 | Cohort 05…) so both sides are identifiable — the
zero-padding + straddle habit from [[reference_org_cohort_inline_pagination]].

## Field names that bit

- `CohortMembership` has **no `is_active`** field (only `cohort`, `learner`,
  `site`, timestamps). The activeness that gates the fan-out is `Learner.is_active`.
- `CohortCourseRegistrationFactory` takes **`course=`**, not `collection=`.
  (An older note in [[reference_dual_grant_course_progress_fixture]] says
  `collection=` — that is stale.)
- `Organisation` lives in `freedom_ls.organisations.models`, not
  `freedom_ls.learner_management.models`.

## Verifying a DataTable paginator headlessly

`get_queryset` uses the site-aware `objects` manager and
`CourseLearnerRegistrationDataTable.get_queryset` reads `request.organisation`,
so build a `RequestFactory` request with `HTTP_HOST=site.domain` and
`req.organisation = org`, assign it to
`freedom_ls.site_aware_models.models._thread_locals.request`, then walk
`table.get_rows(req, table._prepare_columns(), filters={"course": course})`
page by page and assert the concatenation equals the flat queryset.
`delattr(_thread_locals, "request")` in a `finally`.

## The sibling table: `qa_create_direct_course_registrations`

Asked for as the follow-up the same day. "Direct Registrations" is fed by
`LearnerCourseRegistration` — **individual grants only**. A cohort registration
mints a `CourseProgress` per member but creates no `LearnerCourseRegistration`,
so seeding the cohort table does nothing for this one. They are genuinely
independent records, which is the point of the two-paginator check.

`freedom_ls/qa_helpers/management/commands/qa_create_direct_course_registrations.py`

```
uv run python manage.py qa_create_direct_course_registrations [DemoDev] \
    [--course-slug ...] [--num-rows 8] [--email-prefix qa_directreg]
```

Target-driven on the whole table's row count, so pre-existing personas count
towards `--num-rows` and are never rewritten. It imports `_get_site` /
`_get_or_create_user` / `_register` from `qa_create_dashboard_paging_fixtures`.

**The ordering key is `first_name` then `last_name` — NOT the email.** Naming
the scaffolding learners `qa_directreg_01@example.com` upward does nothing for
the table order on its own; the email is just a column. Give them one shared
`first_name` and a zero-padded `last_name` and the order follows. (The same trap
will apply to any DataTable whose `order_by` differs from the identifier the
brief names.)

Result on DemoDev, `functionality-demo-show-end-with-topic`: 2 -> 8 rows,
2 pages, boundary between `QA DirectReg 03` and `04` — inside the padded block.
Page 1 keeps the two pre-existing personas: PostgreSQL's collation sorts
`DemoDev` < `demodev_s1` < `QA DirectReg`, so the fixtures land after them.
