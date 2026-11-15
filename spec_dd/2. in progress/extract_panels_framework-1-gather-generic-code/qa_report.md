# Frontend QA report: extract_panels_framework-1-gather-generic-code

The run recorded 76 test results from plan `3. frontend_qa.md` (Tests 1-13): 70 passed, 4 failed and 2 were skipped. The 4 failing results come from 3 distinct bugs. B1 is the quick view discard prompt body sitting on the panel edge (Test 6.3). B2 is the bulk "Add to cohort" picker keeping the previous target's confirmation (Test 7.8). B3 is the cohort report summary tables truncating learner names on phone and tablet (Test 9.6, two viewports). The smoke gate passed. No bug is resolved in this report.

## Methodology

- Playwright MCP at 1920x1080 (desktop), 375x812 (mobile) and 768x1024 (tablet). Screenshots were collected into `screenshots/`.
- Shots whose basename starts with `page-nojs-` (JS off) or `page-learner-` (learner login) were taken in separate browser contexts with `page.screenshot`, because the MCP screenshot tool only captures the main session.
- No screenshot compression was needed.
- Screenshot check: every basename referenced in this report exists in `screenshots/` (checked with Glob). Missing: none.

## Diff scoping

Class: FULL. Triggered by template and static changes (386 changed files; templates/ and static/ under `freedom_ls/panel_framework`, `freedom_ls/educator_interface`, `freedom_ls/comms`, `freedom_ls/base`, and `tailwind.components.css`). Skipped: nothing. Everything ran, at desktop, mobile and tablet.

## Smoke gate

Status: pass. Pages checked: `/`, `/educator/organisations/demodev/dashboard`, `/educator/organisations/demodev/learners/`, `/educator/organisations/demodev/cohorts/`. No failure.

