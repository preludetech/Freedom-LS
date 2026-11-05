# Frontend QA report: educator-interface-12-docs-and-polish

## Summary

54 test records: 43 pass, 10 fail, 1 skip (9.5, partial). 9 bugs documented (B1 to B9), all UNRESOLVED. Smoke gate passed. Layout probe: 19 records, 18 clean or false-positive, 1 flagged failure (13.4-phone).

## Methodology

- Driven with Playwright MCP against the dev server.
- Viewports: 1920 and 1440 desktop, 390 and 375 phone, 768 tablet.
- Default theme got the full pass. The first_class theme got a reduced pass (server restarted with FLS_THEME=first_class, CSS rebuilt): all seven sections at 1440 and 390, badges, 9.7 and 9.10.
- Screenshots were collected into `screenshots/` beside this report. Every image referenced here was confirmed to exist there.
- The Test 14 doc screenshots (`educator_*.png`) are also in `screenshots/`.

## Diff scoping

Class: FULL (front-end templates and static files changed; 505 changed files, including base templates, cotton components, comms partials, course_applications partials and educator_interface templates). Skipped: nothing.

## Smoke gate

Pass. Pages checked: `/`, `/educator/organisations/demodev/dashboard`, `/educator/organisations/demodev/learners`.

## Results by test

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 2.3 | desktop | pass | none | unregister_from_course and cohorts unregister actions return 404 for GET, HX GET and HX POST. |
| 1.0-members-404 | desktop | pass | none | `/members` is 404 and `/staff` is 200; plan URLs lack the `organisations/` segment. |
| 13.2 | desktop | fail | ![](screenshots/page-2026-11-05T08-24-19-329Z.png) | Dashboard needs-attention avatar sits about 25px below the name (B2). |
| 2.1 | desktop | pass | ![](screenshots/page-2026-11-05T08-26-56-754Z.png) | Learners bulk Deactivate a course registration works; title, Cancel focus, disabled at 0 and result dialog correct. |
| 2.2 | desktop | pass | none | Cohorts bulk Deactivate a course registration is a bar button with the correct title; cancelled. |
| 2.4 | desktop | pass | none | "Register for a course" wording correct; the learners list has no row menu, so those plan parts do not apply. |
| 3-learner-settings | desktop | pass | ![](screenshots/page-2026-11-05T08-31-05-489Z.png) | Reactivate, Deactivate and Resend setup email dialogs correct; History shows the typed reason. |
| 3-learner-overview | desktop | pass | ![](screenshots/page-2026-11-05T08-33-48-522Z.png) | Remove from cohort and Move dialogs correct; Move disabled until a destination is chosen. |
| 3-repeat-submission | desktop | pass | ![](screenshots/page-2026-11-05T08-31-43-802Z.png) | Stale-tab repeat Deactivate shows the "already changed" dialog (422), no error page. |
| 13.5 | desktop | fail | ![](screenshots/page-2026-11-05T08-31-04-478Z.png) | Settings intro offers "deactivate" on an inactive learner (B6). |
| 3-cohort-settings | desktop | pass | ![](screenshots/page-2026-11-05T08-34-15-628Z.png) | Edit, Deactivate/Reactivate and Delete (empty cohort only) dialogs correct; delete lands on the cohorts list. |
| 9.1 | desktop | pass | ![](screenshots/page-2026-11-05T08-34-15-628Z.png) | Reactivate from Settings stays on the tab, badge gone, focus on header. |
| 3-staff | desktop | pass | ![](screenshots/page-2026-11-05T08-34-45-479Z.png) | Staff Deactivate role, Deactivate and Reactivate dialogs correct; no intro paragraph. |
| 3-staff-copy | desktop | fail | ![](screenshots/page-2026-11-05T08-34-45-479Z.png) | Staff copy leaks "Not recorded" and "Whole organisation" placeholders into sentences (B7). |
| 5 | desktop | pass | none | Status chips use the right styles and all carry text. |
| 9.3 | desktop | pass | ![](screenshots/page-2026-11-05T08-35-45-175Z.png) | Educator emails shown exactly as stored. |
| 9.11 | desktop | pass | ![](screenshots/page-2026-11-05T08-36-19-617Z.png) | Quiz names disambiguated with course name only where they collide. |
| 13.4 | desktop | pass | ![](screenshots/educator_cohort_report.png) | Downloads card Generate report works by keyboard and focus returns to the button. |
| 9.10 | desktop | pass | ![](screenshots/page-2026-11-05T08-36-43-437Z.png) | Over-limit cohort shows the notice, disabled Generate, no red alert or setting name. |
| 4.1 | desktop | pass | ![](screenshots/page-2026-11-05T08-37-13-876Z.png) | Role-based nav and 404s correct; empty-state copy for audit log and staff correct. |
| 4.2 | desktop | pass | none | No-match states show "No ... match these filters." with a Clear filters link; not applicable to tabs without search. |
| 6 | desktop | pass | ![](screenshots/page-2026-11-05T08-40-29-920Z.png) | Nameless learner is identified by email across list, quick view, page, report and history. |
| 3-focus-after-confirm | desktop | fail | ![](screenshots/page-2026-11-05T08-41-09-834Z.png) | Focus lands on an unnamed empty table anchor after a row is replaced (B3). |
| 9.12-desktop | desktop | pass | ![](screenshots/page-2026-11-05T08-39-03-460Z.png) | Audit log What is a grouped checklist with one Apply; Who is a single-choice list. |
| 13.8 | desktop | pass | ![](screenshots/page-2026-11-05T08-39-03-460Z.png) | Audit log labels are noun-first. |
| 7-desktop | desktop | pass | ![](screenshots/page-2026-11-05T08-41-54-398Z.png) | Status chip and Clear all return to the default Active+Pending. |
| 8 | desktop | pass | ![](screenshots/page-2026-11-05T08-42-27-534Z.png) | Stale deleted-item actions show "no longer available" dialog; 8.5 404 bodies byte-identical; 8.1 not applicable. |
| 9.2 | desktop | pass | none | Stale inactive-cohort actions show the specific "Cohort B is inactive" messages. |
| 9.8 | desktop | pass | ![](screenshots/page-2026-11-05T08-43-56-332Z.png) | Deleted destination cohort gives "Choose a cohort from the list." with no UUID. |
| 3-bulk-body | desktop | fail | ![](screenshots/page-2026-11-05T08-43-51-095Z.png) | Bulk confirmation bodies repeat the title and omit what is kept and how to undo (B8). |
| 9.13 | desktop | pass | ![](screenshots/page-2026-11-05T08-45-38-704Z.png) | Org switcher opens under its trigger; cohort rename updates h1 and title immediately. |
| 9.6 | desktop | pass | ![](screenshots/page-2026-11-05T08-47-40-061Z.png) | Import preview and result copy correct (no "0 new accounts" or "0 rows" lines). |
| 9.7 | desktop | pass | ![](screenshots/page-2026-11-05T08-47-10-326Z.png) | File input is bordered with a bordered Choose File button (default theme). |
| 10.1-desktop | desktop | pass | ![](screenshots/page-2026-11-05T08-47-56-224Z.png) | Quick view opens by keyboard, focus on heading, Escape returns to trigger. |
| 10.2 | desktop | pass | none | Staff "Deactivate role" dialog by keyboard: focus trapped, Escape returns focus to trigger. |
| 10.4-desktop | desktop | pass | none | Focus rings visible on first 40 tab stops; sort and pagination by keyboard work (anchor focus noted in B3). |
| 11-desktop | desktop | pass | none | Table semantics, region names, aria-sort and live region correct. |
| 13.7 | desktop | pass | ![](screenshots/page-2026-11-05T08-48-44-691Z.png) | Quick view Messages heading, icon-only Send and removed disclosure sentence correct. |
| 13.1 | desktop | fail | ![](screenshots/page-2026-11-05T08-48-44-691Z.png) | Cohort links in learners table and quick view are font-medium, not bold (B5). |
| 1.3-mockups | desktop | pass | ![](screenshots/mockup-dashboard.png) | Mockup comparison at 1440: ours is less dense; see General notes. |
| 1.1 | mobile | pass | ![](screenshots/page-2026-11-05T08-51-27-317Z.png) | All seven sections at 390: no console errors, no sideways scroll, Filter and Sort side by side. |
| 13.2 | mobile | fail | ![](screenshots/page-2026-11-05T08-51-25-511Z.png) | Avatar sits about 75px below the learner name on a phone (B2). |
| 13.6 | mobile | fail | ![](screenshots/page-2026-11-05T08-52-00-834Z.png) | Selection bar has full-size stacked buttons and a text pager (B4). |
| 9.5 | mobile | skip | ![](screenshots/page-2026-11-05T08-53-13-829Z.png) | PARTIAL: immediate task backend runs the 583-learner bulk in-request, so the background bar cannot appear. |
| 9.9 | mobile | pass | ![](screenshots/page-2026-11-05T08-53-38-878Z.png) | Dialog footers visible without scrolling at 375; long email dialog has no sideways scroll. |
| 9.12 | mobile | pass | ![](screenshots/page-2026-11-05T08-53-55-509Z.png) | Filter sheet, separate Sort menu and audit log What groups correct. |
| 7-phone | mobile | pass | ![](screenshots/page-2026-11-05T08-53-55-509Z.png) | Sheet Reset returns to an empty querystring; chip reads "Status: Active, Pending". |
| 10.1-phone | mobile | pass | ![](screenshots/page-2026-11-05T08-54-29-623Z.png) | Quick view is a modal with scrim; focus stays inside; Escape returns focus. |
| 13.3 | mobile | pass | ![](screenshots/page-2026-11-05T08-54-46-794Z.png) | Card action buttons are btn-sm, 44px tall on phones, 8px apart. |
| 9.4 | tablet | pass | ![](screenshots/page-2026-11-05T08-55-21-952Z.png) | Learners and cohorts tables show every column; region scrolls inside itself. |
| tablet-squeeze | tablet | fail | ![](screenshots/page-2026-11-05T08-55-21-952Z.png) | Cohorts and Courses columns squeezed to a few words wide (B9). |
| tablet-nav | tablet | pass | ![](screenshots/page-2026-11-05T08-55-50-763Z.png) | 768 gets the hamburger drawer listing all sections; Escape closes it. |
| 1.1-first_class | desktop | pass | ![](screenshots/page-2026-11-05T08-57-54-536Z.png) | Reduced first_class pass: sections load, contrast ratios pass; Report tab sideways scroll at 390 (see B1). |
| 13.4-phone | mobile | fail | ![](screenshots/page-2026-11-05T08-58-43-845Z.png) | Downloads table spills past the card and the page scrolls sideways (B1). |

