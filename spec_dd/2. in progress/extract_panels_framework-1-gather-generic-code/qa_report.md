# Frontend QA report: extract_panels_framework-1-gather-generic-code

## Summary

The full frontend test plan (`3. frontend_qa.md`) ran on desktop, mobile and tablet. There were 79 test results: 74 passed, 4 failed and 1 was skipped (3.4). The smoke gate passed. The failures come from 2 bugs:

- **B1**: the import error-rows table header draws a white band across the amber warning notice (tests 10.4, 10.5).
- **B2**: the educator navigation sheet on phone and tablet shows a "Close navigation" control (test 12.1 on mobile and tablet).

## Methodology

- Playwright MCP drove a dev server on its own port, logged in as the QA admin.
- Screenshots were collected into `screenshots/` beside this report. Every image linked here exists there.
- Test 9.5 used a second dev server on a throwaway settings module, stopped afterwards (see General notes).
- Pre-step rebase: 4 upstream commits, clean replay of 96 commits, lost-change check passed. The targeted tier ran 13944 passed and 1 failed (`freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer`). That test ran while QA drove the dev server, and it passed when re-run alone, so it was treated as a load flake. The branch was force-pushed with lease.

## Diff scoping

- Class: **FULL**.
- Trigger: 358 changed files, including front-end files such as `freedom_ls/base/static/base/js/alpine-components.js`, `freedom_ls/base/templates/_base_interface.html`, `freedom_ls/base/templates/cotton/button.html`, `freedom_ls/comms/templates/comms/partials/thread.html`, the `educator_interface` templates and the `panel_framework` templates.
- Nothing was skipped. Desktop, mobile and tablet all ran.

## Smoke gate

Outcome: **pass**. Pages loaded: `/` and `/educator/organisations/demodev/cohorts/`.

## Results

### Desktop