## Test results

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 12.2 | desktop | pass | Sidebar docked 256px column, no collapse control at 1920, survives reload | ![](screenshots/page-2026-11-15T13-00-46-486Z.png) |
| 8.2 | desktop | pass | "When" filter options work; 7d shows only 14-15 Nov | ![](screenshots/page-2026-11-15T13-01-08-754Z.png) |
| 8.3 | desktop | pass | Bogus `audit_log-when` returns 200 with full list | |
| 8.1 | desktop | pass | Inactive cohorts hidden by default; Show inactive and chip removal work | ![](screenshots/page-2026-11-15T13-01-53-248Z.png) |
| 9.1 | desktop | pass | Skeleton placeholders, single-link stat tile, attention row quick view button | ![](screenshots/page-2026-11-15T13-02-40-815Z.png) |
| 6.1-6.2 | desktop | pass | Quick view opens beside content; Close 44x44; focus returns to trigger | ![](screenshots/page-2026-11-15T13-02-40-815Z.png) |
| 6.3 | desktop | **fail** | Discard prompt works, but its body sentence sits at the panel edge (B1) | ![](screenshots/page-2026-11-15T13-03-06-076Z.png) |
| 1.1-1.4 | desktop | pass | Deactivate cohort dialog title, body, reason field, buttons and focus correct | ![](screenshots/page-2026-11-15T13-03-57-611Z.png) |
| 1.5-1.6 | desktop | pass | Discard changes prompt, Keep editing, Esc re-prompt behave | ![](screenshots/page-2026-11-15T13-04-11-993Z.png) |
| 1.7 | desktop | pass | 520-char reason returns 422, dialog stays open with field error | ![](screenshots/page-2026-11-15T13-04-30-648Z.png) |
| 1.8-1.9 | desktop | pass | Cohort deactivated, history entry with reason; loading label present | |
| 2.1 | desktop | pass | Reactivate dialog; "Reactivating…" when throttled | |
| 2.2 | desktop | pass | Learner Deactivate and Reactivate dialogs correct | |
| 2.3 | desktop | pass | Resend setup email confirm and send work | |
| 3.5 | desktop | pass | Second resend refused with 422 and one footer Close | ![](screenshots/page-2026-11-15T13-07-44-815Z.png) |
| 2.4 | desktop | pass | Registration row dialogs act on their own rows | ![](screenshots/page-2026-11-15T13-08-27-347Z.png) |
| 2.5 | desktop | pass | Row buttons named per learner; Remove confirm is btn-error | |
| 2.6-2.7 | desktop | pass | Staff dialogs have reason fields; loading labels end in a single "…" | ![](screenshots/page-2026-11-15T13-08-48-734Z.png) |
| 3.1-3.2 | desktop | pass | Stale cohort tabs show "already inactive/active" with one Close | ![](screenshots/page-2026-11-15T13-09-38-891Z.png) |
| 3.3 | desktop | pass | Stale learner Deactivate shows "was already changed" | |
| 3.4 | desktop | skip | Not run: needs emailed setup link; 15-minute resend limit (3.5) answers first | |
| 3.6-3.7 | desktop | pass | Stale staff action shows "This is no longer available" | ![](screenshots/page-2026-11-15T13-10-11-781Z.png) |
| 4.1-4.2 | desktop | pass | Delete cohort dialog correct; no Delete on cohort with learners | |
| 4.3 | desktop | pass | Stale delete shows red alert box, Delete button gone | ![](screenshots/page-2026-11-15T13-11-29-923Z.png) |
| 4.4 | desktop | pass | Delete redirects to cohorts, cohort gone | |
| 5.1 | desktop | pass | Move picker disabled reason in body; enables on choice | ![](screenshots/page-2026-11-15T13-12-56-323Z.png) |
| 5.2 | desktop | pass | Stale move shows "no longer in" message with one Close | |
| 5.3 | desktop | pass | Add staff: error summary, role step, searchable cohort checklist, Cancel without prompt | ![](screenshots/page-2026-11-15T13-14-39-523Z.png) |
| 5.4 | desktop | pass | Change cohorts uses same checklist; unchanged submit shows "wasn't made" | ![](screenshots/page-2026-11-15T13-15-08-520Z.png) |
| 5.5 | desktop | pass | Add learner result with Close and Add another | ![](screenshots/page-2026-11-15T13-15-58-612Z.png) |
| 5.6 | desktop | pass | Messages composer on panel padding; oversight thread read-only in dialog | ![](screenshots/page-2026-11-15T13-16-54-176Z.png) |
| 5.7 | desktop | pass | Add to cohort re-renders; empty submit returns 422 with summary | ![](screenshots/page-2026-11-15T13-13-31-233Z.png) |
| 11.6 | desktop | pass | Adding a learner refreshes the filtered table; search kept | |
| 7.1 | desktop | pass | Selection bar and bulk Deactivate dialog | ![](screenshots/page-2026-11-15T13-17-31-674Z.png) |
| 7.2 | desktop | pass | Bulk resend shows skipped count and result | ![](screenshots/page-2026-11-15T13-17-46-120Z.png) |
| 7.3 | desktop | pass | Confirm disabled when all skipped, reason in body | ![](screenshots/page-2026-11-15T13-18-04-830Z.png) |
| 7.4 | desktop | pass | Changed selection returns 422 with amber notice | ![](screenshots/page-2026-11-15T13-20-32-535Z.png) |
| 7.5 | desktop (JS off) | pass | Fallback Deactivate opens modal over learners page; Close/Cancel are links | ![](screenshots/page-nojs-2026-11-15T13-22-50-948Z.png) |
| 7.5 | mobile (JS off) | pass | Navigation is a block above content, no sideways scroll | ![](screenshots/page-nojs-2026-11-15T13-22-52-645Z.png) |
| 7.6 | desktop | pass | Inline and background bulk runs, notification lists result | ![](screenshots/page-2026-11-15T13-21-38-483Z.png) |
| 7.7 | desktop | pass | Cohorts bulk bar action order correct | |
| 7.8 | desktop | **fail** | Re-choosing the empty option does not re-render the dialog (B2) | ![](screenshots/page-2026-11-15T13-18-23-065Z.png) |
| 8.4 | desktop | pass | Learners toolbar layout, chips, sort headers | ![](screenshots/page-2026-11-15T13-21-38-483Z.png) |
| 9.2 | desktop | pass | Cohort report skeleton then body; shared table header style | ![](screenshots/page-2026-11-15T13-23-25-776Z.png) |
| 9.3 | desktop | pass | Generate report adds Downloads row; compact empty state | ![](screenshots/page-2026-11-15T13-23-46-973Z.png) |
| 9.4 | desktop (JS off) | pass | "Load the figures" link renders report body | ![](screenshots/page-nojs-2026-11-15T13-24-02-824Z.png) |
| 9.5 | desktop | skip | Not run: REPORTS_MAX_LEARNERS 500, largest cohort 149 | |
| 10.1-10.2 | desktop | pass | Import format table; wrong header returns 422 with focused alert | ![](screenshots/page-2026-11-15T13-24-47-209Z.png) |
| 10.3-10.4 | desktop | pass | 60-row preview pager and capped Rows table; 30-row tiles filter | ![](screenshots/page-2026-11-15T13-25-25-870Z.png), ![](screenshots/page-2026-11-15T13-25-08-408Z.png) |
| 10.5 | desktop | pass | Import result page, list rows, time matches audit log | ![](screenshots/page-2026-11-15T13-25-50-601Z.png) |
| 11.1 | desktop | pass | Cohort details and Settings staff list rows | ![](screenshots/page-2026-11-15T13-26-13-345Z.png) |
| 11.2 | desktop | pass | Learner Registrations rows, Courses tab sections | ![](screenshots/page-2026-11-15T13-27-04-893Z.png) |
| 11.3 | desktop | pass | Rename updates h1 and title; empty name shows one line | |
| 11.4 | desktop | pass | Cohorts and learners table columns filled | ![](screenshots/page-2026-11-15T13-01-53-248Z.png) |
| 11.5 | desktop | pass | History row expands to label/value list; null actor fallback | |
| 11.7 | desktop | pass | Compact empty state on Quinn Messages | |
| 12.3 | desktop | pass | Unread count updates after ~35s with no reload | |
| 12.4 | mobile (learner) | pass | Course outline bottom sheet closes with Esc; no close control (see General notes) | ![](screenshots/page-learner-toc375-open-2026-11-15T13-29-31-733Z.png) |
| 12.4 | desktop (learner) | pass | Outline docked; messages and bell panels open | ![](screenshots/page-learner-messages1920-2026-11-15T13-29-36-135Z.png) |
| 12.5 | desktop (learner) | pass | Topic and survey pages load, no console errors | ![](screenshots/page-learner-topic1920-2026-11-15T13-29-34-536Z.png) |
| 12.6 | desktop | pass | `/panel-framework/components/` renders all tones, Table, List | |
| 13.2 | desktop | pass | 18 pages return 200 with no raw template tags | |
| 13.3 | desktop | pass | Every opened panel had one header, a body and one footer | |
| 13.4 | desktop | pass | Focus stays in dialog; Esc returns to trigger | |
| 5.8 | desktop | pass | Register cohort for course re-renders title and registers | |
| 12.1 | mobile | pass | Sidebar bottom sheet with 44px close; Esc closes | ![](screenshots/page-2026-11-15T13-32-33-388Z.png) |
| 1.10 | mobile | pass | Deactivate dialog as bottom sheet; footer in view; 44px targets | ![](screenshots/page-2026-11-15T13-33-01-217Z.png) |
| 6.4 | mobile | pass | Learner cards; quick view full width, Close in view | ![](screenshots/page-2026-11-15T13-33-56-171Z.png) |
| 8.5 | mobile | pass | Filter sheet with Reset, close, footer | ![](screenshots/page-2026-11-15T13-34-04-960Z.png) |
| 9.6 | mobile | **fail** | Sticky first column truncates learner names (B3) | ![](screenshots/page-2026-11-15T13-34-19-209Z.png) |
| 11.8 | mobile | pass | No sideways scroll, no button under 44px | ![](screenshots/page-2026-11-15T13-35-00-183Z.png) |
| 10.3 | mobile | pass | Import preview Rows render as cards | ![](screenshots/page-2026-11-15T13-35-12-317Z.png) |
| 7.x | mobile | pass | Selection bar above cards; More menu inside viewport | ![](screenshots/page-2026-11-15T13-35-24-963Z.png) |
| 13.1 | tablet | pass | Tables render as cards at 768; names readable | ![](screenshots/page-2026-11-15T13-35-55-135Z.png) |
| 12.1 | tablet | pass | Bottom-sheet sidebar with Close navigation; Esc closes | ![](screenshots/page-2026-11-15T13-36-17-072Z.png) |
| 9.6 | tablet | **fail** | Summary tables still truncate learner names (B3) | ![](screenshots/page-2026-11-15T13-36-10-989Z.png) |

