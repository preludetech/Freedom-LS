# Frontend QA report: educator-interface-8-bulk-operations

## Methodology

- Run with the Playwright MCP against a dev server started on its own port.
- Logged in as `org.admin@qa.test` unless a test says otherwise (cohort.admin, cohort.viewer, south.admin, demodev superuser and logged-out checks are in section 8).
- Viewports: desktop 1920x1080, mobile 375x812, tablet 768x1024.
- Data was seeded per section 0 of the test plan (`3. frontend_qa.md`) by a data helper.
- Screenshots were collected into `screenshots/` beside this report. Every image referenced below exists there.
- The Django Debug Toolbar was hidden with an injected style, because it intercepted clicks.

## Diff scoping

- Class: **FULL**. Templates, static files and JS changed (`freedom_ls/educator_interface/templates/...`, `freedom_ls/panel_framework/templates/...`, `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`).
- Skipped: nothing.
- Desktop, mobile and tablet all ran.

## Smoke gate

**Pass.** These pages loaded:

- `/`
- `/educator/organisations/northside/learners`
- `/educator/organisations/northside/learners/import/`

## Design check

No design states tested.

## Results

| Test | Viewport | Status | Notes |
|---|---|---|---|
| 1.1 | desktop | fail | Import learners is a link. The import page has a stepper with `aria-current=step` on Upload, "Step 1 of 3", the file input, sidebar and org switcher. The breadcrumb slot is empty, as on the learners list (by design). Cosmetic FAIL: stepper renders "1. Upload2. Preview3. Result" (B5). |
| 1.2 | desktop | pass | template.csv: attachment `learner-import-template.csv`, BOM, 4 headers and 2 example rows. |
| 1.3 | desktop | pass | 51 pasted lines give 422 with "Add up to 50 at a time; larger lists are imported from a file." and an "Import a file instead" link. |
| 1.4 | desktop | pass | Cohort C Learners tab has an Import learners link ending `?cohort=<pk>`. Cohort Old tab has no link. |
| 2.excel | desktop | pass | 422, focused alert: "This looks like an Excel file. Save it as CSV UTF-8 and upload that." |
| 2.latin1 | desktop | pass | 422, focused alert: "Save the file as CSV UTF-8 and upload it again." |
| 2.badhead | desktop | fail | 422, "Unknown column(s): e-mail, name. Accepted columns: email, first_name, last_name, cohort." Does not say email is missing (B6). |
| 2.empty | desktop | pass | 422, "This file has no rows to import." |
| 2.big | desktop | pass | 422, "2,431 rows; the limit is 2,000." |
| 2.nofile | desktop | pass | Browser blocks submit. With `required` removed: 422 "This field is required." in the focused alert. LearnerImport and LearnerImportRow counts stay 0. |
| 3.1 | desktop | pass | Preview at step 2 of 3. Chip "good.csv · 30 rows". Counts New account 26 / Reactivated 1 / Added to the cohort 1 / Error 2. errors.csv has BOM, correct header and exactly 2 rows. Button "Add 28 learners" and "2 rows with errors will not be added." Count list shows bullet markers between inline links (same list-style issue as B5). |
| 3.2 | desktop | pass | `?label=error` filter shows 2 rows. Reload keeps it. Back returns the full 30-row table. |
| 3.3 | desktop | pass | dup.csv: "Same email as line 2.", "Email is empty."; button reads "Add 1 learner". |
| 3.4 | desktop | pass | Both rows error with "No active cohort called '...' that you can add learners to."; no confirm button; "Nothing can be added: every row has an error or is already a member." Minor: still shows "0 new accounts will get a setup email." |
| 3.5 | desktop | pass | semi.csv: 2 new accounts, semicolon delimiter read. |
| 4.1 | desktop | pass | Result at step 3 of 3: "Added 28 learners. 2 rows were not added." "26 setup emails were sent." Mailpit has 26 messages, none to ada@ or removed@. Error rows, error CSV link and Back/Import another links present. |
| 4.2 | desktop | pass | Preview URL redirects to the result after commit. |
| 4.3 | desktop | pass | import01 Pending in Cohort C; Cohort C filter lists 27; Rae Removed Active; Ada's page heading "Ada Lovelace". |
| 4.4 | desktop | pass | Re-upload: "Already a member: 28", 2 errors, no Add button; Mailpit 0 new. |
| 4.5 | desktop | pass | "Added 1 learner. 2 rows were not added.", "1 setup email was sent."; errors.csv holds exactly the 2 expected rows. |
| 5.1 | desktop | pass | Cohort A tab link goes to `/import/?cohort=<A pk>`; upload page says "Every learner in the file is added to Cohort A. The cohort column is ignored." |
| 5.2 | desktop | fail | Behaviour correct (both land in Cohort A, "Added 2 learners. 0 rows were not added."). Preview's Cohort column shows the raw "Cohort C" for cohortimp (B2). |
| 6.1 | desktop | pass | Checkbox column and "Select all on this page"; nothing selected hides bar buttons and shows pagination. Page size is 10. |
| 6.2 | desktop | fail | "2 selected · showing 1–10 of 95 learners"; Add/Remove buttons and More actions (Deactivate, Reactivate, Register for course, Unregister from course, Resend setup email). The More actions menu extends to y≈1241 in a 1121px document, so the lower items are unreachable (B1). |
| 6.3 | desktop | pass | Add to cohort disabled until chosen; focus on Cancel; "2 learners will be added to Cohort C." then "2 learners changed."; HX-Trigger `learnerChanged` refreshes the table; selection cleared after Close. |
| 6.4 | desktop | pass | "1 learner will be added to Cohort C. \| 2 are already in the cohort and will be skipped."; result "1 learner changed. 2 already in the cohort". Single already-member: "0 learners will be added..." with confirm disabled. |
| 6.5 | desktop | pass | "1 learner will be removed from Cohort A. \| 1 is not a member and will be skipped. \| They lose access to: Course Pub." |
| 6.6 | desktop | pass | Search Alpha (30 rows, 10/page). "All 10 on this page are selected. Select all 30 matching" then "All 30 matching are selected. Clear selection"; untick bulk05 gives 29. "29 learners will be added to Cohort B." then "29 learners changed."; bulk05 absent from Cohort B. |
| 6.7 | desktop | pass | Select all matching then sort: selection cleared, bar buttons hidden, 0 checked. |
| 6.8 | desktop | pass | "31 learners will be removed from Cohort B. They lose access to: Course Hid and Course Pub." then "31 learners changed."; Cohort B empty. |
| 6.9 | desktop | pass | Deactivate (destructive style) "2 learners lose access to this organisation's courses." with kept-data line; Reactivate restores. Mixed: "1 learner changed. 1 already active". |
| 6.10 | desktop | pass | Adapted (split selections). "1 is already registered individually and will be skipped."; Register and Unregister (destructive style) work; Courses cells update. |
| 6.11 | desktop | fail | Confirmation reads "2 learners will be sent a setup email. \| 1 is account already set up and will be skipped." (B3). Result and cooldown behaviour correct; Mailpit 1 message. Repeat confirmation still promises 2 sends although the cooldown skips them. |
| 6.12 | desktop | pass | Ticked keys: count unchanged, so safe skip ("already inactive"), no 422. Select-all-matching (Beta, 18): after a change in tab 2, 422 "The selection changed since you opened this." with 17. |
| 6.13 | desktop | pass | JS disabled: items render as visible buttons with `formaction`; full-page confirmation and result "2 learners changed." with "Back to learners" keeping `?learners-q=bulk1`. |
| 6.14 | desktop | pass | Ran with a scratch settings module (threshold 5). "This will affect 17 learners. \| It runs in the background. Anything skipped is reported in the result." Run page "17 learners changed." with no polling trigger; reactivate of 30 gave "30 learners changed." |
| 7.1 | desktop | pass | Cohort Old needs the inactive filter. "3 selected"; Register/Unregister buttons; More actions has Deactivate, Reactivate. |
| 7.2 | desktop | fail | Confirmation: "2 cohorts will be registered for Course Hid. \| 1 is an inactive cohort and will be skipped." Result: "2 cohorts changed. \| 1 could not be changed \| Cohort Old: could not be changed" (B4). |
| 7.3 | desktop | pass | "0 cohorts will be registered for Course Hid. \| 2 are already registered and will be skipped. \| 1 is an inactive cohort and will be skipped."; confirm disabled. |
| 7.4 | desktop | pass | "2 cohorts will be unregistered from Course Hid." (destructive) then "2 cohorts changed."; second run "1 cohort changed. 1 not registered". |
| 7.5 | desktop | pass | Bulk Deactivate shows Inactive; Reactivate "1 cohort will give access to its courses again." |
| 7.6 | desktop | pass | Single Deactivate/Reactivate on the settings tab work. Wording: "stop giving access to its 0 courses" when there are no active registrations. |
| 8.1 | desktop | pass | cohort.admin: Register/Unregister only in More actions (nothing else in the DOM); no Import link; picker offers Cohort A and B; import URL 403 "You can't import learners here"; direct POSTs to deactivate/reactivate/resend 403; add_to_cohort with Cohort C pk gives 422 "Select a valid choice." |
| 8.2 | desktop | pass | cohort.viewer: 5 rows, no checkboxes, no selection status; import URL 403. |
| 8.3 | desktop | pass | south.admin: import preview/result/errors.csv and run URL all 404 under both orgs. |
| 8.4 | desktop | pass | demodev superuser: result URL 404; import page 200. |
| 8.5 | desktop | pass | Logged out: import page 302 to `/accounts/login/?next=...`. |
| 9.1 | desktop | pass | Two tabs confirm at once: both land on the same result "Added 2 learners. 0 rows were not added."; each learner once; one email each. |
| 9.2 | desktop | pass | Replaying the confirmed POST returns 422 with "0 learners will be added to Cohort C. 2 are already in the cohort and will be skipped."; no second membership. |
| 10.1 | mobile | pass | No overflow (scrollWidth 375) on upload, 422 summary, preview and result. Preview table hidden below md; cards show email, Line, Label, Reason. Stepper labels run together (same as B5). |
| 10.2 | mobile | fail | Selection bar fixed at bottom (219px, stacked buttons); modal and summary render as bottom sheets in the viewport. More actions items all at top>=813px in an 812px viewport, so none can be tapped; items are 36px tall (B1). |
| 10.3 | mobile | pass | Bulk run page "17 learners changed." and Back to learners fit; nothing overlaps nav. |
| 10.1 | tablet | pass | No overflow (scrollWidth 768) on upload, preview (table layout), result and bulk run page. Sidebar collapses to hamburger. |
| 10.2 | tablet | fail | Bar at bottom of table; More actions menu opens downward out of view, no item visible (B1). |
| 10.3 | tablet | pass | Bulk run result page fits; back link visible. |

