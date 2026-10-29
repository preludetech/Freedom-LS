# Frontend QA report: educator-interface-8-bulk-operations

## Methodology

- Driven by hand through Playwright MCP against a dev server on port 8091. The branch badge was confirmed to show this branch.
- Personas come from the plan's section 0 and the data was seeded with `qa_create_bulk_operations_scenario`.
- Screenshots were collected into `screenshots/` beside this report. Every image referenced below exists there.
- Test 6.14 ran on a scratch settings module (threshold 5, database task backend) with `db_worker --batch`. The server then went back to normal dev settings and the scratch module was deleted.
- The rebase's front-end check was folded into this pass (same pages, three viewports) because main brought in no front-end change.

## Diff scoping

Class: FULL. Templates and static JS changed, in `educator_interface`, `panel_framework`, `learner_management` and the two `alpine-components.js` files (171 files in the diff, including spec_dd and docs). Desktop, mobile and tablet all ran. Skipped: nothing.

## Smoke gate

Pass. Pages checked: `/` and `/educator/organisations/northside/learners`.

## Results

| Test | Viewport | Status | Note |
|---|---|---|---|
| 1.1 | desktop | fail | Import page elements all present, but no breadcrumb/back link renders (B1) |
| 1.2 | desktop | pass | template.csv: attachment, BOM, four headers, two example rows |
| 1.3 | desktop | pass | 50 cap stated only when exceeded (422 with "Import a file instead" link) |
| 1.4 | desktop | pass | Import learners link on Cohort C tab carries ?cohort=pk; none on Cohort Old |
| 2.1 | desktop | pass | Six bad files refused with 422, focused alert summary, nothing stored |
| 2.2 | desktop | pass | No file: browser validation, or server 422 "This field is required." |
| 3.1 | desktop | pass | Preview counts 26 / 1 / 1 / 2 errors, error CSV, "Add 28 learners" |
| 3.2 | desktop | pass | Error filter link survives reload; Back returns 30 rows |
| 3.3 | desktop | pass | Duplicate and blank-email rows flagged; button reads "Add 1 learner" |
| 3.4 | desktop | pass | No cohort: all errors, no confirm button. Minor: still says "0 new accounts will get a setup email." |
| 3.5 | desktop | pass | Semicolon delimiter read |
| 3.6 | desktop | pass | Trailing empty column ignored |
| 4.1 | desktop | pass | Result page, 28 added, 26 setup emails sent (Mailpit confirms) |
| 4.2 | desktop | pass | Back and direct load of the preview URL redirect to the result |
| 4.3 | desktop | pass | import01 Pending in Cohort C, cohort count 27, Rae Removed Active |
| 4.4 | desktop | pass | Re-upload: nothing to add, no email |
| 4.5 | desktop | pass | dup.csv confirmed; error CSV holds the two expected rows |
| 5.1 | desktop | pass | Cohort-scoped upload page sentence correct |
| 5.2 | desktop | pass | Added to Cohort A; result links back to the cohort's learners |
| 6.1 | desktop | pass | Checkbox column and select-all present, buttons hidden; page size 10 |
| 6.2 | desktop | fail | Action bar works; course action labels differ from spec (B2) |
| 6.3 | desktop | pass | Add to cohort modal and "2 learners changed." |
| 6.3-result | desktop | pass | Result summary modal over refreshed table |
| 6.4 | desktop | fail | Skip behaviour correct; result wording differs from plan (B3) |
| 6.5 | desktop | pass | Remove from cohort with skip line and lost-access list |
| 6.6 | desktop | pass | Select all matching, untick, add 29 learners to Cohort B |
| 6.7 | desktop | pass | Sort and paging clear the selection |
| 6.8 | desktop | pass | Remove 31 matching learners from Cohort B |
| 6.9 | desktop | pass | Deactivate and Reactivate; label is "Inactive" |
| 6.10 | desktop | pass | Register/Unregister for course, run as two selections |
| 6.11 | desktop | pass | Resend setup email; skip groups correct (wording in B3) |
| 6.12 | desktop | pass | Stale selection: keys mode runs with skips, all-matching mode returns 422 |
| 6.13 | desktop | pass | JS-off full-page confirmation and result flows |
| 6.14.1 | desktop | pass | Threshold notice "runs in the background" |
| 6.14.2 | desktop | pass | 204 + HX-Trigger; bar locked with running text and spinner |
| 6.14.2-mobile | mobile | pass | Fixed bar fits, no overflow, 279px tall |
| 6.14.2-tablet | tablet | fail | Bar not fixed at 768px (B4) |
| 6.14.3 | desktop | pass | Worker run: result modal, lock lifted, notification read |
| 6.14.4 | desktop | pass | Unrelated open modal not replaced by the result |
| 6.14.5 | desktop | pass | Navigated away: no modal, bell shows 1 new, entry opens list |
| 6.14.6 | desktop | pass | JS-off background run with flash and notification |
| 6.14.7 | desktop | pass | Run status URL captured (used in 8.3) |
| 7.1 | desktop | pass | Cohort list buttons and More actions menu (label wording in B2) |
| 7.2 | desktop | fail | Behaviour correct; skip wording differs from plan (B3) |
| 7.3 | desktop | pass | Both skip lines, Confirm disabled |
| 7.4 | desktop | pass | Unregister cohorts from course; plan expectation stale (see notes) |
| 7.5 | desktop | pass | Bulk Deactivate and Reactivate Cohort C |
| 7.6 | desktop | pass | Single Deactivate/Reactivate on the Cohort C page |
| 8.1 | desktop | pass | cohort.admin: reduced menu, no import, 403 on import URL |
| 8.2 | desktop | pass | cohort.viewer: no checkboxes or buttons, 403 on import URL |
| 8.3 | desktop | pass | south.admin: import and run URLs 404 |
| 8.4 | desktop | pass | Non-requester superuser: import result/preview/run 404 |
| 8.5 | desktop | pass | Anonymous redirected to login |
| 9.1 | desktop | pass | Concurrent confirm: one result, no duplicates, one email each |
| 9.2 | desktop | pass | Repeat submit after Back: 422 re-render, no duplicates |
| 10.1 | mobile | pass | Import pages no overflow; preview rows as cards |
| 10.1-error | mobile | pass | Error summary wraps cleanly |
| 10.2 | mobile | pass | Bar fixed at bottom (219px), More actions opens upward |
| 10.3 | mobile | pass | Bottom-sheet confirmation and result fit |
| 10.1 | tablet | pass | No overflow; preview is a table at md |
| 10.2 | tablet | fail | Bar not fixed at 768px (B4) |
| 10.3 | tablet | pass | Centred confirmation and result modals fit |

