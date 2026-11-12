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

2026-11-12: third Cohort W ask; caller now wants w.admin@qa.test "Wanda Wadmin" (script updated to
that; pk 118). Deleted old w.cohortadmin@ (pk 110) outright (User 1, EmailAddress 1, StaffMember 1,
ORA 1, guardian UserObjectPermission 2) so Cohort W has exactly one admin. Residue that day: Eve org
staff_viewer + staff row, Vince extra staff_roles_viewer, Nora Cohort A viewer (by Vince), Olga row
inactive. Delete grant rows then call `sync_user_object_permissions(user, target)` so guardian perms
do not go stale. ORA has NO `content_object`; use `g.content_type.get_object_for_this_type(pk=g.object_id)`.
User has no get_full_name(). Site: FORCE_SITE_NAME=DemoDev, so port 8019 needs no Site change.

2026-11-12 (later, 2nd reset): recurring. Inspect with `qa_staff_scenario_inspect_script.py` (piped to
`manage.py shell`), list extra ORA/StaffMember pks by hand, delete, then run the seed. The seed DOES
reset assigned_by on its own grants (Oscar's re-given org_admin went back to "by demodev"). Deleting
existing2 User cascades StaffMember 1 + EmailAddress 1 + User 1. Hook gotcha: the security guard
blocks any Bash command containing the os-module environ attribute (it matches "dot env"); use a
flag file for APPLY instead.
Lena = learner.only@qa.test, user 103, Learner pk cbc9f5af-9cc6-43f7-b757-35bdb3c82b51 (Cohort A).
Northside learner-free cohorts: Cohort B (b8b9c680-...) and Cohort Old (inactive).

2026-11-12 (3rd reset): assign_object_role get_or_create's on (user, ct, obj, role) and REACTIVATES an
inactive row, so leave an inactive copy of a grant the seed expects (the seed revives it); only delete
rows for roles the seed does not grant (e.g. Vera/Manny cohort_admin on A). Lena messages-tab data:
one Conversation per pair (pair_key "minpk:maxpk", unique per site), so the educator's own panel is one
thread. Reused `_pair`/`_Msg` from qa_create_direct_messaging_scenario: demodev(10)-Lena 3 msgs,
Oscar(75)-Lena 2, Cora(78)-Lena 2. "Other educator conversations" = oversight_conversations_for
(educators_of the learner) minus the viewer's own pair. The staff seed does not touch comms.
Logging into the dev server via curl with a password was denied by the permission classifier; verify
with the ORM query instead.