## Bugs

### B1: 'More actions' menu opens off-screen below the selection bar

Manifestations:

- 6.2 (desktop)
- 10.2 (mobile)
- 10.2 (tablet)

![](screenshots/page-2026-10-25T06-26-25-903Z.png)
![](screenshots/page-mobile-more-actions.png)
![](screenshots/page-tablet-more-actions.png)

**Expected:** every item in the selection bar's More actions menu can be seen and clicked or tapped at every viewport.

**Actual:** the menu drops downward from a bar that sits at the bottom of the table (desktop, tablet) or is fixed to the bottom of the viewport (mobile).

- Desktop 1920x1080: items reach y≈1241 while the document is 1121px tall, so Register, Unregister and Resend cannot be reached even fully scrolled.
- Mobile 375x812: every item starts at y>=813, so none is tappable.
- Tablet: no item is visible.

### B2: Cohort import preview shows the ignored cohort column instead of the target cohort

Manifestations:

- 5.2 (desktop)

![](screenshots/page-2026-10-25T06-25-34-466Z.png)

**Expected:** importing from Cohort A's Learners tab (`?cohort=<pk>`), whose upload page says "The cohort column is ignored", the preview's Cohort column reads "Cohort A" for every row.

**Actual:** the preview echoes the file's raw value ("Cohort C" for cohortimp@qa.test, blank for ben@). The learners correctly land in Cohort A, but the preview tells the educator they will join Cohort C.

