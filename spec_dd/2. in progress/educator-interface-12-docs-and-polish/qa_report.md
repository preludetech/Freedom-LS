# Frontend QA report: educator-interface-12-docs-and-polish

## Methodology

- Tested by hand with the Playwright MCP at 1440x900 (desktop), 375 and 390 (phone) and 768 (tablet).
- Screenshots were collected into `screenshots/` beside this report. Every image linked here exists in that directory.
- The branch was rebased onto main first. One `app_structure.md` conflict was resolved, and two stale tests were fixed in 47277db57.
- The server ran on dev settings with the `first_class` theme, taken from the environment (`FLS_THEME`). The plan's second pass in the default theme was NOT run. Test 14's doc screenshots are `first_class`, not default.
- Over-limit tests used DemoDev's "QA Over 500 Cohort" (limit 500).

## Diff scoping

Class: FULL. The diff touches 413 files, including `freedom_ls/educator_interface/templates/**`, `freedom_ls/panel_framework/templates/**` and `freedom_ls/comms/templates/**`. Nothing was skipped; everything ran.

## Smoke gate

Pass. Pages checked: `/` and `/educator/organisations/northside/learners`. No failure URL or reason.

## Results by test

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 1 | desktop | pass | All 7 sections return 200 with their headings (Staff is headed Staff; `/members` is 404). No console errors. Export CSV is `btn-secondary btn-sm` at toolbar right. | ![](screenshots/t1-desktop-learners.png) |
| 1-report-copy | desktop | fail | Quiz confusions "Got it wrong" reads "1 of 1 learners" (see B7). | ![](screenshots/t1-desktop-report.png) |
| 2.1 | desktop | fail | "More actions" needs two clicks (see B1). | ![](screenshots/page-2026-11-05T17-39-35-558Z.png) |
| 2.1 | desktop | pass | Bulk Deactivate a course registration: question title, Cancel focused, in-flight "Deactivating…", result "2 learners changed.". With 0 eligible the confirm is disabled. Bulk Register likewise. | ![](screenshots/t2-1-deactivate-reg-dialog.png) |
| 2.2 | desktop | pass | Cohorts bar: "Deactivate the Course Pub registration for 2 cohorts?", trigger `btn-secondary btn-sm`. | none |
| 2.3 | desktop | pass | `unregister_from_course` and cohorts `unregister` endpoints: GET 404, POST with HX-Request and CSRF 404. | none |
| 2.4 | desktop | pass | Cohort Courses tab action reads "Register for a course". Rows have no row menu any more, so the row-menu half has nothing to check. | none |
| 3-learner-settings | desktop | pass | Deactivate, Reactivate and Resend setup email dialogs: question titles naming the learner, Cancel focused, primary verb at right. | ![](screenshots/t3-learner-deactivate-dialog.png) |
| 3-remove-move | desktop | pass | Remove confirm is `btn-error` with Cancel focused. Move dialog titled "Move Ada Lovelace", Move disabled until a destination is chosen. | ![](screenshots/educator_learner_move.png) |
| 3-courses-tab | desktop | fail | No Deactivate or Reactivate on a registration in the Courses tab (see B4). | ![](screenshots/page-2026-11-05T17-47-13-571Z.png) |
| 3-register-single-title | desktop | fail | Single-learner Register and Add to cohort titles are not questions (see B5). | none |
| 3-cohort-settings | desktop | pass | Deactivate, Reactivate, and Delete (only on an empty cohort). Taken name shows "Another cohort already has this name." with `aria-invalid`. | ![](screenshots/t3-cohort-name-taken.png) |
| 3-staff | desktop | pass | Deactivate role, Deactivate staff member and Reactivate staff member dialogs: question titles, Cancel focused, primary confirm. | ![](screenshots/educator_members.png) |
| 3-staff-added-by | desktop | fail | "Added 2 Nov 2026 by Not recorded" (see B6). | ![](screenshots/educator_members.png) |
| 3-bulk | desktop | pass | All bulk dialogs have question titles, correct button styles and Cancel focused. | ![](screenshots/educator_bulk_add_to_cohort.png) |
| 3-side-effects | desktop | pass | Deactivate with reason: Inactive badge, button flips to Reactivate, History row recorded. Focus lands on `#main-content`. | ![](screenshots/educator_confirm_with_reason.png) |
| 3-repeat | desktop | pass | Stale tab: the dialog opens, confirming shows "Bulk 01 Alpha was already changed. Nothing changed…" rather than an error. | ![](screenshots/t3-stale-deactivate-confirmed.png) |
| 4.1 | desktop | pass | cohort.viewer nav is Dashboard, Cohorts, Learners, Courses; `/staff` and `/audit-log` are 404. Empty audit log and empty staff messages correct. | ![](screenshots/t4-eastside-staff-empty.png) |
| 4.2 | desktop | pass | No-match message and "Clear filters" restore the list on learners, cohorts, staff, audit log, cohort Learners tab and learner History tab. | none |
| 4.3 | desktop | pass | Eastside dashboard and Cohort Empty overview empty states are centred, muted and end in full stops. | ![](screenshots/t4-3-empty-cohort-overview.png) |
| 5 | desktop | pass | Status badge colours and header badge rules correct; every badge has text. | ![](screenshots/t1-desktop-learners.png) |
| 6 | desktop | pass | Nameless learner shows the email everywhere; Escape returns focus to the trigger. | ![](screenshots/t6-nameless-quickview.png) |
| 7 | desktop | pass | Status chip "Active, Pending" with no remove control; Clear all returns to the default and drops the URL parameter. | ![](screenshots/t7-status-inactive.png) |
| 8.1 | desktop | skip | Rows no longer carry a row menu, so there is no trigger. The same dialog is covered by 8.2-8.4. | none |
| 8.2-8.3 | desktop | pass | Deleted cohort: quick-view trigger and bulk action both open "This is no longer available". | ![](screenshots/t8-unavailable-dialog.png) |
| 8.4 | desktop | pass | Sorting a deleted cohort's Learners tab shows the same dialog; no navigation. | none |
| 8.5 | desktop | pass | Other-organisation and zero uuid quick views: both 404 with identical 1390-byte bodies. | none |
| 9.1 | desktop | pass | Reactivate Cohort Old from Settings: URL stays on settings, badge gone, button now Deactivate. | ![](screenshots/t9-1-reactivated.png) |
| 9.2 | desktop | pass | Stale tabs refuse with the right sentences on submit. | ![](screenshots/t9-2-stale-rename.png) |
| 9.3 | desktop | pass | Nameless educators listed by email as stored; Overview has no Educators card. | ![](screenshots/t4-3-empty-cohort-overview.png) |
| 9.6 | desktop | pass | All-existing CSV: "Already a member: 2", no confirm offered. | ![](screenshots/t9-6-import-preview.png) |
| 9.7 | desktop | pass | File input bordered with a styled "Choose File" button, 48px tall. | ![](screenshots/t9-7-import-page.png) |
| 9.8 | desktop | pass | Bulk Add to cohort and Move with a deleted cohort: "Choose a cohort from the list.", dialog stays open. | ![](screenshots/t9-8-bulk-add-gone.png) |
| 9.10 | desktop | pass | Dashboard and Report show the identical over-limit sentence; Generate report disabled; notice contrast about 8.2:1. | ![](screenshots/t9-10-report-overlimit.png) |
| 9.11 | desktop | pass | Quiz confusions disambiguate duplicate names with the course; unique names stay alone. | ![](screenshots/t1-desktop-report.png) |
| 9.12-desktop | desktop | pass | Add filter, What opens a grouped checklist with one Apply; Who stays its own filter. | ![](screenshots/t9-12-audit-what-desktop.png) |
| 13.8 | desktop | pass | Noun-first audit labels present. | ![](screenshots/t9-12-audit-what-desktop.png) |
| 9.13 | desktop | pass | Switcher popover sits under its trigger; switching works; renaming updates the tab title at once. | ![](screenshots/t9-13-org-switcher.png) |
| 10.1 | desktop | pass | Keyboard to quick view (non-modal at desktop); Escape returns focus to the trigger. | none |
| 10.2 | desktop | pass | Native modal traps focus; Escape returns focus to the trigger. | none |
| 10.3 | desktop | pass | After keyboard Remove, focus lands on the table anchor, not body (the anchor is empty and unnamed; see general notes). | ![](screenshots/t10-3-focus-after-remove.png) |
| 10.4-generate | desktop | fail | Focus is BODY while a report generates (see B2). | none |
| 10.4-switcher-focus | desktop | fail | No visible focus indicator on switcher items (see B3). | ![](screenshots/t10-4-switcher-item-focus.png) |
| 10.4 | desktop | pass | Sort, Add filter, switcher and pagination work by keyboard with visible focus rings. | none |
| 11 | desktop | pass | Table captions, `scope=col`, `aria-sort`, region names, dialog names and checkbox labels all present. | none |
| 11-live-region | desktop | pass | Single-row actions raise no toast; the polite region carries the table summary (see general notes). | none |
| 12 | desktop | pass | Contrast sweep: nothing below 4.5:1 except avatar initials the script could not parse (visually dark on light). | none |
| 13.1-13.4 | desktop | pass | Link styling, Clear buttons, dashboard rows, row-button gaps and Downloads card as specified. | ![](screenshots/page-2026-11-05T17-38-01-835Z.png) |
| 13.5 | desktop | pass | Headers, Settings contents and role-based actions as specified; all action buttons `btn-sm` except the import page's "Upload and preview". | none |
| 13.7 | desktop | fail | Quick view Messages has two stacked rules (see B8). | ![](screenshots/educator_learner_quick_view.png) |
| 14 | desktop | pass | 14 doc screenshots saved at 1440x900 in the `first_class` theme (see Methodology). | ![](screenshots/educator_dashboard.png) |
| 1 | mobile (390) | pass | All 7 sections load, no console errors, `scrollWidth` 390; Filter and Sort sit side by side at 44px. | ![](screenshots/m-learners.png) |
| 7 | mobile | pass | Filter sheet: Inactive plus Show results adds the parameter; Reset clears it and closes the sheet. | ![](screenshots/m-learners-filter-sheet.png) |
| 9.12 | mobile | pass | Learners filter sheet and Sort menu; audit log sheet has six collapsed groups. | ![](screenshots/m-audit-filter-sheet.png) |
| 10.1 | mobile (375) | pass | Quick view is non-modal on the phone, matching the 5 Nov rule; the plan says modal (see general notes). | ![](screenshots/m375-quickview-modal.png) |
| 13.6 | mobile (375) | fail | Pager uses text buttons, not icon buttons (see B9). | ![](screenshots/page-2026-11-05T18-13-24-041Z.png) |
| 9.9 | mobile (375) | pass | Add staff role step, Move and Change cohorts sheets keep Cancel and the action visible; long-email title wraps; no sideways scroll. | ![](screenshots/m375-change-cohorts-long-email.png) |
| 9.5 | mobile (375) | skip | Not verifiable: the dev task backend runs the 501-learner job inline, so the running bar never shows. | ![](screenshots/m375-bulk-reactivate-after.png) |
| 9.4 | tablet | pass | Learners and cohorts tables show every column; the learners table scrolls inside its focusable region; `scrollWidth` 768. | ![](screenshots/t-learners-scrolled.png) |
| tablet-gap | tablet | fail | 160px empty band under tables (see B10). | ![](screenshots/t-cohorts-bottom.png) |

