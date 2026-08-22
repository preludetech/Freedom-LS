---
name: reference-column-pagination-scenario
description: qa_create_column_pagination_scenario — a dedicated cohort+course where BOTH course-progress paginators are live, without touching functionality-demo-course-parts
metadata:
  type: reference
---

`qa_create_column_pagination_scenario [SITE_NAME] [--num-learners 22]
[--target-item-count 18] [--educator-email ...]` (positional site, default DemoDev).
File: `freedom_ls/qa_helpers/management/commands/qa_create_column_pagination_scenario.py`.
Idempotent.

Builds:
- Course `qa-column-pagination-course` (published, free) with 3 seed topics, then
  delegates to `qa_add_course_items_for_pagination` (via `call_command`) to pad to 18
  flat items -> **2 column pages** at `COLUMN_PAGE_SIZE = 15`.
- Cohort `QA Column Pagination Cohort` with 22 learners
  (`qa_colpag_learner_{n}@example.com` / `testpass123`) -> **2 learner pages** at
  `LEARNER_PAGE_SIZE = 20`.
- Grants object-level `view_cohort` to `qa-educator-progress@example.com` and
  `demodev@email.com` (see [[reference_educator_cohort_visibility_grants]] — without a
  grant the cohort is invisible even though it exists).

## Why a dedicated course

The obvious move is `qa_add_course_items_for_pagination DemoDev` with its DEFAULT
`--course-slug functionality-demo-course-parts`. **Don't.** That course is the shared
subject of the course-player / resume / TOC / deadline fixtures (`demodev_s1` sits at 43%,
resume index 4), and padding it from 7 to 18 items recomputes every percentage and moves
the resume point. Always pass an explicit `--course-slug`.

Both paginators must be live *simultaneously* to test that paging columns preserves the
learner page: `course_progress_panel.html` line ~160 does
`{% join_query registration=selected_reg.pk page=learner_page.number as col_extra %}`.
A half-renamed variable there silently resets the learner paginator to page 1.

Constants live in `CohortCourseProgressPanel` (`freedom_ls/educator_interface/views.py`):
`COLUMN_PAGE_SIZE = 15`, `LEARNER_PAGE_SIZE = 20`. Columns = Topic + Form only;
CourseParts are excluded. See [[reference_course_progress_pagination]].

GOTCHA: `qa_add_course_items_for_pagination`'s own summary prints
`Item count: 3 -> 3` because `Course.viewable_items()` is memoized per instance. Re-query
`Course.objects.get(pk=...)` to get the true count (the orchestrator command does this and
reports 18).
