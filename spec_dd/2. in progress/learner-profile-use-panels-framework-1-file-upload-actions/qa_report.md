# Frontend QA report

## Methodology

Walked by hand with the Playwright MCP against the branch's dev server (port 8342), logged in as the QA admin. Screenshots were collected into `screenshots/` beside this report, and every referenced image exists there. Failed requests were simulated by routing `**/__actions/**` as the plan describes (500, 404, 413, aborted request, and a 500 carrying an OOB toast fragment).

## Diff scoping

- Class: **FULL**
- Changed files:
  - `freedom_ls/base/static/base/js/alpine-components.js`
  - `freedom_ls/base/templates/cotton/button.html`
  - `freedom_ls/educator_interface/forms.py`
  - `freedom_ls/educator_interface/templates/educator_interface/partials/inline_record_form.html`
  - `freedom_ls/panel_framework/actions.py`
  - `freedom_ls/panel_framework/reference.py`
  - `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`
  - `freedom_ls/panel_framework/templates/panel_framework/modal/form.html`
  - `freedom_ls/panel_framework/templates/panel_framework/partials/inline_record_form.html`
  - `freedom_ls/panel_framework/templates/panel_framework/reference/_examples.html`
  - `freedom_ls/panel_framework/templates/panel_framework/widgets/clearable_file_input.html`
  - `freedom_ls/panel_framework/widgets.py`
  - plus panel_framework and base tests
- Skipped: nothing. Desktop, tablet and mobile all ran. Tablet and mobile focused on layout, as the plan lists.

## Smoke gate

**pass**. Pages checked: `/`, `/panel-framework/components/`. No failure URL or reason.