## Design check

No design states tested. The plan has no `-design` tests; a mockup comparison is in General notes.

## Bugs

### B1: Report tab Downloads table overflows the page on phones

Manifestations: 13.4-phone (mobile).

![](screenshots/page-2026-11-05T08-58-43-845Z.png)

Expected: At 390 the Downloads table (Generated / By / Download) fits the card or scrolls inside its own region; the page never scrolls sideways (Test 1: scrollWidth <= innerWidth).

Actual: With generated reports listed, the 473px table sits in a wrapper with overflow visible; Download buttons are cut off at the card edge and documentElement.scrollWidth is 506 at 390 (both themes).

### B2: Dashboard needs-attention avatar is centred on the whole row, not beside the name

Manifestations: 13.2 (desktop), 13.2 (mobile).

![](screenshots/page-2026-11-05T08-24-19-329Z.png)
![](screenshots/page-2026-11-05T08-51-25-511Z.png)

Expected: Each row shows the learner as a person link: avatar chip beside the bold name (Test 13.1/13.2), with the cohort blocks under/after it.

Actual: The row `<li>` uses items-center, so the avatar is vertically centred on the multi-line row: about 25px below the name at desktop and about 75px below it on a phone.

### B3: Focus after a row is replaced, a sort or a page change lands on an unnamed empty table anchor