| Test | Status | Notes | Screenshot |
|---|---|---|---|
| 1.1-1.4 | pass | Deactivate cohort dialog: title, body, optional reason, Cancel left / Deactivate right, focus on Cancel, 40px buttons | ![](screenshots/page-2026-11-16T13-49-50-952Z.png) |
| 1.5-1.6 | pass | Footer Cancel closes at once. Header x shows the discard prompt. Keep editing restores the text. Esc re-shows the prompt | ![](screenshots/page-2026-11-16T13-50-07-843Z.png) |
| 1.7 | pass | Reason capped at 500 by the browser. With the cap removed, 520 characters gives a 422 with a field error and the dialog stays open | ![](screenshots/page-2026-11-16T13-51-39-889Z.png) |
| 1.8-1.9 | pass | "Deactivating…" then the page reloads as Inactive. History row shows the reason. Cohort reactivated afterwards | none |
| 2.1 | pass | Reactivate dialog has no reason field, Cancel focused, one primary button | none |
| 2.2 | pass | Learner Deactivate cancelled. Dan Reactivate confirmed | none |
| 2.3 | pass | Resend setup email confirm for Penny, "Sending…", dialog closes | none |
| 2.4 | pass | Registration Deactivate has a reason field. Reactivate has none. Each acts on its own row | none |
| 2.5 | pass | Row buttons have full names. Remove confirm is btn-error. Cancel closes | none |
| 2.6 | pass | Both staff Deactivate dialogs have reason fields | none |
| 2.7 | pass | Button styles and the single-ellipsis loading labels are correct | none |
| 3.5 | pass | Second resend gets "Setup email sent recently" with one focused Close | ![](screenshots/page-2026-11-16T13-56-12-036Z.png) |
| 3.1 | pass | Stale deactivate: "already inactive", one focused footer Close | ![](screenshots/page-stale-3-1.png) |
| 3.2 | pass | Stale reactivate: "already active" with Close | none |
| 3.3 | pass | Stale learner deactivate: "was already changed" with Close | none |
| 3.4 | skip | See General notes | none |
| 3.6 | pass | Stale staff deactivate gives the generic "This is no longer available" refusal with a footer Close | ![](screenshots/page-stale-3-6.png) |
| 3.7 | pass | Every refusal has no form, no Cancel and exactly one footer Close | none |
| 4.1-4.2 | pass | Delete dialog on an empty cohort: reason field, Cancel focused, one btn-error Delete. A non-empty cohort offers no Delete | ![](screenshots/page-delete-4-1.png) |
| 4.3 | pass | Stale delete keeps the dialog open with a red error that takes focus. Delete is withdrawn | ![](screenshots/page-delete-stale-4-3.png) |
| 4.4 | pass | "Deleting…" then the cohorts list without the cohort | none |
| 5.7 | pass | Add to cohort: the select re-renders the title. A 422 puts focus on the error summary | ![](screenshots/page-addcohort-422-5-7.png) |
| 5.1 | pass | Move dialog: Move disabled with an aria reason in the body at 14px. Choosing a cohort enables Move | ![](screenshots/page-move-5-1.png) |
| 5.2 | pass | Stale move: "no longer in" refusal with Close | none |
| 5.3 | pass | Empty email gives an error summary. Role step shows the cohort checklist. Plan needs a non-staff email (see General notes) | ![](screenshots/page-addstaff-role-5-3.png) |
| 5.4 | pass | Change cohorts: search, count and checklist. An unchanged submit is refused | ![](screenshots/page-changecohorts-5-4.png) |
| 5.5 | pass | Learner added result dialog with Close and Add another | ![](screenshots/page-addlearner-result-5-5.png) |
| 5.6 | pass | Messages composer on panel padding. Oversight dialog has one header, read-only note and footer Close | ![](screenshots/page-oversight-5-6.png) |
| 5.8 | pass | Register for a course: title re-renders, registration listed | ![](screenshots/page-register-5-8.png) |
| 11.6 | pass | Add learner refreshes the table, keeping search and filters, and shows the new row | none |
| 6.1-6.2 | pass | Quick view opens beside the table. Close is 44x44. Focus returns to the trigger | ![](screenshots/page-quickview-6-1.png) |
| 6.3 | pass | Esc in the composer shows the discard prompt. Keep editing keeps the draft | ![](screenshots/page-qv-discard-6-3.png) |
| 7.1 | pass | Bulk deactivate dialog for 3 learners, cancelled | ![](screenshots/page-bulk-deact-7-1.png) |
| 7.2 | pass | Bulk resend shows skip lines, then a result dialog with Close | ![](screenshots/page-bulk-resend-result-7-2.png) |
| 7.3 | pass | Confirm disabled with the reason in the body at 14px. The More menu closes on choice | ![](screenshots/page-bulk-resend-disabled-7-3.png) |
| 7.4 | pass | Dialog re-renders with recounted lines. No notice box appeared, so no tone to judge | ![](screenshots/page-bulk-notice-7-4.png) |
| 7.5 | pass | JS off: fallback bar opens the confirmation, with Cancel and close as links. Nav docked at 1920 | ![](screenshots/page-nojs-confirm-7-5.png) |
| 7.6 | pass | Inline run (30) and background run (328) both correct. Notification listed. Dev backend took about 54s | ![](screenshots/page-bulk-bg-result-7-6.png) |
| 7.7 | pass | Cohort bulk bar shows the four actions | ![](screenshots/page-cohorts-bulk-7-7.png) |
| 7.8 | pass | Add to cohort: confirm disabled until a cohort is chosen, reason in the body at 14px | ![](screenshots/page-bulk-addcohort-7-8.png) |
| 8.1 | pass | Show inactive filter adds and removes with its chip | ![](screenshots/page-cohorts-filter-8-1.png) |
| 8.2 | pass | Audit log When options work. Last 7 days gives 807 of 809 entries | ![](screenshots/page-history-7d-8-2.png) |
| 8.3 | pass | A bogus When value shows the full list, no error | none |
| 8.4 | pass | Applied chip, Add filter, Clear all and Export CSV in the toolbar row | ![](screenshots/page-history-7d-8-2.png) |
| 9.1 | pass | Dashboard skeletons then figures. Only the Cohorts tile links | ![](screenshots/page-dashboard-9-1.png) |
| 9.2 | pass | Report tables share one header style. Headings 18px/600. Status badges | ![](screenshots/page-report-9-2.png) |
| 9.3 | pass | Compact empty state, then Generate report adds a downloads row | ![](screenshots/page-report-generated-9-3.png) |
| 9.4 | pass | JS off: "Load the figures" link loads the body | ![](screenshots/page-report-nojs-9-4.png) |
| 9.5 | pass | Over-limit cohort shows the amber warning and no table | ![](screenshots/page-report-overlimit-9-5.png) |
| 10.1 | pass | Import format table uses the shared header. Buttons are btn-sm | ![](screenshots/page-import-10-1.png) |
| 10.2 | pass | Wrong header gives a 422 and a focused red alert | ![](screenshots/page-import-badheader-10-2.png) |
| 10.3 | pass | 60-row preview with pager. 30-row preview tiles filter by label | ![](screenshots/page-import-preview60-10-3.png) |
| 10.4 | **fail** | Error rows sit in an amber warning notice, but the sticky header cells have an opaque white background. See B1 | ![](screenshots/page-import-preview30-10-3.png) |
| 10.5 | **fail** | Result page is otherwise correct (focus, 32px buttons, time matches audit log). Same white header band. See B1 | ![](screenshots/page-import-result-10-5.png) |
| 11.1 | pass | Status chip, created date, staff list as list rows, headings 18px/600 | ![](screenshots/page-cohort-settings-11-1.png) |
| 11.2 | pass | Registrations as list rows. Course sections have no box. Quiz table in the shared style | ![](screenshots/page-learner-courses-11-2.png) |
| 11.3 | pass | Rename updates in place. Empty name shows one line under the field | ![](screenshots/page-cohort-rename-empty-11-3.png) |
| 11.4 | pass | Cohorts and learners tables filled, with "—" for empty values | ![](screenshots/page-cohorts-filter-8-1.png) |
| 11.5 | pass | History row shows a dl. Deleted user shows a fallback icon | ![](screenshots/page-history-deleted-user-11-5.png) |
| 11.7 | pass | Learner with no messages shows the compact empty state | ![](screenshots/page-learner-nomessages-11-7.png) |
| 12.2 | pass | Sidebar docked as a 256px column, same after reload | ![](screenshots/page-dashboard-9-1.png) |
| 12.3 | pass | Messages unread count went from 1 to 2 after 35s with no reload | none |
| 12.4 | pass | Learner course outline docked at 1920. Messages and notification panels open | ![](screenshots/page-learner-course-1920-12-4.png) |
| 12.5 | pass | Topics open with no console or page errors | ![](screenshots/page-learner-topic-12-5.png) |
| 12.6 | pass | Component reference page returns 200 with all tones, table and list rows | ![](screenshots/page-component-reference-12-6.png) |
| 13.2 | pass | 21 educator URLs return 200 with no leaked template tags | none |
| 13.3 | pass | Other dialogs each have a header close, a body and one footer, and close from Cancel | none |
| 13.4 | pass | Focus stays in the dialog. Keyboard close returns focus to the trigger | none |

