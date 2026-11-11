---
name: staff admin scenario leftovers
description: qa_create_staff_administration_scenario does NOT remove grants/staff rows added by QA runs, despite its docstring; reset recipe + Cohort W lone admin
type: reference
---
`qa_create_staff_administration_scenario` (branch educator-interface-13-staff-roles) only re-asserts
expected grants. It does NOT delete extra grants a tester added in the browser (assigned_by = Oscar
75 / Cora 78 / Vince 79), does NOT reactivate a deactivated staff row (Olga org.admin2 left
inactive), and does NOT remove staff rows of Eve (existing@) / existing2@. After running it, diff
every @qa.test grant on Northside/Southside/Westside/Eastside + their cohorts against the seed's
grant list and delete the extras; delete Eve/existing2 staff rows; set Olga's row active.
ObjectRoleAssignment and StaffMember deletes cascade to nothing (1 row each).

Test 7 step 5 "Cohort W, one cohort admin, no other staff": run
`qa_lone_cohort_admin_script.py` (now creates w.cohortadmin@qa.test Wanda Westcohort, pk 110 on
2026-11-10). Earlier run used lone.admin@qa.test (Lou, pk 108); his grant + Westside staff row were
deleted, user left. Cohort W pk 1a4124f9-fccd-452e-b3f2-f593efa5d6c9.

2026-11-10: existing2@qa.test (pk 107) deleted outright for a "no account" test. By then it held
no grants/staff rows/audit refs; delete was User 1 + EmailAddress 1 only. Role assigned_by and
audit actor FKs are SET_NULL, so nothing PROTECTs a staff user delete. Re-seeding the staff
scenario may recreate existing2 — check before assuming it is absent.

2026-11-10 (later): seed now deletes ALL demodev@email.com StaffMember rows itself (_clear_superuser)
but still leaves its inactive cohort grants, Eve's extra grants/staff row, existing2's staff row.
The diff/reset script (APPLY flag) lived in the session scratchpad as reset.py; recipe: run seed,
dry-run, APPLY, then delete existing2 User (User 1 + EmailAddress 1; seed does not recreate it).
Wanda's Westside staff row shows as "UNKNOWN STAFF (left alone)" -- expected, keep it.
zsh gotcha: `echo =====` in a chained Bash command errors ("= not found") and aborts the rest.
