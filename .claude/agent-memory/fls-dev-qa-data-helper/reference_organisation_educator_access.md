---
name: reference-organisation-educator-access
description: How a persona gets into the organisation-scoped educator interface — the two independent access paths, why "no ObjectRoleAssignment" does NOT mean "no access", and where cohort reports actually live
metadata:
  type: reference
---

## The two access paths are independent — check BOTH before believing a gap

`organisations_accessible_to` = orgs with a guardian `view_organisation`
**union** orgs owning any cohort the user holds a guardian `view_cohort` on.
`cohorts_visible_to(user, org)` returns *every* cohort in the org for a
`view_organisation` holder, otherwise only the `view_cohort`-granted ones.

So a QA plan that reports "persona has no ObjectRoleAssignment for org X, the
step is blocked" is often **wrong**: a bare `assign_perm("view_cohort", ...)`
on one cohort (which several qa_ commands do, with no ORA row at all) already
opens `/educator/organisations/<slug>/cohorts/<uuid>` for that one cohort.
Verified empirically Aug 2026 for `org.educator@example.com` on DemoDev: with
an added `organisation_staff` role deleted inside a rolled-back atomic block,
the cohort page still returned 200 — the role only widened her cohort list
from 1 to 4. Always run that counterfactual before reporting "this unblocked
the step".

## If a persona really does need organisation_staff

There is no standalone command for it, deliberately — the one written for the
false diagnosis above was deleted. Grant it inline the way
`qa_create_organisation_scenarios` does: `assign_object_role(user, org,
"organisation_staff")` from `role_based_permissions.utils`, inside that
command's `_pin_current_site` / `_site_context`. Do **not** use
`ObjectRoleAssignmentFactory` — it writes the row but skips the guardian
`view_organisation` sync that the queries actually read.

## Reports are NOT an educator-interface surface

`grep -ri report freedom_ls/educator_interface/` (excluding tests) returns
nothing. `GeneratedReport` generation/download live only in the Django admin
(`reports/views.py`, wired via `GeneratedReportAdmin.get_urls()` behind
`admin_view` -> **staff required**, plus an object-level `can_view_cohort`).
`org.educator@` is `is_staff=False`, so "open the cohort's report" can only
mean the cohort detail / course-progress panel. If a plan really wants the PDF
flow, the persona needs `is_staff=True` as well — ask first, it changes what
the persona proves.

## Credentials trap seen again

`org.educator@example.com`'s password was her **own email**, not the
`demodev@email.com` the QA plan quoted — `qa_create_organisation_scenarios`
does not reset the password of a pre-existing persona. Probe candidates before
quoting (see [[reference_verified_learner_setup]]), and prove login with a
rolled-back real POST + unverified negative control
([[reference_proving_allauth_login_works]]).
