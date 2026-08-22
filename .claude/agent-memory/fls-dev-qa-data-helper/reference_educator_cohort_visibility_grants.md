---
name: reference-educator-cohort-visibility-grants
description: A QA educator only sees cohorts they hold a guardian view_cohort grant on — qa_create_large_cohort / qa_create_empty_learner_cohort grant NOTHING, so their cohorts are invisible in /educator/ until you assign_perm
metadata:
  type: reference
---

`CohortDataTable.get_queryset` -> `learner_management.queries.cohorts_visible_to(user, organisation)`:

- If the user has `freedom_ls_organisations.view_organisation` on the current
  organisation -> EVERY cohort in that org.
- Otherwise -> only cohorts with a guardian `view_cohort` object grant.

Consequence for QA seeding: only `qa_create_cohort_progress` assigns
`view_cohort` (to `qa-educator-progress@example.com`, password `testpass123`).
`qa_create_large_cohort` and `qa_create_empty_learner_cohort` create cohorts in
the site's DEFAULT organisation with NO grants, so the educator lands on
`/educator/` and cannot see them — the tester reports "the cohort wasn't
created". Fix (data only):

```python
from guardian.shortcuts import assign_perm
assign_perm("view_cohort", educator, cohort)
```

after running those two commands. Superusers (`demodev@email.com`) see
everything and mask the problem.

Pagination: rows are `CohortMembership` @ 20/page, so `QA Large Cohort`
(25 members) is the one that renders the "Learners 1-20 of 25" line.
See [[reference_course_progress_pagination]].
