# Frontend QA report: educator-interface-11-audit-log

All 18 tests passed across desktop, mobile and tablet. No bugs were found and no design states were tested. The test plan was corrected in place during the run (URLs, action labels, control names and a few expectations that had drifted from the spec and code).

## Methodology

- Tool: Playwright MCP, driving the dev server on port 8315 against the `educator-interface-11-audit-log` branch.
- Personas come from the test plan: Orla (organisation admin), Cole (cohort admin), Vera (cohort viewer), Sid (Southside admin) and demodev (site admin).
- Screenshots were collected into `screenshots/` beside this report. Every image referenced below exists there.
- Setup: the pre-step rebase replayed 52 commits onto origin/main. Conflicts were only in the generated `docs/app_structure.md` and `test_organisation/import_contracts.toml`, resolved by re-running `generate_app_map.py`. The lost-change check passed, the full tier ran 10140 passed, pre-commit was clean, and the branch was force-pushed. The upstream-change review found nothing changed. The rebase's front-end check was folded into this QA run (same pages, same three viewports). The dev DB carried residue from earlier QA runs (Sol in Cohorts A/B/C, 177 old audit rows) that broke section 4, so it was fully wiped and reseeded (`create_demo_data --yes`, then `qa_create_learner_administration_scenario`).

## Diff scoping

Class: FULL.

Changed front-end files (all under `freedom_ls/educator_interface/templates/educator_interface/`):

- `data-table-cells/`: `audit_details.html`, `audit_what.html`, `audit_when.html`, `audit_who.html`, `deactivate_registration.html`, `member.html`, `member_actions.html`, `member_roles.html`, `unregister.html`
- `modal/`: `add_member.html`, `change_cohorts.html`, `deactivate_cohort_registration_confirmation.html`, `deactivate_confirmation.html`, `deactivate_learner_confirmation.html`, `deactivate_member_confirmation.html`, `deactivate_registration_confirmation.html`, `deactivate_role_confirmation.html`, `delete_cohort_confirmation.html`, `reactivate_registration_confirmation.html`, `remove_from_cohort_confirmation.html`, `remove_role_confirmation.html`, `suspend_member_confirmation.html`, `unregister_confirmation.html`, `unregister_from_course_confirmation.html`
- `panels/`: `learner_history.html`, `learner_registrations.html`
- `partials/`: `audit_history_empty.html`, `audit_log_card.html`, `audit_log_empty.html`, `reason_field.html`

Desktop, mobile and tablet all ran. Nothing was skipped.

## Smoke gate

Pass. Pages checked: `/` and `/educator/organisations/northside/audit-log`.

## Results