## Results

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 1.1-1.5 | desktop | pass | Three wrapper ids present. "Current file: first-aid-certificate.pdf", no `certificates/2026/` anywhere, no link. Remove checkbox then native file input. Label "Attachment:" is for the file input. Error example shows "2 fields to fix.", required error, CHOOSE_AGAIN message, empty file input and Current file line. Inline example has file input + Save, multipart, no Remove, no Current file. | ![](screenshots/page-2026-11-17T14-09-43-588Z.png) |
| 1.6 | desktop | pass | Current file line is base size. Field labels and the Remove label are the existing smaller label style shared with every form. | ![](screenshots/page-2026-11-17T14-09-43-588Z.png) |
| 1.7 | desktop | pass | No sideways scroll. Examples do not overflow at 1920/768/375. | ![](screenshots/page-2026-11-17T14-09-43-588Z.png) |
| 1.7 | tablet | pass | No sideways scroll, no overflow. | ![](screenshots/page-ref-tablet-1794924618636.png) |
| 1.7 | mobile | pass | No sideways scroll, no overflow. | ![](screenshots/page-ref-mobile-1794924619772.png) |
| 1.8 | desktop | **fail** | Console error on every load of the reference page: Alpine "Undefined variable: refocusAfterRequest" (see B2). Notice and Callout render as before. | ![](screenshots/page-2026-11-17T14-09-43-588Z.png) |
| 1.9 | desktop | **fail** | Inline example is live: choosing a file and pressing Save posts to the reference page and swaps a whole copy of the page into `#file-field-inline`, duplicating ids (see B1). | none |
| 1.10 | desktop | pass | Checkbox accessible name is "Remove first-aid-certificate.pdf". | none |
| 2.1-2.4 | desktop | pass | Name panel: First/Last name in one row, Save at end. Save disabled and reads "Saving…" (single ellipsis) while held. Name saved, heading updated, focus back on first_name. Over 200 chars gives one red line "Ensure this value…" with role=alert under the row, no box, no summary, aria-invalid=true, aria-describedby=id_first_name_error. Form has no enctype/hx-encoding. | ![](screenshots/page-learner-name-saving-1794924658719.png) |
| 2.3 | desktop | pass | Field error one line, no box, input marked invalid. | ![](screenshots/page-learner-name-error-1794924680708.png) |
| 2.5 | desktop | pass | Hidden request-error holder has height 0; no gap in the panel. | ![](screenshots/page-learner-name-saving-1794924658719.png) |
| 2.6 | mobile | pass | No sideways scroll at 375; fields stack, Save below. | ![](screenshots/page-learner-settings-mobile-1794924730294.png) |
| 6.1 | desktop | **fail** | Routed 500: "Your changes could not be saved. Try again." appears under the row with role=alert at 14px like a field error. Changed name kept; Save enabled and reads Save; panel not replaced. FAIL: message drawn in body text colour, not error colour (see B3). | ![](screenshots/page-inline-request-error-1794924697307.png) |
| 6.2 | desktop | pass | Route removed, Save: message hidden, name saved. | none |
| 7.1 | desktop | pass | Routed 404 on the Name form: page reloaded, no request error message. | none |
| 3 | desktop | pass | Cohort Name panel: field + Save in one row. Save disabled and "Saving…" while held. Heading updated, focus back on name. Over 150 chars gives one-line role=alert error, no box/summary, aria-invalid=true. No enctype/hx-encoding. Hidden holder takes no space. Name restored. | ![](screenshots/page-cohort-name-error-1794924770441.png) |
| 4.1-4.3 | desktop | pass | Create cohort dialog: header, Name field, footer; focus in Name; no enctype/hx-encoding. Empty submit gives "1 field to fix." summary with focus on it and "This field is required."; no "Choose the file again". | ![](screenshots/page-create-cohort-422-1794924828191.png) |
| 4.4-4.5 | desktop | pass | Typed name + Esc shows "Discard changes?". Keep editing keeps the name. Cleared + Esc closes with no prompt. | ![](screenshots/page-discard-prompt-1794924901616.png) |
| 4.6 | desktop | pass | Save and Save and add another disabled and read "Saving…" while held, never "Uploading…". Cohort created (dialog navigated to the new cohort). | ![](screenshots/page-dialog-saving-1794924921937.png) |
| 4.7 | mobile | pass | Dialog is a bottom sheet at 375 (0..375 wide, anchored to the bottom), no sideways scroll. | ![](screenshots/page-dialog-request-error-mobile-1794924942225.png) |
| 5.1 | desktop | **fail** | Routed 500: dialog stays open, message inside the modal body above the field, holder focused, typed name kept, Save enabled and reads Save, no server error page. FAIL: message in body text colour, not error colour (see B3). | ![](screenshots/page-dialog-request-error-500-1794924905030.png) |
| 5.2 | desktop | pass | 413: message reads "The file may be too large to upload. Choose a smaller file."; only one message. | none |
| 5.3 | desktop | pass | `route.abort()`: "Your changes could not be saved. Try again." | none |
| 5.4 | desktop | pass | Route removed: message hidden as the request starts, cohort created, dialog closed (navigated to the new cohort). | ![](screenshots/page-dialog-saving-1794924921937.png) |
| 5.5 | desktop | pass | Reopened create dialog has no leftover message. | none |
| 5.6 | desktop | pass | Message element is a `<p role=alert>`. | none |
| 5.7 | mobile | pass | Message wraps inside the sheet, no sideways scroll (colour issue as 5.1). | ![](screenshots/page-dialog-request-error-mobile-1794924942225.png) |
| 7.2 | desktop | pass | Empty create-cohort submit: 422 summary only, request-error holder stays hidden. | ![](screenshots/page-create-cohort-422-1794924828191.png) |
| 7.3 | desktop | pass | Add to cohort dialog, cohort select refreshes on change: GET routed to 500, no request error message in the form, dialog stays usable. | ![](screenshots/page-add-to-cohort-refresh-500-1794924978608.png) |
| 7.4 | desktop | pass | Quick view GET routed to 500: drawer shows "Something went wrong loading this." with Retry; no request error message. | ![](screenshots/page-quick-view-500-1794924992183.png) |
| 7.5 | desktop | pass | No real educator action answers an error with a toast, so a 500 carrying an OOB toast fragment was routed to the create-cohort POST: the toast shows and the form adds no request error message. | ![](screenshots/page-toast-error-1794925018906.png) |
| 8.1 | desktop | pass | Deactivate confirm dialog: button disabled with spinner and "Deactivating…" while held (request then aborted, learner unchanged). | ![](screenshots/page-confirm-loading-1794925033744.png) |
| 8.2 | desktop | pass | Logged in as learner qa.alice, opened the course and its first item: no console errors. No learner-side template uses the button's loading state (only educator/panel templates and claim_link_notice do), so learner submit buttons are unaffected. | ![](screenshots/page-learner-activity-1794925062451.png) |
| 8.3 | desktop | pass | Deactivate button's loading span carries `data-loading-label="Deactivating…"`, equal to its visible loading text. | none |

## Design check

no design states tested

## B1: Reference page inline file example posts for real and nests a copy of the page

Manifestations:
- Test 1.9 (desktop)

Screenshots: none captured for this bug.

**Expected:** The inline example on `/panel-framework/components/` is static: its wrapper `#file-field-inline` carries `hx-disable`, so pressing its Save posts nothing.

**Actual:** `#file-field-inline` has no `hx-disable`. Choosing a file and pressing Save posts multipart to the reference page URL and swaps the whole page (header, every section) into the example, duplicating ids such as `file-field-dialog`.

## B2: Reference page logs an Alpine error: refocusAfterRequest is undefined

Manifestations:
- Test 1.8 (desktop)

![](screenshots/page-2026-11-17T14-09-43-588Z.png)

**Expected:** No console error on `/panel-framework/components/`.