Manifestations: 3-focus-after-confirm (desktop), 10.4-desktop (desktop).

![](screenshots/page-2026-11-05T08-41-09-834Z.png)

Expected: After confirming an action whose row is replaced, focus goes to the table heading (or the row's trigger); focus is visible and announced.

Actual: Focus moves to `<div tabindex=-1 data-table-anchor>` at the top of the table: zero height, no accessible name, no visible focus ring. Seen after Remove from cohort on the learner page and after sorting or paginating the learners table.

### B4: Phone selection bar uses full-size stacked buttons and a text pager

Manifestations: 13.6 (mobile).

![](screenshots/page-2026-11-05T08-52-00-834Z.png)

Expected: At 375 the bulk action buttons are small, and the pager is two small icon-only buttons (Previous, Next) around "Page X of Y".

Actual: Bulk buttons are full-size btn (16px), one per row, making the bar about 250px tall; the pager shows text "Previous"/"Next" buttons with arrows rather than icon-only buttons.

### B5: Cohort names in the learners table and quick view are medium weight, not the person-link bold

Manifestations: 13.1 (desktop).

![](screenshots/page-2026-11-05T08-48-44-691Z.png)

Expected: Cohort names inside rows (learners table, dashboard rows, quick view) use the person-link style: bold, text colour, no underline, blue on hover.

Actual: Learners table and quick view cohort links are font-medium (500); dashboard rows use bold (700).

### B6: Learner Settings intro offers 'deactivate' for an inactive learner

Manifestations: 13.5 (desktop).

![](screenshots/page-2026-11-05T08-31-04-478Z.png)

Expected: The Settings tab intro names only actions the tab offers for this learner's state.

Actual: For inactive Rae Removed the intro reads "Change Rae Removed's name, add them to a cohort, register them for a course or deactivate them." while the button is Reactivate.

### B7: Staff copy shows table placeholder labels inside sentences

Manifestations: 3-staff-copy (desktop).

![](screenshots/page-2026-11-05T08-34-45-479Z.png)

Expected: Role lines and dialog bodies read as sentences: e.g. "Added 5 Nov 2026" when no actor is recorded, and "Organisation admin for the whole organisation".

Actual: Staff rows read "Added 5 Nov 2026 by Not recorded"; the Reactivate dialog reads "These roles take effect again: Organisation admin on Whole organisation."

### B8: Bulk confirmation bodies repeat the title and omit what changes, what is kept and how to undo

Manifestations: 3-bulk-body (desktop).

![](screenshots/page-2026-11-05T08-43-51-095Z.png)
![](screenshots/page-2026-11-05T08-26-56-754Z.png)

Expected: Test 3: every confirmation body says what stops, what is kept and how to undo it; a header states each fact once.

Actual: Bulk Add to cohort: title "Add 1 learner to QA Temp A?" body "Add 1 learner to QA Temp A." and nothing else. Bulk "Deactivate a course registration" and Register for a course also open by restating the title.

### B9: Learners table squeezes the Cohorts and Courses columns at tablet width and with the quick view docked

Manifestations: tablet-squeeze (tablet).

![](screenshots/page-2026-11-05T08-55-21-952Z.png)
![](screenshots/page-2026-11-05T08-48-44-691Z.png)

Expected: Columns keep a readable width; the table scrolls inside its region rather than crushing columns ("Space: no region is squeezed").

Actual: At 768 (and at 1440 with the quick view docked) course titles wrap every one or two words and rows grow to about 250px, although the region already scrolls sideways.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1.1 | desktop | /educator/organisations/northside/dashboard | ![](screenshots/page-2026-11-05T08-24-19-329Z.png) | clean (probe false positive: overflow from clipped sr-only "No progress to show"; scrollWidth == innerWidth) |
| 1.1 | desktop | /educator/organisations/northside/learners | ![](screenshots/page-2026-11-05T08-24-21-358Z.png) | clean |
| 1.1 | desktop | /educator/organisations/northside/cohorts | ![](screenshots/page-2026-11-05T08-24-23-020Z.png) | clean |
| 1.1 | desktop | /educator/organisations/northside/courses | ![](screenshots/page-2026-11-05T08-24-24-406Z.png) | clean |
| 1.1 | desktop | /educator/organisations/northside/staff | ![](screenshots/page-2026-11-05T08-24-26-071Z.png) | clean |
| 1.1 | desktop | /educator/organisations/northside/audit-log | ![](screenshots/page-2026-11-05T08-24-27-752Z.png) | clean |
| 1.1 | desktop | /educator/organisations/northside/cohorts/<CohortA>/__tabs/report | ![](screenshots/page-2026-11-05T08-24-29-153Z.png) | clean |
| 9.3 | desktop | /educator/organisations/northside/cohorts/<QA Checkpoint> | ![](screenshots/page-2026-11-05T08-35-45-175Z.png) | clean |
| 1.1 | mobile | /educator/organisations/northside/dashboard | ![](screenshots/page-2026-11-05T08-51-25-511Z.png) | clean (probe flag 'overflow x=0..480' from clipped sr-only text; no sideways scroll) |
| 1.1 | mobile | /educator/organisations/northside/learners | ![](screenshots/page-2026-11-05T08-51-27-317Z.png) | clean (probe flag 'overflow x=0..447' from text clipped by truncate/sr-only inside cards; no sideways scroll) |
| 1.1 | mobile | /educator/organisations/northside/cohorts | ![](screenshots/page-2026-11-05T08-51-29-035Z.png) | clean |
| 1.1 | mobile | /educator/organisations/northside/courses | ![](screenshots/page-2026-11-05T08-51-30-572Z.png) | clean |
| 1.1 | mobile | /educator/organisations/northside/staff | ![](screenshots/page-2026-11-05T08-51-32-561Z.png) | clean (probe flag 'overflow x=0..821' from the 87-character email, truncated with an ellipsis; no sideways scroll) |
| 1.1 | mobile | /educator/organisations/northside/audit-log | ![](screenshots/page-2026-11-05T08-51-34-331Z.png) | clean |
| 1.1 | mobile | /educator/organisations/northside/cohorts/<CohortA>/__tabs/report | ![](screenshots/page-2026-11-05T08-51-35-850Z.png) | clean (probe flag 'overflow x=0..608' from the summary table inside its own scrolling region; no sideways page scroll) |
| 9.4 | tablet | /educator/organisations/northside/learners | ![](screenshots/page-2026-11-05T08-55-21-952Z.png) | clean (probe flag 'overflow x=0..971' is the table inside its own scrolling region; no page sideways scroll) |
| 9.4 | tablet | /educator/organisations/northside/cohorts | ![](screenshots/page-2026-11-05T08-55-23-866Z.png) | clean (probe flag 'overflow x=0..771' (3px, region edge); no page sideways scroll) |
| 1.1 | tablet | /educator/organisations/northside/dashboard | ![](screenshots/page-2026-11-05T08-55-25-293Z.png) | clean (probe flag 'overflow x=0..874' from clipped sr-only text; no page sideways scroll) |
| 13.4-phone | mobile | /educator/organisations/northside/cohorts/<QA Checkpoint>/__tabs/report | ![](screenshots/page-2026-11-05T08-58-43-845Z.png) | FLAG: documentElement.scrollWidth 506 > innerWidth 390: Downloads table TH 'Download' right edge 506 with no clipping ancestor (B1) |

## Data changes

| What | Via |
|---|---|
| Ran the six seed commands (educator_interface_seed, cohort_administration, learner_administration, bulk_operations, member_administration, educator_polish) on site DemoDev. Main org northside; second org southside; empty-staff org eastside; quietside with no audit entries. | sdd:qa-data-helper |
| Created QA Over 500 Cohort (13fb3b65...) in org demodev with 501 learners via qa_create_report_cohort, because the running server (config.settings_dev) ignores settings_local's REPORTS_MAX_LEARNERS=5. | sdd:qa-data-helper |
| Created a nameless staff user with an 87-char email, cohort_viewer on Cohort B (northside). | sdd:qa-data-helper |
| Bulk-registered Ada Lovelace and Bea Blue (northside) for Course Other, then deactivated that registration (Test 2.1). | QA run through the UI |
| Reactivated then deactivated Rae Removed (with reason); deactivated then reactivated qa-nameless-learner@email.com. Net state unchanged. | QA run through the UI |
| Removed qa-nameless-learner from Cohort C Renamed twice and re-added each time; reactivated then re-deactivated Cohort Old; deleted the empty Cohort Removed; generated two PDF reports for QA Checkpoint Cohort. | QA run through the UI |
| Deleted Cohort Empty (Test 8); created and deleted QA Temp A and QA Temp B (Test 9.8); deactivated/reactivated Cohort B several times (net active); renamed Cohort C and back. | QA run through the UI |
| Bulk-registered all 583 demodev learners for Course Other (Test 9.5); imported qa.import.new1@qa.test (Imogen Import) into northside (Test 9.6). | QA run through the UI |

## Bug status

| Bug | Status |
|---|---|
| B1 | **FIXED** (commit: 5465e96a6) — Report tab Downloads table overflows the page on phones. Re-verified at 390: scrollWidth 390, table scrolls in its own region ([after](screenshots/page-2026-11-05T09-16-32-184Z.png)). |
| B2 | **FIXED** (commit: d993d2277) — Dashboard needs-attention avatar is centred on the whole row, not beside the name. Re-verified: avatar/name centre gap 0–2px on dashboard, cohort Overview and Report at 1440 and 390 ([after](screenshots/page-2026-11-05T09-31-06-203Z.png)). |
| B3 | **UNRESOLVED** — Focus after a row is replaced, a sort or a page change lands on an unnamed empty table anchor (reason: the code deliberately focuses a data-table anchor while the plan says the table heading; which target is right is a product/a11y decision) |
| B4 | **UNRESOLVED** — Phone selection bar uses full-size stacked buttons and a text pager (reason: icon-only pager vs labelled buttons and button size vs 44px touch rule need a design decision) |
| B5 | **FIXED** (commit: ffe4b7a7b) — Cohort names in the learners table and quick view are medium weight, not the person-link bold. Re-verified: weight 700, no underline in table and quick view. |
| B6 | **UNRESOLVED** — Learner Settings intro offers 'deactivate' for an inactive learner (reason: copy wording decision) |
| B7 | **UNRESOLVED** — Staff copy shows table placeholder labels inside sentences (reason: copy wording decision) |
| B8 | **UNRESOLVED** — Bulk confirmation bodies repeat the title and omit what changes, what is kept and how to undo (reason: needs per-action copy decisions) |
| B9 | **UNRESOLVED** — Learners table squeezes the Cohorts and Courses columns at tablet width and with the quick view docked (reason: column-width/layout design decision; fix budget also exhausted) |

## General notes

- Rebase: pre-step rebase onto origin/main replayed 95 commits with 0 conflicts and the lost-change check passed. Upstream changes were tests and spec ideas only (no shared front-end), so the rebase front-end check is subsumed by this full QA run. Verification: targeted tier 3939 passed; pre-commit clean; branch force-pushed (b2ace529f).
- Not run / partial: the Test 12 contrast sweep sampled badges, muted text, links, the over-limit notice and filter chips in both themes (all pass; the "Not started" muted chip is 4.79:1 in first_class, a narrow pass); focus-ring and border (3:1) sampling was not exhaustive. The first_class theme got a reduced pass (all sections at 1440 and 390, badges, 9.7, 9.10), not the full matrix. 9.5 is PARTIAL (immediate task backend). Test 8.1 and the row-menu parts of 2.4/10.2 do not apply: no table defines row menus. Test 4.2 does not apply to courses, cohort Courses/History, or learner Courses/History tabs (no search or filter).
- Plan corrections: URLs are `/educator/organisations/<org>/...` not `/educator/<org>/...`; the import page is `/learners/import/` (the slash-less URL in Test 9.7 is a 404). The over-limit case used a 501-learner cohort because the dev server (config.settings_dev) does not read settings_local's REPORTS_MAX_LEARNERS=5.
- Observations with no action: every person link carries its own inline `<style>@layer components{.panel-avatar-*}</style>` block (repeated per row, harmless visually); the Cohort report card's Refresh is a full-size ghost button beside 14px text while Generate report is btn-sm; the dashboard tile "7 Cohorts" places its label lower than the sibling tile with a subtitle; the import page helper line "email is required; cohort is matched by name" has no full stop; the Playwright aria snapshot reports the native `<summary>` "Add filter" as generic; the first More actions click after a scroll-into-view closes immediately because the menu closes on window scroll (Playwright artefact, not reproducible by mouse).
- Mockup comparison (Educator Dashboard.dc.html at 1440, not a pixel reference): the mockup puts each needs-attention learner on one compact row (avatar, name with the cohort under it, status badge, action); ours uses rows about 99px tall over three lines with the cohort block beside the name, so it is noticeably less dense. Tiles: the mockup puts an uppercase label above the figure; ours puts the label under the figure. The learners and cohorts mockups were not opened.

status: ok · reason: 9 bugs — 3 fixed, 6 unresolved; report rendered, screenshots verified