### B3: Resend setup email skip line reads '1 is account already set up'

Manifestations:

- 6.11 (desktop)

![](screenshots/page-2026-10-25T06-31-17-163Z.png)

**Expected:** "1 account is already set up and will be skipped."

**Actual:** "1 is account already set up and will be skipped." The `ResendSetupEmailBulkAction.unchanged_reason` "account already set up" is dropped into the generic "N is {reason} and will be skipped" template.

### B4: Cohort bulk register reports an inactive cohort as a failure, not a skip

Manifestations:

- 7.2 (desktop)

No screenshot.

**Expected:** the confirmation says Cohort Old "is an inactive cohort and will be skipped", and the result summary lists it as skipped with that reason.

**Actual:** the result reads "2 cohorts changed. | 1 could not be changed | Cohort Old: could not be changed". `CohortCourseBulkAction.skip_reason` classifies an inactive cohort as a skip for the preview, but the run sends it to apply. The `ValueError` there (`failure_exceptions`) maps it to a failure with the generic `FAILED_REASON`.

### B5: Import stepper labels run together ('1. Upload2. Preview3. Result')

Manifestations:

- 1.1 (desktop)
- 10.1 (mobile)

![](screenshots/page-2026-10-25T06-19-42-033Z.png)
![](screenshots/page-2026-10-25T06-41-21-095Z.png)