## Design check

No design states tested.

## B1: Quick view discard prompt body sits on the panel edge instead of its padding

Manifestations: Test 6.3 (desktop).

![](screenshots/page-2026-11-15T13-03-06-076Z.png)

- Expected: in the quick view, the "Discard your message?" prompt's body sentence "The message you wrote hasn't been sent." starts on the same 24px padding as its heading and footer buttons (x=1465), as the same prompt does inside a modal dialog.
- Actual: the body sentence starts at the quick view's left edge (x=1441). The prompt body wrapper `panel-surface space-y-4 py-5 text-sm` sits inside a `-mx-6 -mb-5` wrapper and has no horizontal padding.

## B2: Bulk picker dialog keeps the previous target's confirmation after the picker is set back to no choice

Manifestations: Test 7.8 (desktop).

![](screenshots/page-2026-11-15T13-18-23-065Z.png)

- Expected: choosing the empty `---------` option in the bulk "Add to cohort" picker re-renders the dialog to its no-choice state: title "Add to cohort?", confirm disabled, "Choose a cohort first." in the body.
- Actual: no request is sent (htmx validates the form, and the required select is empty, so the change-triggered re-post is blocked). The dialog keeps "Add 2 learners to QA cohort B?" and "Add 2 learners to QA cohort B." with "Add to cohort" enabled while the picker shows no cohort. `bulk_picker.html` is unchanged from main.