### Mobile

| Test | Status | Notes | Screenshot |
|---|---|---|---|
| 1.10 | pass | Bottom sheet with the footer in view, 44px controls, no sideways scroll | ![](screenshots/page-2026-11-16T13-52-23-508Z.png) |
| 7.5 | pass | JS off at 375: nav stacked above content, filter sheet renders inline | ![](screenshots/page-nojs-mobile-7-5.png) |
| 6.4 | pass | Quick view is a full-width bottom sheet with controls in reach | ![](screenshots/page-quickview-mobile-6-4.png) |
| 8.5 | pass | Filter sheet opens with a 44px Close. Stays closed at 1920 | ![](screenshots/page-filter-sheet-8-5.png) |
| 9.6 | pass | Report tables scroll in their own region. Page does not scroll sideways | ![](screenshots/page-report-mobile-9-6.png) |
| 10.3 | pass | Import preview shows rows as cards, no sideways scroll | ![](screenshots/page-import-mobile-10-3.png) |
| 11.8 | pass | Cohort and learner pages: no sideways scroll, no button under 44px | ![](screenshots/page-learner-settings-mobile-11-8.png) |
| 12.1 | **fail** | Sheet has no header and closes by backdrop and Esc, but shows a "Close navigation" control. See B2 | ![](screenshots/page-sidebar-sheet-12-1.png) |
| 12.4 | pass | Learner course outline sheet has no header or close control. Esc closes it | ![](screenshots/page-learner-outline-mobile-12-4.png) |

