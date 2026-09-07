---
name: reference-org-cohort-inline-pagination
description: qa_create_org_cohort_pagination — padding one Organisation so the admin change page's Cohorts tab spans 3 pages; the admin-inline paginator family and how to verify a page walk headlessly
metadata:
  type: reference
---

`qa_create_org_cohort_pagination [--site-name DemoDev] [--organisation-slug demodev]
[--num-cohorts 30] [--name-prefix "QA Page Cohort"]`.
File: `freedom_ls/qa_helpers/management/commands/qa_create_org_cohort_pagination.py`.
Idempotent (matched on the model's own `(site, organisation, name)` constraint,
`unique_cohort_name_per_organisation`).

Creates bare `Cohort` rows via `CohortFactory(name=..., organisation=..., site=...)` --
**no members, no course registrations**. The inline renders only `name`, and empty
cohorts keep the fixture from moving any progress percentage or report the tester is
mid-assertion on. Cost of one row is exactly one row.

## The admin-inline paginator family (unfold `TabularInline`)

Distinct from the educator-interface paginators in
[[reference_course_progress_pagination]]. In `freedom_ls/learner_management/admin.py`:

| inline | model | `per_page` | `ordering` |
|---|---|---|---|
| `OrganisationCohortInline` | Cohort | 20 | `["name"]` |
| `OrganisationLearnerInline` | Learner | 25 | `["user__email"]` |

Both are contributed to `OrganisationAdmin.inlines` from `learner_management` (same seam
as `ORGANISATION_SUMMARIES`, see [[reference_organisation_admin_summary_counts]]).
Read `per_page` off the inline class in the command rather than hardcoding it, so the
reported page count cannot drift from the admin.

## Name the rows so the check under test cannot be faked

The ask is always "prove no row repeats and none is skipped across a page boundary".
**Zero-pad the numbers** (`QA Page Cohort 01`, not `1`): under `ordering = ["name"]` an
unpadded `10` sorts before `2`, which looks exactly like the skipped row the tester is
hunting for. Aim for the padding block to STRADDLE a boundary — here 46 rows page
20/20/6 and the 1->2 boundary falls at `QA Page Cohort 16` -> `17`, so both sides of the
first boundary are individually identifiable scaffolding.

## Verifying the walk headlessly

Don't eyeball the tab. Rebuild what the admin does and compare against the flat queryset:

```python
qs = Cohort.objects.filter(organisation=org).order_by(*OrganisationCohortInline.ordering)
p = Paginator(qs, OrganisationCohortInline.per_page)
seen = [c.name for n in p.page_range for c in p.page(n).object_list]
assert seen == [c.name for c in qs]      # nothing repeated, nothing skipped
assert len(set(seen)) == len(seen)
```

Do it under a thread-local request (`_thread_locals.request = RequestFactory().get("/admin/")`)
so `Cohort.objects` applies the ambient site filter the browser applies; `_base_manager`
sees every site and can disagree. Report both counts.

## State seeded Sep 2026

DemoDev organisation `bd37c908-ab4e-4836-966f-3e62dde6a0ab` (slug `demodev`, site id 3):
16 -> **46** cohorts, the 30 new ones `QA Page Cohort 01`..`30`, all site 3, all empty.