## B3: Cohort report summary tables truncate learner names in the sticky first column on phone and tablet

Manifestations: Test 9.6 (mobile 375, tablet 768).

![](screenshots/page-2026-11-15T13-34-19-209Z.png)
![](screenshots/page-2026-11-15T13-36-10-989Z.png)

- Expected: in a table that scrolls sideways in its own region every person's name is readable (panel-framework visual checklist; plan Test 9.6).
- Actual: `cohort_report_body_region.html` renders the row header as `sticky left-0 min-w-44 ... whitespace-nowrap` with `c-panel-person-link`, whose name span is `block truncate`. Names longer than about 100px show as "Aaron Abrah…", "Amy Achter…", "Penny Pendi…" at 375 and 768.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 0-capture-check | desktop | `/` | ![](screenshots/page-2026-11-15T12-59-59-707Z.png) | clean (debug toolbar not yet collapsed in this shot; fixed with djdt=hide cookie afterwards) |
| 12.2 | desktop | `/educator/organisations/demodev/dashboard` | ![](screenshots/page-2026-11-15T13-00-46-486Z.png) | clean |
| 8.1 | desktop | `/educator/organisations/demodev/cohorts` | ![](screenshots/page-2026-11-15T13-01-53-248Z.png) | clean |
| 6.3 | desktop | `/educator/organisations/demodev/dashboard` | ![](screenshots/page-2026-11-15T13-03-06-076Z.png) | clean |
| 1.1 | desktop | `/educator/organisations/demodev/cohorts/<A>/__tabs/settings` | ![](screenshots/page-2026-11-15T13-03-57-611Z.png) | clean |
| 2.6 | desktop | `/educator/organisations/demodev/staff` | ![](screenshots/page-2026-11-15T13-08-48-734Z.png) | clean |
| 5.6 | desktop | `/educator/organisations/demodev/learners/<alice>/__tabs/messages` | ![](screenshots/page-2026-11-15T13-16-37-629Z.png) | clean |
| 9.2 | desktop | `/educator/organisations/demodev/cohorts/<A>/__tabs/report` | ![](screenshots/page-2026-11-15T13-23-25-776Z.png) | clean |
| 10.2 | desktop | `/educator/organisations/demodev/learners/import/` | ![](screenshots/page-2026-11-15T13-24-47-209Z.png) | clean |
| 1.10 | mobile | `/educator/organisations/demodev/cohorts/<A>/__tabs/settings` | ![](screenshots/page-2026-11-15T13-33-01-217Z.png) | clean |
| 6.4 | mobile | `/educator/organisations/demodev/learners/` | ![](screenshots/page-2026-11-15T13-33-10-671Z.png) | clean |
| 11.8 | mobile | `/educator/organisations/demodev/learners/<quinn>` | ![](screenshots/page-2026-11-15T13-35-00-183Z.png) | clean |
| 13.1 | tablet | `/educator/organisations/demodev/cohorts/<A>/__tabs/learners` | ![](screenshots/page-2026-11-15T13-35-55-135Z.png) | clean |