## Design check

No design states tested.

## Bugs

### B1: Bulk "More actions" menu closes itself on the first click

Manifestations: Test 2.1 (desktop). Same on the cohorts bulk bar.

![](screenshots/page-2026-11-05T17-39-35-558Z.png)

- Expected: one click on More actions opens the selection bar's menu.
- Actual: the menu opens (`aria-expanded` true at 34ms) and closes 12ms later. Opening focuses the first item, that focus scrolls the window, and the dropdown's `x-on:scroll.window='close'` shuts it. A second click opens it.

### B2: Focus drops to body while a keyboard-triggered report generates

Manifestations: Test 10.4-generate (desktop). No screenshot.

- Expected: after Generate report by keyboard, focus stays on or returns to the Generate button, never `<body>`.
- Actual: `document.activeElement` is BODY for the whole generation (4s or more, sampled every 500ms). Focus returns to Generate only once the finished row swaps in.

### B3: Organisation switcher menu items have no visible keyboard focus indicator

Manifestations: Test 10.4-switcher-focus (desktop).

![](screenshots/t10-4-switcher-item-focus.png)

- Expected: a keyboard-focused switcher item shows a visible focus ring (WCAG 2.4.7, 3:1 non-text contrast).
- Actual: the focused item has `outline: none` and only a faint grey row tint, barely distinguishable from its neighbours.