| Test | Viewport | Status | Notes |
|---|---|---|---|
| 1 | desktop | pass | History tab empty state; Reason (optional) with help text; deactivate row with reason by Orla Admin; reactivate row newest first with empty details; reactivate dialog has no reason field; direct `__tabs/history` URL shows both rows. |
| 2 | desktop | pass | Input has maxlength=500. A 501-char value set via JS got POST 422, the dialog stayed open with the max-length error, Ada stayed Active. 500 chars stored in full and wrap in Details. Ada reactivated. |
| 3 | desktop | pass | Stale first tab got "already changed / Nothing changed" after a second tab deactivated Ada; exactly one new Learner deactivated row. Own member row shows no controls. Controls are labelled Deactivate role / Deactivate (plan said Remove / Suspend). |
| 4 | desktop | pass | Add to cohort, Move, Remove from cohort with reason, learner and cohort registration deactivate/reactivate/register, org and cohort Add learners. All rows correct on learner and cohort History tabs. Labels follow the spec, not the plan. |
| 5 | desktop | pass | Cohort created, renamed, no-change save wrote no row, deactivated, reactivated, deleted with reason. All rows remain in the org Audit log after delete. Target is the name at write time. Cohort A Settings shows no Delete and explains why. |
| 6.2-6.3 | desktop | pass | Resend setup email wrote a row; immediate second send was refused (try again in 15 minutes) and wrote no row. Nameless learner rows show; org log Target reads nameless@qa.test. |
| 7 | desktop | pass | Deactivate role wrote two Role deactivated rows with reason. Add member (two-step) wrote Role assigned. Change cohorts add/remove wrote matching rows. Member deactivate/reactivate wrote rows. Cohort A History has only Cohort A role rows. Labels follow the spec. |
| 8 | desktop | pass | Sidebar Administration: Members then Audit log. Columns When/Who/What/Target/Details, newest first, no search/sort/checkboxes/export. Who, What (multi-select), When filters narrow correctly; pagination 25 + 14. Plan combo replaced by System + Cohort deleted (empty state with Clear filters). Tampered params render the unfiltered list. |
| 9 | desktop | pass | Cole and Vera see no History tab; history URLs and `/audit-log` return 404; no Audit log/Members in the sidebar. Sid sees only Southside rows; Northside log 404. As demodev, each org log holds only its own rows. Org switcher dropdown not exercised. |
| 6.1 | desktop | pass | Run as demodev (Edit name needs `change_user`, held only by site_admin, same on main). Rename and rename back wrote rows; no-change save wrote none. Who shows demodev@email.com. |
| 10 | desktop | pass | HTML/script payloads in cohort name and reason render as literal text in the org log and cohort History: no injected elements, no alert, no console errors. |
| 12 | desktop | pass | Admin index lists Audit log entries. No Add link; columns, filters and search work. Change page has 13 read-only fields, no inputs, no Save/Delete. `/add/` and `/delete/` both 403. Action column shows raw codes. |
| 2.5 | desktop | pass | Reason (optional) with staff-only help text on all seven other dialogs. |
| 13.3 | desktop | pass | No Reason field on Reactivate member, Move, Change cohorts, Add to cohort (also none on learner Reactivate, cohort Reactivate, Register, Resend setup email). |
| 13 | desktop | pass | Learners, cohorts, members and learner Overview/Courses render with no console errors. Typed reason then Cancel shows a Discard changes? guard; nothing submitted. |
| 11.1 | mobile | pass | Ada History at 375px: cards with What first, then When, Who, Details; 500-char reason wraps; no horizontal scroll. Empty Details label still printed. |
| 11.2 | mobile | pass | Org Audit log at 375px: cards, no horizontal scroll. Filter opens the Filter & sort sheet (Who/When selects, What chips). Who = System narrows to five rows. |
| 11-dialog | mobile | pass | Deactivate dialog with Reason fits 375px; input full width; buttons 42px tall. |
| 11.3 | tablet | pass | Org Audit log at 768px: full table fits, no horizontal scroll; Details column narrow but readable. Drawer shows Members and Audit log. Cohort A History table and tabs fit. |

### Screenshots by test

**Test 1 (desktop)**

![](screenshots/page-2026-10-28T16-55-42-505Z.png)
Test 1: History tab with deactivate and reactivate rows.

![](screenshots/page-2026-10-28T16-55-34-302Z.png)
Test 1: deactivate dialog with Reason (optional) field.

**Test 2 (desktop)**

![](screenshots/page-2026-10-28T16-56-23-267Z.png)
Test 2: 501-character reason rejected with 422, dialog stays open.

![](screenshots/page-2026-10-28T16-56-33-594Z.png)
Test 2: 500-character reason wrapping in the Details cell.

**Test 3 (desktop)**

![](screenshots/page-2026-10-28T16-56-54-734Z.png)
Test 3: stale tab shows "already changed / Nothing changed".

**Test 4 (desktop)**

![](screenshots/page-2026-10-28T16-59-25-292Z.png)
Test 4: org Add learners result.

![](screenshots/page-2026-10-28T16-58-03-467Z.png)
Test 4: Ben history.

![](screenshots/page-2026-10-28T16-58-29-295Z.png)
Test 4: Sol history.

![](screenshots/page-2026-10-28T16-58-56-036Z.png)
Test 4: Cohort C history.

**Test 5 (desktop)**

![](screenshots/page-2026-10-28T17-00-22-971Z.png)
Test 5: cohort lifecycle rows remaining in the org Audit log after delete.

**Test 8 (desktop)**