### Screenshots

![](screenshots/page-2026-10-29T13-05-21-548Z.png)
6.1 (desktop): checkbox column, select-all header and pagination, nothing selected.

![](screenshots/page-2026-10-29T13-05-38-566Z.png)
1.1 (desktop): import upload page with no breadcrumb or back link.

![](screenshots/page-2026-10-29T13-06-08-042Z.png)
1.3 (desktop): Add learners dialog refusing a list over 50 and linking to the import page.

![](screenshots/page-2026-10-29T13-07-55-836Z.png)
2.1 (desktop): refused bad file with the focused error summary.

![](screenshots/page-2026-10-29T13-08-20-611Z.png)
3.1 (desktop): import preview with counts, notes and "Add 28 learners".

![](screenshots/page-2026-10-29T13-09-03-641Z.png)
4.1 (desktop): import result page, step 3 current.

![](screenshots/page-2026-10-29T13-11-36-180Z.png)
6.3 (desktop): Add to cohort confirmation modal.

![](screenshots/page-2026-10-29T13-12-17-111Z.png)
6.3-result (desktop): result summary modal over the refreshed table.

![](screenshots/page-2026-10-29T13-18-47-537Z.png)
6.12 (desktop): selection-changed re-render in all-matching mode.

![](screenshots/page-2026-10-29T13-20-14-974Z.png)
6.13 (desktop): JS-off full-page confirmation.

