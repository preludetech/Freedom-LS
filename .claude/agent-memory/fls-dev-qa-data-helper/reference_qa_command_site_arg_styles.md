---
name: reference-qa-command-site-arg-styles
description: Which qa_ commands take the site as a POSITIONAL arg vs a --site-name option, plus the required-option surprises; saves a failed run every time a QA plan lists them all as "cmd DemoDev"
metadata:
  type: reference
---

The `qa_*` commands are NOT consistent about how the site is passed. QA plans
routinely write `qa_x DemoDev` for all of them; two of the popular ones then
exit 2 with `Error: Got unexpected extra argument (DemoDev)`.

POSITIONAL `SITE_NAME` (`@click.argument("site_name")`):
`qa_create_cohort_progress` (required), `qa_create_large_cohort` (required),
`qa_create_empty_learner_cohort` (required), `qa_create_deadline_overrides`
(required), `qa_create_soft_deadline` (required), `qa_create_course_visibility`
(default DemoDev), `qa_create_course_access_types` (default DemoDev),
`qa_create_rich_dashboard_learner` (default DemoDev),
`qa_create_course_player_learner` (default DemoDev),
`qa_create_course_detail_variants` (default DemoDev),
`qa_add_course_items_for_pagination` (required).

`--site-name` OPTION (no positional accepted):
`qa_create_organisation_scenarios`, `qa_create_password_reset_learner`.

Required-option surprises:
- `qa_create_empty_learner_cohort` REQUIRES `--course-slug` (repeatable). Bare
  `qa_create_empty_learner_cohort DemoDev` exits 2 with
  `Error: Missing option '--course-slug'.` Use
  `--course-slug functionality-demo-course-parts`.
- `qa_create_deadline_overrides` requires `--cohort-name`, `--course-slug`,
  `--learner-email` (the flag IS `--learner-email` post-rename), and the learner
  must ALREADY be a `CohortMembership` of that cohort, else
  `Error: Learner '<email>' is not a member of cohort '<name>'.`
  Add the membership first with `CohortMembershipFactory(cohort=..., user=...,
  site=...)`.
- `qa_create_large_cohort` takes `--course-slug` (repeatable, OPTIONAL); without
  it the cohort has 25 learners but zero course registrations, so the educator
  course-progress matrix has nothing to show.

Cohort defaults: `QA Progress Demo Cohort` (9 learners),
`QA Large Cohort` (25 learners, paginates at 20/page),
`QA Empty Learners Cohort` (0 learners).