**Actual:** Every load logs "Alpine Expression Error: Undefined variable: refocusAfterRequest" and an uncaught error. The File field inline example includes `panel_framework/partials/inline_record_form.html` (`x-data=refocusAfterRequest`), registered in `panel_framework/static/panel_framework/js/alpine-components.js`, which `component_reference.html` (extends `_base.html`) does not load.

## B3: Request error message is drawn in body text colour, not error colour

Manifestations:
- Test 5.1 (desktop)
- Test 5.7 (mobile)
- Test 6.1 (desktop)

![](screenshots/page-dialog-request-error-500-1794924905030.png)
![](screenshots/page-inline-request-error-1794924697307.png)
![](screenshots/page-dialog-request-error-mobile-1794924942225.png)

**Expected:** "Your changes could not be saved. Try again." (and the 413 message) shows in error colour, like a field error, in both the dialog and the inline form.

**Actual:** The `[data-request-error]` holder has `text-error` (computed rgb(210,51,25)) but the `<p role=alert>` the script inserts computes rgb(26,35,50), the body text colour, so the message reads as ordinary text.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1 | desktop | /panel-framework/components/ | ![](screenshots/page-2026-11-17T14-09-43-588Z.png) | clean |
| 1 | tablet | /panel-framework/components/ | ![](screenshots/page-ref-tablet-1794924618636.png) | clean |
| 1 | mobile | /panel-framework/components/ | ![](screenshots/page-ref-mobile-1794924619772.png) | clean |
| 2 | desktop | /educator/organisations/demodev/learners/&lt;pk&gt;/__tabs/settings | ![](screenshots/page-learner-name-error-1794924680708.png) | clean |
| 2 | mobile | /educator/organisations/demodev/learners/&lt;pk&gt;/__tabs/settings | ![](screenshots/page-learner-settings-mobile-1794924730294.png) | clean |
| 2 | tablet | /educator/organisations/demodev/learners/&lt;pk&gt;/__tabs/settings | ![](screenshots/page-learner-settings-tablet-1794924731099.png) | clean |
| 3 | desktop | /educator/organisations/demodev/cohorts/&lt;pk&gt;/__tabs/settings | ![](screenshots/page-cohort-name-error-1794924770441.png) | clean |
| 5 | mobile | /educator/organisations/demodev/cohorts | ![](screenshots/page-dialog-request-error-mobile-1794924942225.png) | clean |
| 5 | tablet | /educator/organisations/demodev/cohorts | ![](screenshots/page-dialog-request-error-tablet-1794924942318.png) | clean |

## Data changes

| Via | What |
|---|---|
| sdd:qa-data-helper | Empty branch dev DB seeded: `create_demo_data --yes`, `content_save demo_content DemoDev`, `qa_create_dev_org_baseline --site-name DemoDev` (DemoDev site, demodev org, QA cohort A/B/empty/inactive, named QA learners) |

## Bug status

| Bug | Status |
|---|---|
| B1 | **FIXED** (commit: 8f6876c6d) — Reference page inline file example posts for real and nests a copy of the page |
| B2 | **FIXED** (commit: c45f18a25) — Reference page logs an Alpine error: refocusAfterRequest is undefined |
| B3 | **FIXED** (commit: 0dac2d6af) — Request error message is drawn in body text colour, not error colour |

Re-verified in the browser after each fix:

- B1: `#file-field-inline` carries `hx-disable`; choosing a file and pressing Save sends no POST and nests nothing. The example's plain `<form>` now submits natively as a GET, reloading the reference page with `?attachment=inline.pdf`; harmless, and the page renders once.
- B2: the reference page loads `panel_framework/js/alpine-components.js`; no console error or warning on load, and ticking Remove plus choosing a file in the dialog example sends nothing.
- B3: the message's computed colour now equals the holder's error colour (rgb(210,51,25)) in the create-cohort dialog and the learner Name inline form.

![](screenshots/page-dialog-request-error-fixed-1794933090452.png)
![](screenshots/page-inline-request-error-fixed-1794933094063.png)

## General notes

- The empty dev database was seeded by the QA data helper before testing.
- Test 2.3 / 3: the learner first name accepts an empty value and the cohort name input is browser-required, so the over-length case was used for the field error.
- Test 6.1: after a 422 left a field error, a following failed request shows the request error message above the stale field error; both stay until the next swap.
- Test 7.5: a 4xx/5xx carrying an OOB toast swaps the response's (empty) main content into the form's target, so the dialog body empties while the toast shows. That swap lives in the pre-existing base `htmx:beforeSwap` listener, not this branch's code; no real educator action answers an error with a toast today.
- Confirm dialogs (e.g. Deactivate) do not use `modal/form.html`, so a failed confirm request shows no request error message; outside this change's scope.
- The reference page's dialog examples render field labels and the Remove label in the existing smaller label style shared with every form.

status: ok · reason: 3 bugs — 3 fixed, 0 unresolved; report rendered, screenshots verified
