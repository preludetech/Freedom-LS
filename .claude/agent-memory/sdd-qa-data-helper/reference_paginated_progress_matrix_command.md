---
name: reference-paginated-progress-matrix-command
description: qa_create_paginated_progress_matrix — org-owned "QA Pagination Cohort" with both course-progress paginators live AND a real progress spread; how to keep progress_percentage consistent when writing completions in bulk
metadata:
  type: reference
---

`qa_create_paginated_progress_matrix [SITE_NAME] [--organisation-slug rpas-training]
[--cohort-name "QA Pagination Cohort"] [--num-learners 32] [--target-item-count 26]
[--educator-email ...]` (positional site, default DemoDev). Idempotent.
File: `freedom_ls/qa_helpers/management/commands/qa_create_paginated_progress_matrix.py`.

Builds:
- Course `qa-pagination-matrix-course` (published, free), 26 topics split over
  **two dedicated CourseParts** (`qa-pagination-matrix-part-1/-2`) so the panel
  also renders part headers on both column pages -> 2 column pages at
  `COLUMN_PAGE_SIZE = 15`.
- Cohort **in a named organisation** (default RPAS Training), 32 learners
  `qa_pagmatrix_learner_01..32@example.com` / `testpass123` -> 2 learner pages
  at `LEARNER_PAGE_SIZE = 20`.
- Progress spread: first 6 members 0%, last 6 at 100%, the 20 between spaced
  evenly 4%..92%, each partway learner also getting one *started-not-completed*
  topic so in-progress cells render.
- Object-level `view_cohort` to `org.educator@example.com`.

## Difference from `qa_create_column_pagination_scenario`

That one is the minimal both-paginators pair (22 learners / 18 items) in the
site's **default** organisation, everyone at 0%. Use this one when the QA needs
an organisation-staff educator route (`/educator/organisations/<slug>/...`) or
real percentages in the matrix. It deliberately does NOT reuse
`qa_add_course_items_for_pagination`: that command's CoursePart slug
(`qa-pagination-test-section`) is a single global row, so attaching it to a
second course would drag all of the other course's padding topics along.

## GOTCHA — a TopicProgress created already-complete never recalculates

`CourseItemProgress.__init__` snapshots `_original_completion_value`, and
`newly_completed_item()` returns None when that snapshot is non-null. So
`TopicProgress(..., complete_time=now)` fires `post_save` but
`recalculate_course_progress_on_save` returns early: the owning
`CourseProgress.progress_percentage` stays at the registration's initial 0.
Any bulk-completion seeding must write the percentage itself. The command calls
`learner_management.utils.calculate_course_progress_percentage(course,
completed_topic_ids, completed_form_ids)` per record.

Prefer that targeted refresh over the global
`manage.py recalculate_progress_percentages`: the global command walks every
record in the install and would also rewrite fixtures that hold a deliberately
stale/discrepant value (e.g. `qa_create_legacy_checkbox_score`).

## Progress-record minting on this branch (`better_course_progress_tracking`)

`CourseProgress` is keyed on the granting registration
(`cohort_registration` / `learner_registration`, exactly one set). Records are
minted only by the three `post_save` receivers in
`freedom_ls/learner_progress/signals.py` (learner registration, cohort
registration fan-out, cohort membership catch-up), all via
`transaction.on_commit` — which runs immediately in an autocommit management
command, so creating the registration and then the memberships is enough; never
construct `CourseProgress` by hand. The matrix reads
`CourseProgress.objects.filter(learner=..., cohort_registration=selected_reg)`.

## URL

The educator interface is organisation-scoped:
`/educator/organisations/<org-slug>/cohorts/<cohort-uuid>/__tabs/course_progress`
(`course_progress` is the default tab). Paginator query params are `col_page`
(columns) and `page` (learners); they are independent. Older QA commands still
print the pre-organisation `/educator/cohorts/<pk>/...` path — that 404s.