### Tablet

| Test | Status | Notes | Screenshot |
|---|---|---|---|
| 13.1 | pass | At 768 tables render as cards, names unclipped, no sideways scroll | ![](screenshots/page-cohort-learners-tablet-13-1.png) |
| 12.1 | **fail** | Navigation opens as the same bottom sheet with the same "Close navigation" control. See B2 | ![](screenshots/page-sidebar-tablet-12-1.png) |

## Design check

No design states tested.

## B1: Import error-rows table header draws a white band across the amber warning notice

Manifestations:

- Test 10.4, desktop
- Test 10.5, desktop

![](screenshots/page-import-preview30-10-3.png)

![](screenshots/page-import-result-10-5.png)

**Expected:** the error rows table inside the warning notice reads as part of the notice. Its header row sits on the notice's own tint like the body rows.

**Actual:** the table's header cells (th) carry an opaque white background. This comes from the shared table's sticky header for its capped-height scroll region. On the import preview and the import result, the header row is a white band across the amber notice while the body rows show the tint.

## B2: Educator navigation sheet on phone and tablet shows a "Close navigation" control

Manifestations:

- Test 12.1, mobile
- Test 12.1, tablet

![](screenshots/page-sidebar-sheet-12-1.png)

![](screenshots/page-sidebar-tablet-12-1.png)

**Expected:** the shell side panel rises as a bottom sheet with no header and no close control. It closes by backdrop tap or Esc (panel-framework SKILL.md rules; Test 12.1). The learner course outline already behaves this way.

**Actual:** `freedom_ls/educator_interface/templates/educator_interface/_shell.html` renders an `lg:hidden` "Close navigation" x button at the top of the sidebar content, so the educator navigation sheet shows a close control below lg. The same button exists on main.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| smoke | desktop | `/educator/organisations/demodev/cohorts/` | ![](screenshots/page-2026-11-16T13-48-33-115Z.png) | clean |
| 1.1 | desktop | `/educator/organisations/demodev/cohorts/<A>/__tabs/settings` | ![](screenshots/page-2026-11-16T13-49-50-952Z.png) | clean |
| 1.10 | mobile | `/educator/organisations/demodev/cohorts/<A>/__tabs/settings` | ![](screenshots/page-2026-11-16T13-52-23-508Z.png) | clean |
| 3.5 | desktop | `/educator/organisations/demodev/learners/<penny>/__tabs/settings` | ![](screenshots/page-2026-11-16T13-56-12-036Z.png) | clean |
| 5.1 | desktop | `/educator/organisations/demodev/cohorts/<A>/__tabs/learners` | ![](screenshots/page-move-5-1.png) | clean |
| 12.1 | mobile | `/educator/organisations/demodev/cohorts` | ![](screenshots/page-cohorts-mobile-12-1.png) | clean |
| 13.1 | tablet | `/educator/organisations/demodev/learners` | ![](screenshots/page-learners-tablet-13-1.png) | clean |
| 13.1 | tablet | `/educator/organisations/demodev/cohorts/<A>/__tabs/learners` | ![](screenshots/page-cohort-learners-tablet-13-1.png) | clean |