### B4: Learner Courses tab has no Deactivate/Reactivate on an individual registration

Manifestations: Test 3-courses-tab (desktop).

![](screenshots/page-2026-11-05T17-47-13-571Z.png)

- Expected: per plan Test 3, Deactivate and Reactivate on a registration from the learner page Courses tab.
- Actual: the Courses tab lists active registrations as progress cards with no registration actions and omits inactive ones. The actions live in the Overview tab's Registrations panel.

### B5: Single-learner Register and Add to cohort dialog titles are not questions

Manifestations: Test 3-register-single-title (desktop), two records: Register, and Add to cohort. No screenshot.

- Expected: every confirmation title is a question naming the object, like the bulk "Register 2 learners for Course Other?".
- Actual: "Register Ada Lovelace for a course" and "Add qa-nameless-learner@email.com to a cohort". There is no question mark, and the chosen course or cohort is never named.

### B6: Staff Roles cell reads "Added <date> by Not recorded"

Manifestations: Test 3-staff-added-by (desktop).

![](screenshots/educator_members.png)

- Expected: when the granting user is unknown, the sentence reads naturally, for example by dropping the "by" clause.
- Actual: "Added 2 Nov 2026 by Not recorded" on every role granted outside the UI.

### B7: Report quiz confusions say "1 of 1 learners"