**Expected:** Upload, Preview and Result read as three separate steps.

**Actual:** the stepper `<ol class='flex gap-4'>` keeps decimal list-style with outside markers, so each "2." / "3." marker sits inside the 16px gap and the labels butt against the previous one.

### B6: Bad-header error names only the first header problem

Manifestations:

- 2.badhead (desktop)

![](screenshots/page-2026-10-25T06-22-49-646Z.png)

**Expected (QA plan):** one message naming e-mail and name as unknown, saying email is missing, and listing the accepted headers.

**Actual:** "Unknown column(s): e-mail, name. Accepted columns: email, first_name, last_name, cohort." There is no mention that email is missing. `_check_headers` in `base/csv_import.py` raises on the first category (unknown, then repeated, then missing). The spec sentence can be read either way.

## Bug status

- **FIXED** (commit: 165908f9) — B1: 'More actions' menu opens off-screen below the selection bar. Re-verified at 375, 768 and 1920 widths: every item inside the viewport and clickable; the Status filter dropdown still opens downward. ![](screenshots/page-fixed-more-actions-375.png) ![](screenshots/page-2026-10-25T07-00-57-825Z.png)
- **FIXED** (commit: cfe26575) — B2: Cohort import preview shows the ignored cohort column instead of the target cohort. Re-verified: both rows read "Cohort A" in the table and the mobile cards; a plain import still shows the file's cohort. ![](screenshots/page-fixed-cohort-import-preview.png)
- **FIXED** (commit: 8f9a6b90) — B3: Resend setup email skip line reads '1 is account already set up'. The confirmation now reads "1 account is already set up and will be skipped." ("2 accounts are ..." in the plural); it sits under the skip list as its own line, because the framework's skip lines take a reason that follows "is/are".
- **FIXED** (commit: b917e9cd) — B4: Cohort bulk register reports an inactive cohort as a failure, not a skip. Re-verified: result now reads "2 cohorts changed. | 1 an inactive cohort | Cohort Old: an inactive cohort". ![](screenshots/page-fixed-inactive-cohort-skip.png)
- **FIXED** (commit: bc086292) — B5: Import stepper labels run together ('1. Upload2. Preview3. Result'). The stepper reads "1. Upload  2. Preview  3. Result" with no list markers, and the preview's count links lost their stray bullets. Re-verified on the upload page. ![](screenshots/page-fixed-badhead.png)
- **FIXED** (commit: dd676db0) — B6: Bad-header error names only the first header problem. Decision: one message lists every unknown, repeated and missing header, then the accepted columns; the spec now says so. Re-ran 2.badhead: 422 "Unknown column(s): e-mail, name. Missing required column(s): email. Accepted columns: email, first_name, last_name, cohort." PASS. ![](screenshots/page-fixed-badhead.png)

The B4 fixer's commit was blocked by mypy errors in the untracked seeding command; this run renamed a loop variable there to clear them and committed the staged fix.

## General notes

- The plan assumed 25 rows per page, but the learners list shows 10. Section 6.6 used 10 per page, and 6.10 and 6.11 were adapted: selections were split, and cohortimp stood in for import01.
- Section 6.14's environment-variable step is a no-op, because `BULK_BACKGROUND_THRESHOLD` is read from Django settings only. A scratch settings module was used instead. The test plan should be corrected.
- Section 6.12 with ticked keys produces a safe skip rather than a 422, because the count does not change. The 422 was exercised with a select-all-matching selection.
- Section 6.11: the confirmation does not account for the 15-minute resend cooldown, so it can promise sends that then skip.
- Section 3.4 shows "0 new accounts will get a setup email." when nothing can be added.
- Confirmation sentences use "N learners will be added to X." rather than the plan's "Add N learners to X." (the spec says to use the single action's wording).
- Section 7.6: single-cohort deactivate says "its 0 courses".
- The More actions labels are "Register for course" and "Unregister from course".
- The inline counts list on the preview shows bullet markers between inline links (same list-style issue as B5).
- The data helper created an uncommitted qa_helpers seeding command, `freedom_ls/qa_helpers/management/commands/qa_create_bulk_operations_scenario.py`. Its dev_tooling test is still missing.

status: ok · reason: 6 bugs — 3 fixed (B1, B2, B4), 3 unresolved (B3, B5, B6); full run after the fixes: 9539 passed; report rendered, screenshots verified