![](screenshots/page-2026-10-29T13-22-13-640Z.png)
7.1 (desktop): cohorts list with Register for course / Unregister from course buttons.

![](screenshots/page-2026-10-29T13-26-59-920Z.png)
6.14.2 (desktop): selection bar locked while "Deactivate is running…".

![](screenshots/page-2026-10-29T13-27-22-822Z.png)
6.14.2-mobile (mobile): fixed running bar, 279px tall.

![](screenshots/page-2026-10-29T13-27-30-631Z.png)
6.14.2-tablet (tablet): selection bar rendered inline, not fixed.

![](screenshots/page-2026-10-29T13-28-00-172Z.png)
6.14.3 (desktop): worker result modal "30 learners changed."

![](screenshots/page-2026-10-29T13-33-59-598Z.png)
8.1 (desktop): cohort.admin reduced More actions menu.

![](screenshots/page-2026-10-29T13-35-44-991Z.png)
10.1-error (mobile): bad-header error summary at 375px.

![](screenshots/page-2026-10-29T13-35-46-823Z.png)
10.1 (mobile): import page cards at 375px.

![](screenshots/page-2026-10-29T13-36-08-712Z.png)
10.2 (mobile): fixed selection bar with two rows ticked.

![](screenshots/page-2026-10-29T13-36-09-312Z.png)
10.2 (mobile): More actions menu open upward.

![](screenshots/page-2026-10-29T13-36-10-514Z.png)
10.3 (mobile): confirmation as a bottom sheet.

![](screenshots/page-2026-10-29T13-36-12-513Z.png)
10.3 (mobile): result modal.

![](screenshots/page-2026-10-29T13-37-36-742Z.png)
10.2 (tablet): selection bar not fixed at 768px.

![](screenshots/page-2026-10-29T13-37-51-298Z.png)
10.3 (tablet): centred confirmation modal.

![](screenshots/page-2026-10-29T13-37-53-339Z.png)
10.3 (tablet): result modal.

![](screenshots/page-2026-10-29T13-38-14-547Z.png)
10.1 (tablet): import preview as a table at md.

## Design check

No design states tested.

## B1: Import pages show no breadcrumb/back link to Learners

Manifestations: 1.1 (desktop).

![](screenshots/page-2026-10-29T13-05-38-566Z.png)

- Expected: QA plan 1.1: sidebar, breadcrumbs and organisation switcher present "as on any educator page".
- Actual: `standalone_page_context` builds breadcrumbs from `[section]` alone, giving a single crumb. `panel_framework/partials/breadcrumbs.html` renders its back link only for 2 or more crumbs, so the import upload, preview and result pages have no "Learners" back link. The spec only says the breadcrumbs are built "the way panel_framework_view does", which for a section root also renders nothing. Spec and plan disagree. Whether a sub-page of a section gets a back link is a product decision.

## B2: Course bulk actions labelled "Register for course" / "Unregister from course"

Manifestations: 6.2 (desktop), 7.1 (desktop).

![](screenshots/page-2026-10-29T13-22-13-640Z.png)

- Expected: spec R7 tables and action-bar paragraph, and QA plan 6.2/7.1: "Register for a course", "Unregister from a course".
- Actual: `RegisterForCourseBulkAction`, `UnregisterFromCourseBulkAction`, `RegisterCohortForCourseBulkAction` and `UnregisterCohortFromCourseBulkAction` use "Register for course" / "Unregister from course", matching main's existing single-learner `RegisterLearnerForCourseAction` label. Following the spec makes the bulk menu differ from the single action; keeping the code means rewording the spec. This is a copy and consistency decision.

## B3: Bulk result and skip wording differs from the QA plan's sentences

Manifestations: 6.4 (desktop), 7.2 (desktop). No screenshots.