Manifestations: Test 1-report-copy (desktop).

![](screenshots/t1-desktop-report.png)

- Expected: "1 of 1 learner".
- Actual: "Got it wrong: 1 of 1 learners" on every Quiz confusions card.

### B8: Quick view Messages section draws two stacked rules

Manifestations: Test 13.7 (desktop).

![](screenshots/educator_learner_quick_view.png)

- Expected: the Messages heading sits above one rule with space below it.
- Actual: two horizontal rules about 17px apart, one under the Messages heading row and a second above the message form.

### B9: Phone pager uses text buttons, not icon buttons

Manifestations: Test 13.6 (mobile, 375).

![](screenshots/page-2026-11-05T18-13-24-041Z.png)

- Expected: plan 13.6 asks for two small icon buttons (Previous, Next) around "Page X of Y".
- Actual: "← Previous" (102px) and "Next →" (77px) text buttons, 44px tall.

### B10: Empty 160px band under tables at tablet width

Manifestations: tablet-gap (tablet, 768). It predates this branch (spec 8).

![](screenshots/t-cohorts-bottom.png)

- Expected: no large empty gap between the last row and the table footer when nothing is selected.
- Actual: the scroll region keeps 160px of bottom padding at md width whenever bulk actions exist, to make room for the fixed selection bar, even with no selection.

### B11: Layout probe counts clipped text as overflowing ink

Manifestations: Test 1 (desktop), Test 1 (mobile), Test 9.4 (tablet).

![](screenshots/page-2026-11-05T17-38-01-835Z.png)
![](screenshots/m-staff.png)

- Expected: the probe flags only ink a user can see past the viewport.
- Actual: it flags sr-only spans, `.truncate` (ellipsis-clipped) text and tables inside horizontal scroll regions. Document `scrollWidth` equals the viewport on every flagged page.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1 | desktop | /educator/organisations/northside/dashboard | ![](screenshots/page-2026-11-05T17-38-01-835Z.png) | overflow: content ink spans x=256..1538 in a 1440px viewport (probe counts the clipped sr-only "No progress to show" spans; `scrollWidth` 1440, nothing visible spills) |
| 1 | desktop | /educator/organisations/northside/learners | ![](screenshots/t1-desktop-learners.png) | clean |
| 1 | desktop | /educator/organisations/northside/cohorts | ![](screenshots/t1-desktop-cohorts.png) | clean |
| 1 | desktop | /educator/organisations/northside/courses | ![](screenshots/t1-desktop-courses.png) | clean |
| 1 | desktop | /educator/organisations/northside/staff | ![](screenshots/t1-desktop-staff.png) | clean |
| 1 | desktop | /educator/organisations/northside/audit-log | ![](screenshots/t1-desktop-auditlog.png) | clean |
| 1 | desktop | /educator/organisations/northside/cohorts/<checkpoint>/__tabs/report | ![](screenshots/t1-desktop-report.png) | clean |
| 14 | desktop | /educator/organisations/northside/learners/<ada> | ![](screenshots/educator_learner_page.png) | clean |
| 14 | desktop | /educator/organisations/northside/cohorts/<cohort-a> | ![](screenshots/educator_cohort_overview.png) | clean |
| 14 | desktop | /educator/organisations/northside/cohorts/<cohort-a>/__tabs/history | ![](screenshots/educator_history.png) | clean |
| 1 | mobile | /educator/organisations/northside/learners | ![](screenshots/m-learners.png) | overflow: content ink spans x=0..447 in a 390px viewport (text inside `.truncate` spans clipped with an ellipsis; `scrollWidth` 390) |
| 1 | mobile | /educator/organisations/northside/staff | ![](screenshots/m-staff.png) | overflow: content ink spans x=0..821 in a 390px viewport (long email in a `.truncate` span; `scrollWidth` 390) |
| 1 | mobile | /educator/organisations/northside/cohorts/<checkpoint>/__tabs/report | ![](screenshots/m-report.png) | overflow: content ink spans x=0..908 in a 390px viewport (report tables inside focusable horizontal scroll regions; `scrollWidth` 390) |
| 1 | mobile | /educator/organisations/northside/dashboard | ![](screenshots/m-dashboard.png) | overflow: content ink spans x=0..480 in a 390px viewport (sr-only "No progress to show") |
| 1 | mobile | /educator/organisations/northside/cohorts | ![](screenshots/m-cohorts.png) | clean |
| 1 | mobile | /educator/organisations/northside/audit-log | ![](screenshots/m-auditlog.png) | clean |
| 9.4 | tablet | /educator/organisations/northside/learners | ![](screenshots/t-learners.png) | overflow: content ink spans x=0..970 in a 768px viewport (table inside its horizontal scroll region by design; `scrollWidth` 768) |
| 9.4 | tablet | /educator/organisations/northside/cohorts | ![](screenshots/t-cohorts.png) | overflow: content ink spans x=0..770 in a 768px viewport (2px; `scrollWidth` 768, region 718/718) |