## Data changes

| What changed | Via |
|---|---|
| Re-ran `qa_create_dev_org_baseline --site-name DemoDev` (idempotent): QA cohorts A/B/inactive/empty, named learners, Cora cohort admin, more than 250 learners, audit history, Alice-Cora conversation | `sdd:qa-data-helper` |

## Bug status

| Bug | Status |
|---|---|
| B1 | **UNRESOLVED** — Import error-rows table header draws a white band across the amber warning notice (reason: the fix (commit 1fe573edc) gave `<c-panel-notice>` a per-tone `--panel-table-head` composited over the white surface, but the import notice sits on the grey page canvas, so the header still showed as a cream band against the olive-grey body; reverted in 166820610. The header needs an opaque fill that matches the notice wherever it sits, or the notice an opaque background of its own) |
| B2 | **FIXED** (commit: 1dbd8ff6e) — Educator navigation sheet on phone and tablet shows a 'Close navigation' control |
| — | **UNRESOLVED** — full test run after the fixes did not complete (reason: stopped by the user before it reported; the fixer's targeted tier passed, 2563 tests) |

## General notes

- Pre-step rebase: 4 upstream commits, clean replay of 96 commits, lost-change check passed, targeted tier 13944 passed and 1 failed (`freedom_ls/panel_framework/tests/playwright/test_quick_view_flow.py::test_quick_view_drawer`, run while QA drove the dev server; passed when re-run alone, so treated as a load flake). Branch force-pushed with lease.
- Plan out of date, Test 5.3: the second staff member (Cora) is already staff, so entering her email is refused ("This change wasn't made / Cora Cohortadmin is already on the staff here."). The role step needs a non-staff email.
- Test 3.6: a stale "Deactivate staff member" answers with the generic "This is no longer available / It may have been removed, or you may no longer have access to it." rather than a named "already inactive" refusal. Main raises `Http404('The staff member is already inactive')` for this case, so the wording predates the branch.
- Bulk skip lines word inactivity as "1 is already inactive and will be skipped" (no noun), while setup lines say "1 learner is already set up and will be skipped". The "already inactive" reason string is the same on main.
- Cohort "Add filter" menu shows the toggle as a group "Show inactive" holding one option also named "Show inactive". The choice label is the same on main.
- With JavaScript off at 375, the learners filter sheet renders inline in the toolbar (Filter heading, Reset, Close, status pills, selects, Cancel / Show results) below the stacked navigation. It is usable as a fallback.
- Closing a dialog by a mouse click on its footer Cancel leaves focus on body. Esc and keyboard activation of Cancel or the header close return focus to the trigger (the plan's 13.4 check is keyboard and passes).
- The dev task backend runs background bulk jobs inside the request, so the 328-learner resend showed "Sending…" for about 54s before its result. Production uses the database backend.
- Test 9.5 was staged by starting a second dev server on a throwaway settings module (`REPORTS_MAX_LEARNERS=10`, kept in the job's temp directory, not the repo). That server was stopped afterwards.
- Data touched by tests (all part of normal flows, left in a consistent state): QA cohort empty deleted (Test 4.4; the baseline command recreates it), QA cohort inactive left inactive, Dan reactivated (Test 2.2), learner Zed Newqa added then deactivated (5.5, 7.4), 28 + import learners added from `qa_import_30.csv`, a "Course Hid" registration added to QA cohort A (5.8), a report generated for QA cohort B. Re-running `qa_create_dev_org_baseline` restores the named scenario.
- **Skipped, Test 3.4:** not run, as the plan allows. Staging needs Penny's setup link, which only reaches the mailbox, and Penny was rate-limited by 3.5.

status: ok · reason: 2 bugs — 1 fixed, 1 unresolved; report rendered, screenshots verified