## Data changes

| Via | What |
|---|---|
| sdd:qa-data-helper | Ran `qa_create_dev_org_baseline --site-name DemoDev`: created "QA cohort empty" (pk 538fa94a); reset qa.penny@email.com to pending (unusable password, last_login None); everything else already existed |
| sdd:qa-data-helper | Edited `freedom_ls/qa_helpers/management/commands/qa_create_dev_org_baseline.py` (uncommitted) so a re-run puts Penny back to pending; saved a note under `.claude/agent-memory/sdd-qa-data-helper/` |
| QA run (browser) | Deleted "QA cohort empty" as Test 4.4 requires; QA cohort A deactivated and reactivated; Quinn's Quiz registration now inactive and Demo Finance active; Dan reactivated then deactivated again; Cora deactivated then reactivated |
| QA run (browser) | Aaron removed from and re-added to QA cohort A (5.2/5.7); learners qa.newlearner53544@email.com and qa.newlearner81548@email.com created (5.5/11.6) |
| QA run (browser) | Bulk resend setup email run inline (90 qa.bg) and in background (299); Bg Learner 004/005 deactivated (7.4 attempt); qa.bgz1-4@email.com created and qa.bgz1/2 deactivated |
| QA run (browser) | Imported 28 learners qa.imp30r01-28@email.com (Test 10.5); generated a report download for QA cohort A (9.3); a 60-row import preview left unconfirmed |
| QA run (browser) | Reactivated Quinn's "show end with Quiz" registration (11.2); renamed QA cohort A and back (11.3) |
| QA run (browser) | Alice sent a message to demodev@email.com (12.3); QA cohort B registered for Standard Markdown - Demo Finance (5.8) |

## Bug status

| Bug | Status |
|---|---|
| B1 | **FIXED** (commit: 17a17895a) — Quick view discard prompt body sits on the panel edge instead of its padding. Re-verified at 1920: body and heading both at x=1465; the modal-dialog prompt unchanged (729/729). |
| B2 | **FIXED** (commit: 67208227c) — Bulk picker dialog keeps the previous target's confirmation after the picker is set back to no choice. Re-verified: clearing the picker re-renders "Add to cohort?" with the confirm disabled and "Choose a cohort first."; a forced empty confirm is still refused ("This field is required."); cohort "Register for a course" picker still re-renders. |
| B3 | **FIXED** (commit: d8fbd932b) — Cohort report summary tables truncate learner names in the sticky first column on phone and tablet. Re-verified at 375 and 768: every name fits (row header min-width 256px), no page sideways scroll. |

## General notes

No action needed unless stated.

- Every `c-panel-avatar-chip` renders its own inline `<style>@layer components{...}</style>` block (22 on the dashboard). Same on main.
- The Staff page name column caps at `md:max-w-56`, so "demodev@email.com" truncates at 1920 with room to spare. Same on main.
- The learner quick view's Messages section draws a rule under its heading, and its composer sits 16px in from the quick view's padding (composer `px-4` when `in_quick_view`). Same on main.
- The inline Save button's loading text is "Saving..." with three dots (`cotton/button.html` default and `inline_record_form.html`); the ellipsis rule covers dialogs only. Same on main.
- Add staff member's Role and Cohorts fieldsets draw bordered boxes inside the dialog. Same on main.
- Decision for the user: the learner course-outline bottom sheet at 375 has no close control (the base template comment says the panel has no chrome; it closes with Esc or the backdrop), while the panel-framework rule says a phone sheet has a header with a close control.
- Tests not run: 3.4 (account already set up; needs the emailed setup link and the 15-minute resend limit answers first) and 9.5 (report over-limit; REPORTS_MAX_LEARNERS is 500 and the largest cohort has 149). Test 11.7 "cohort with no staff" cannot occur because the org admin is always listed.
- The data helper edited `freedom_ls/qa_helpers/management/commands/qa_create_dev_org_baseline.py` (uncommitted) to reset the pending learner on re-run.
- Console errors seen were only the expected 422 responses for validation and refusal paths; no JS errors.

status: ok · reason: 3 bugs — 3 fixed, 0 unresolved; report rendered, screenshots verified