## Data changes

| Via | What |
|---|---|
| sdd:qa-data-helper | Ran the plan's six seed commands (`educator_interface_seed`, cohort, learner, bulk and member administration scenarios, `educator_polish_scenario`). The bulk scenario reset deleted 35 earlier @qa.test users. |
| UI during the run | Registered Ada Lovelace and Bea Blue for Course Other then deactivated it; registered Ada for Course Hid; deactivated Bulk 01 Alpha (reason "QA side-effect check"); added qa-nameless-learner to Cohort Empty; deleted Cohort Removed; created and deleted "QA Gone Cohort". |
| UI during the run | Created and deleted cohorts "QA Pick Gone 1/2/3"; Cohort B deactivated then reactivated; Cohort Old reactivated (now active); Cohort Empty renamed and renamed back; import preview of 2 existing members (no commit). |
| UI during the run | Bulk-deactivated then bulk-reactivated the 501 learners of DemoDev "QA Over 500 Cohort" (net unchanged). |

## Bug status

| Bug | Status |
|---|---|
| B1 | **FIXED** (commit: 57ebf7c88) — Bulk "More actions" menu closes itself on the first click |
| B2 | **FIXED** (commit: 7a45fe973) — Focus drops to body while a keyboard-triggered report generates |
| B3 | **FIXED** (commit: 4727b11cf) — Organisation switcher menu items have no visible keyboard focus indicator |
| B4 | **UNRESOLVED** — Learner Courses tab has no Deactivate/Reactivate on an individual registration (reason: placement decision; plan puts the actions on the Courses tab, code keeps them in the Overview Registrations panel) |
| B5 | **UNRESOLVED** — Single-learner Register and Add to cohort dialog titles are not questions (reason: plan and code disagree on the single-row title wording; needs the intended wording) |
| B6 | **UNRESOLVED** — Staff Roles cell reads "Added <date> by Not recorded" (reason: copy decision: what the sentence says when the granter is unknown) |
| B7 | **UNRESOLVED** — Report quiz confusions say "1 of 1 learners" (reason: fix budget exhausted this run) |
| B8 | **UNRESOLVED** — Quick view Messages section draws two stacked rules (reason: fix budget exhausted this run) |
| B9 | **UNRESOLVED** — Phone pager uses text buttons, not icon buttons (reason: plan 13.6 and code disagree; choose icon-only or labelled pager) |
| B10 | **UNRESOLVED** — Empty 160px band under tables at tablet width (reason: decide how room for the fixed selection bar is reserved; predates this branch) |
| B11 | **UNRESOLVED** — Layout probe counts clipped text as overflowing ink (reason: decide whether the generic probe should skip sr-only, truncated and scroll-region text) |

## General notes

- The plan is out of date on 10.1: a quick view is non-modal on phones too, by the 5 Nov rule.
- The plan is out of date on 8.1: rows have no row menus any more. The same applies to the row-menu half of Test 2.4.
- 9.5 could not be verified. The dev task backend runs bulk jobs inline (a 44.7s request), so the running bar never shows.
- "Clear all" keeps the search text, while "Clear filters" clears it.
- After a keyboard Remove, focus lands on an empty, unnamed table anchor.
- Single-row actions announce the table summary ("No results") in the polite region rather than the action.
- Filter chips and Add filter are `<summary>` elements exposed as "generic".
- Stale Register and Add learner dialogs open normally and refuse only on submit.
- The import page's "Upload and preview" button is full-size.
- With the quick view open at desktop, the learners table scrolls inside its region.

status: ok · reason: 11 bugs — 3 fixed, 8 unresolved; report rendered, screenshots verified