- Expected: plan 6.4: "1 learner changed. 2 were already in the cohort."; plan 7.2: "1 is an inactive cohort and will be skipped."; plan 6.11: "setup email sent recently".
- Actual: the result summary reads "1 learner changed. | 2 already in the cohort" followed by per-learner reasons; the cohort skip line reads "1 is inactive and will be skipped."; the resend skip group reads "emailed recently". The spec does not fix these sentences, so whether to change the code or the plan is a copy decision.

## B4: Selection bar is not fixed to the bottom at tablet width (768px)

Manifestations: 6.14.2-tablet (tablet), 10.2 (tablet).

![](screenshots/page-2026-10-29T13-27-30-631Z.png)
![](screenshots/page-2026-10-29T13-37-36-742Z.png)

- Expected: QA plan 6.14.2 and 10.2: at 375x812 and 768x1024 the selection bar is fixed to the bottom of the viewport.
- Actual: `table_selection_bar.html` uses `fixed inset-x-0 bottom-0 ... md:static`, and its comment says it is fixed below md only. At 768 (md) the bar renders inline under the table, so after ticking rows on a long page the bar and the running status sit off-screen. The spec is silent. The template choice is deliberate, so changing the breakpoint is a UX decision.

## Bug status

- **UNRESOLVED** — B1: Import pages show no breadcrumb/back link to Learners (reason: the spec says breadcrumbs are built the way `panel_framework_view` builds them, which gives a section root no back link; the QA plan expects one. Whether a section's sub-page gets a back link is a product decision)
- **UNRESOLVED** — B2: Course bulk actions are labelled "Register for course" / "Unregister from course" rather than the spec's "Register for a course" / "Unregister from a course" (reason: the code matches main's existing single-learner "Register for course" action. Following the spec splits the two labels; keeping the code means rewording the spec. A copy decision)
- **UNRESOLVED** — B3: Bulk result and skip wording differs from the QA plan's sentences (reason: the spec does not fix these sentences, so choosing between the code's wording and the plan's is a copy decision)
- **UNRESOLVED** — B4: Selection bar is not fixed to the bottom at tablet width (768px) (reason: the template deliberately fixes the bar only below `md`; moving the breakpoint is a UX decision the spec does not make)

## General notes

### Stale plan expectations (not bugs)

These expectations were stale because of the plan's own earlier steps or older wording.

- Page size is 10, not 25 (6.1, 6.6).
- The status label is "Inactive" (main's existing label), not "Removed" (6.9).
- 6.10 ran as two selections: no single search term covers bulk20/21 and solo together, and searching clears the selection.
- 6.11 used cohortimp instead of import01 (same kind of import-created pending account) and waited out the 15-minute resend window.
- 7.4's expected counts conflict with the plan's own seed (Cohort B was seeded on Course Hid) and with 7.2 (which registered Cohort A).
- 8.1 and 9.1 counts differ because earlier steps changed the data (Ben left Cohort B in 6.8; semi.csv was never confirmed earlier).

### Copy observations (no action attached)

- The import result headline reads "Added 2 learners. 0 rows were not added." when nothing failed.
- The nothing-to-add preview still says "0 new accounts will get a setup email."
- On mobile (375x812) the selection bar takes about a third of the viewport (219 to 279px tall).

### Data blocker cleared during the run

The notification bell panel returned HTTP 500 (AttributeError in a GenericForeignKey prefetch). Four notifications from the 2026-10-25 QA run targeted `learner_management.BulkActionRun`, a model that existed only on this branch (created by learner_management 0008, deleted by 0010 when it moved to panel_framework). The rows were deleted by pk and the panel worked. No install outside this dev database can hold such rows, because 0008 and 0010 ship together, but the comms panel has no guard against a notification whose target model is gone.

### Test-harness artefact

At 768px, Playwright's scroll-into-view click on "More actions" once left the menu closed (the menu closes on scroll). A click after scrolling worked. This is treated as a test-harness artefact.

### Dev badge overlap

The dev-only branch badge overlaps the bottom-left of the fixed mobile selection bar.

status: ok · reason: 4 bugs — 0 fixed, 4 unresolved (each needs a product or copy decision); report rendered, screenshots verified