![](screenshots/page-2026-10-28T17-03-22-647Z.png)
Test 8: org Audit log with columns and filters.

![](screenshots/page-2026-10-28T17-03-53-492Z.png)
Test 8: What multi-select with chip "What: a, b, c".

![](screenshots/page-2026-10-28T17-04-25-975Z.png)
Test 8: empty state "No entries match these filters." with Clear filters.

**Test 9 (desktop)**

![](screenshots/page-2026-10-28T17-05-05-183Z.png)
Test 9: role-restricted views (cohort admin / viewer, no History tab).

![](screenshots/page-2026-10-28T17-05-32-047Z.png)
Test 9: Southside log showing Sid Admin deactivating Sam South.

**Test 10 (desktop)**

![](screenshots/page-2026-10-28T17-06-28-546Z.png)
Test 10: HTML and script payloads rendered as literal text.

**Test 12 (desktop)**

![](screenshots/page-2026-10-28T17-06-58-653Z.png)
Test 12: Django admin audit log entries changelist.

**Test 11.1 (mobile)**

![](screenshots/page-2026-10-28T17-07-44-826Z.png)
Test 11.1: Ada History cards at 375px.

**Test 11.2 (mobile)**

![](screenshots/page-2026-10-28T17-07-54-604Z.png)
Test 11.2: org Audit log cards at 375px.

![](screenshots/page-2026-10-28T17-08-01-116Z.png)
Test 11.2: Filter & sort sheet.

**Test 11-dialog (mobile)**

![](screenshots/page-2026-10-28T17-08-17-502Z.png)
Test 11-dialog: deactivate dialog with Reason at 375px.

**Test 11.3 (tablet)**

![](screenshots/page-2026-10-28T17-08-32-347Z.png)
Test 11.3: org Audit log table at 768px.

![](screenshots/page-2026-10-28T17-08-40-794Z.png)
Test 11.3: hamburger drawer with Members and Audit log.

![](screenshots/page-2026-10-28T17-08-45-287Z.png)
Test 11.3: Cohort A History at 768px.

Tests 6.2-6.3, 7, 6.1, 2.5, 13.3 and 13 have no screenshots.

![](screenshots/page-2026-10-28T16-54-37-535Z.png)
Smoke gate: the organisation Audit log as Orla, also the per-run capture check (file written to qa-screenshots/, no image bytes returned).

## Design check

No design states tested.

## Bugs

No bugs were found.

## Bug status

No bugs this run.

## Plan corrections

- Educator URLs are `/educator/organisations/<slug>/...` (plan wrote `/educator/<slug>/`).
- Section 0.2 now names `create_demo_data --yes` as the prerequisite after a wipe.
- Action labels updated to the spec and code: Role assigned / Role deactivated / Member deactivated / Registration deactivated|reactivated / Cohort registration deactivated|reactivated (plan had Role granted / Role removed / Member suspended / Unregistered / Re-registered).
- Control names updated: Deactivate role, Deactivate, Deactivate registration.
- 6.1 runs as demodev because Edit name needs `change_user`, which only site_admin holds (same on main).
- 5.5 Target wording clarified: Target is the name at write time.
- 8.6 empty-state combo changed to System + Cohort deleted because the seed writes a System Learner deactivated row for Rae.
- 2.5 notes the maxlength=500 attribute.
- 7.3 notes the confirm step on Add member.

## General notes

No defects found. Observations with no action attached:

- On mobile cards and the desktop History table, rows without details still print an empty Details label/cell.
- At 768px the org log Details column is narrow and wraps heavily but remains readable.
- The Django admin changelist shows raw action codes (`learner.renamed`) in the Action column and its filter, not labels.
- The organisation switcher dropdown was not exercised (orgs opened by URL).
- The Django debug toolbar panel opens by default in dev and intercepts clicks until hidden (`djdt=hide` cookie plus localStorage `djdt.show=false`).
- Screenshot snapshot `.yml` and console `.log` files the MCP server wrote into `qa-screenshots/` were deleted before the collect, so only the 25 PNGs reached the spec dir.

status: ok · reason: 0 bugs, nothing to fix; report rendered, screenshots verified
