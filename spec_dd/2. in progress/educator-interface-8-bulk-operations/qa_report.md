# Frontend QA report: bulk operations

## Methodology

The test plan (`3. frontend_qa.md`) was walked by hand with the Playwright MCP at desktop 1920x1080, mobile 375x812 and tablet 768x1024, as the personas named in the plan. Screenshots were collected into `screenshots/` beside this report, and every image referenced here exists there.

- The branch was rebased onto main at the start of this run. Main had removed the old deadline models, so the branch's migrations were renumbered. The dev database was wiped and re-seeded from §0.
- The post-rebase front-end check was covered by this full QA pass and not run separately.
- §6.14 ran on a scratch settings module with database tasks and a background threshold of 5. That module was deleted afterwards.

## Diff scoping

Class: **FULL**. Triggering changed files (28):

- `freedom_ls/base/static/base/js/alpine-components.js`
- `freedom_ls/educator_interface/templates/educator_interface/`: `_shell.html`, `interface.html`, `learner_import_denied.html`, `learner_import_preview.html`, `learner_import_result.html`, `learner_import_upload.html`, `standalone_page.html`
- `freedom_ls/educator_interface/templates/educator_interface/modal/bulk_run_stopped.html`
- `freedom_ls/educator_interface/templates/educator_interface/partials/`: `import_learners_link.html`, `import_stepper.html`, `learner_import_result_body.html`, `run_status.html`
- `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`
- `freedom_ls/panel_framework/templates/cotton/`: `data-table-card.html`, `data-table.html`
- `freedom_ls/panel_framework/templates/panel_framework/modal/form.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/`: `breadcrumbs.html`, `bulk_confirmation.html`, `bulk_confirmation_form.html`, `bulk_confirmation_message.html`, `bulk_picker.html`, `bulk_result.html`, `bulk_result_body.html`, `bulk_selection_inputs.html`, `table_selection_bar.html`
- `freedom_ls/panel_framework/templates/panel_framework/views/`: `_bulk_confirmation_base.html`, `bulk_result.html`

Nothing was skipped: desktop, mobile and tablet all ran.

## Smoke gate

Pass. Pages loaded: `http://127.0.0.1:8001/` and `http://127.0.0.1:8001/educator/organisations/northside/learners`.

## Design check

No design states tested.

## Results

### §1 Entry points and template

| Test | Viewport | Status | Note |
|---|---|---|---|
| 1.1 | desktop | pass | Import learners link beside Add learners. Import page has stepper (Upload current), "Step 1 of 3", file input, columns line, template link. No breadcrumbs, consistent with every educator page. ![](screenshots/page-2026-10-25T19-49-05-628Z.png) |
| 1.2 | desktop | pass | Template CSV has a UTF-8 BOM, the header and two example rows. |
| 1.3 | desktop | pass | The 50-line cap is stated only when a pasted list exceeds it, with an "Import a file instead" link (422). ![](screenshots/page-2026-10-25T19-50-01-892Z.png) |
| 1.4 | desktop | pass | Cohort C Learners tab links to `?cohort=<pk>`. Cohort Old has no link. |

### §2 Upload rejections

| Test | Viewport | Status | Note |
|---|---|---|---|
| 2.1 | desktop | pass | Six bad files each refused at 422 with the spec sentence in a focused `role=alert` summary. No LearnerImport rows stored. ![](screenshots/page-2026-10-25T19-51-30-259Z.png) |
| 2.2 | desktop | pass | No file: browser required check blocks. With `required` removed the server answers 422, not 500. |

### §3 Preview

| Test | Viewport | Status | Note |
|---|---|---|---|
| 3.1 | desktop | pass | good.csv preview: step 2 of 3, counts 26/1/1/2, exact error reasons, errors CSV has 2 rows, button "Add 28 learners". ![](screenshots/page-2026-10-25T19-51-51-778Z.png) |
| 3.2 | desktop | pass | Error filter shows 2 rows, survives reload; Back returns the full table. |
| 3.3 | desktop | pass | Duplicate and blank-email rows flagged; button reads "Add 1 learner". |
| 3.4 | desktop | pass | All rows error, no confirm button. Minor: still says "0 new accounts will get a setup email." |
| 3.5 | desktop | pass | Semicolon delimiter read. |
| 3.6 | desktop | pass | Trailing delimiter column ignored. |

### §4 Commit and result

| Test | Viewport | Status | Note |
|---|---|---|---|
| 4.1 | desktop | pass | Result at step 3 of 3, "Added 28 learners. 2 rows were not added.", 26 setup emails, Mailpit agrees. ![](screenshots/page-2026-10-25T19-52-26-149Z.png) |
| 4.2 | desktop | pass | Preview URL redirects to the result after confirm. |
| 4.3 | desktop | pass | Pending, cohort memberships and reactivation are correct; Ada's name unchanged. |
| 4.4 | desktop | pass | Re-upload: all "Already a member", no button, no email. |
| 4.5 | desktop | pass | dup.csv: 1 added, error CSV has the two error rows, one email. |

### §5 Import from a cohort

| Test | Viewport | Status | Note |
|---|---|---|---|
| 5.1 | desktop | pass | `?cohort=<A pk>` upload page says the cohort column is ignored. |
| 5.2 | desktop | pass | New account and existing learner both land in Cohort A. Result: "Added 2 learners. 0 rows were not added." ![](screenshots/page-2026-10-25T19-53-38-142Z.png) |

### §6 Bulk actions on the learners list

| Test | Viewport | Status | Note |
|---|---|---|---|
| 6.1 | desktop | pass | Checkbox column and select-all present. With nothing selected only Add learners shows. |
| 6.2 | desktop | pass | Status region reads "2 selected · showing 1–9 of 9 learners"; bar buttons and More actions menu present. ![](screenshots/page-2026-10-25T19-54-01-307Z.png) |
| 6.3 | desktop | pass | Picker, confirm disabled until a cohort is chosen, "2 learners changed.", table refreshed. ![](screenshots/page-2026-10-25T19-54-08-356Z.png) |
| 6.4 | desktop | pass | Skip lines for existing members; selection cleared on close; 0-change confirm disabled. |
| 6.5 | desktop | pass | Remove shows skip and "They lose access to" lines; cancelled. ![](screenshots/page-2026-10-25T19-56-00-000Z-remove.png) |
| 6.6 | desktop | pass | Select all 30 matching, untick one, "29 learners changed."; DB confirms. ![](screenshots/page-2026-10-25T19-57-00-000Z-selectall-confirm.png) |
| 6.7 | desktop | pass | Sorting or paging clears an all-matching selection. |
| 6.8 | desktop | pass | Filtered select-all removal of 31 learners; cohort now empty. |
| 6.9 | desktop | pass | Deactivate uses destructive style; Reactivate skip path correct. ![](screenshots/page-2026-10-25T19-58-00-000Z-deactivate.png) |
| 6.10 | desktop | pass | Register/Unregister course with substitution (see General notes). |
| 6.11 | desktop | pass | Resend setup email with substitution; cooldown skips appear in the result only. |
| 6.12 | desktop | pass | Stale selection: single-row case proceeds with skip; select-all case re-renders at 422. ![](screenshots/page-2026-10-25T20-04-00-000Z-stale2.png) |
| 6.13 | desktop | pass | JS disabled: full-page confirm and result pages work for deactivate and add to cohort. ![](screenshots/page-2026-10-25T20-06-00-000Z-nojs-confirm.png) ![](screenshots/page-2026-10-25T20-06-01-000Z-nojs-result.png) ![](screenshots/page-2026-10-25T20-07-00-000Z-nojs-picker.png) ![](screenshots/page-2026-10-25T20-07-01-000Z-nojs-picker-result.png) |
| 6.14.1 | desktop | pass | Background wording on confirm. ![](screenshots/page-2026-10-25T20-10-00-000Z-bg-confirm.png) |
| 6.14.2 | desktop | pass | Running bar and disabled controls; no overflow at 375 and 768. ![](screenshots/page-2026-10-25T20-10-01-000Z-bg-running.png) ![](screenshots/page-2026-10-25T20-11-00-000Z-bg-running-375.png) ![](screenshots/page-2026-10-25T20-11-01-000Z-bg-running-768.png) |
| 6.14.3 | desktop | pass | Result modal opens after the worker finishes; bell entry already read. ![](screenshots/page-2026-10-25T20-13-00-000Z-bg-done-modal.png) |
| 6.14.4 | desktop | pass | An open modal is not replaced; result opens after it closes. ![](screenshots/page-2026-10-25T20-15-00-000Z-bg-modal-kept.png) |
| 6.14.5 | desktop | pass | Off the learners page, bell shows "1 new" about 31s after the worker. ![](screenshots/page-2026-10-25T20-17-00-000Z-dashboard-bell.png) |
| 6.14.6 | desktop | pass | JS off: flash message, bell updates after worker. ![](screenshots/page-2026-10-25T20-19-00-000Z-nojs-bg-flash.png) |
| 6.14.7 | desktop | pass | Run status URL answers 200 for the requester. |

### §7 Bulk actions on the cohorts list

| Test | Viewport | Status | Note |
|---|---|---|---|
| 7.1 | desktop | pass | Cohort Old shows only under the inactive filter. Register/Unregister are bar buttons; Deactivate/Reactivate are in More actions. |
| 7.2 | desktop | pass | "1 is inactive and will be skipped." (plan wording "an inactive cohort"). |
| 7.3 | desktop | pass | Nothing to register: confirm disabled. ![](screenshots/page-2026-10-25T20-22-00-000Z-cohorts-register-none.png) |
| 7.4 | desktop | pass | Unregister, with substitution for data drift. ![](screenshots/page-2026-10-25T20-23-00-000Z-cohorts-unregister.png) |
| 7.5 | desktop | pass | Bulk deactivate and reactivate Cohort C. |
| 7.6 | desktop | pass | Single deactivate and reactivate work. Copy nit noted below. |

### §8 Permissions and enumeration

| Test | Viewport | Status | Note |
|---|---|---|---|
| 8.1 | desktop | pass | cohort.admin sees limited actions; import URL 403; direct POSTs to forbidden endpoints 403; tampered cohort value never reaches Cohort C. ![](screenshots/page-2026-10-25T20-26-00-000Z-cohortadmin-403.png) |
| 8.2 | desktop | pass | cohort.viewer has no checkboxes or selection bar; import URL 403. |
| 8.3 | desktop | pass | Other-organisation admin gets 404 on every import and run URL. |
| 8.4 | desktop | pass | Superuser who is not the requester gets 404 on result and run status. |
| 8.5 | desktop | pass | Logged out: redirect to login. |

### §9 Repeat submissions

| Test | Viewport | Status | Note |
|---|---|---|---|
| 9.1 | desktop | pass | Double confirm of one preview: no duplicate users, one email per address. |
| 9.2 | desktop | pass | Re-submitting a cached confirm page re-renders at 422 with "Add 0 learners"; no second membership. |

### §10 Viewports

| Test | Viewport | Status | Note |
|---|---|---|---|
| 10.1 | mobile | pass | No overflow; preview renders as cards; stepper wraps. ![](screenshots/page-2026-10-25T20-40-02-000Z-mobile-preview.png) ![](screenshots/page-2026-10-25T20-41-00-000Z-mobile-error-cards.png) ![](screenshots/page-2026-10-25T20-40-01-000Z-mobile-error.png) |
| 10.2 | mobile | **fail** | Fixed bottom bar covers the last card's checkbox (see B1). ![](screenshots/page-2026-10-25T20-43-01-000Z-mobile-short-list-covered.png) ![](screenshots/page-2026-10-25T20-44-01-000Z-mobile-menu.png) |
| 10.3 | mobile | pass | Confirm and result open as full-width bottom sheets. ![](screenshots/page-2026-10-25T20-44-02-000Z-mobile-confirm.png) ![](screenshots/page-2026-10-25T20-44-03-000Z-mobile-result.png) |
| 10.1 | tablet | pass | No overflow; table (not cards) at md. ![](screenshots/page-2026-10-25T20-40-07-000Z-tablet-preview.png) |
| 10.2 | tablet | pass | Bar is static under the table at md; no checkbox covered. ![](screenshots/page-2026-10-25T20-46-00-000Z-tablet-selected.png) ![](screenshots/page-2026-10-25T20-46-01-000Z-tablet-menu.png) |
| 10.3 | tablet | pass | Confirm modal 512px wide, centred; result fits. ![](screenshots/page-2026-10-25T20-46-02-000Z-tablet-confirm.png) ![](screenshots/page-2026-10-25T20-46-03-000Z-tablet-result.png) |

## Bugs

### B1: Mobile selection bar covers the last rows' checkboxes

Manifestations: test 10.2, mobile.

![](screenshots/page-2026-10-25T20-43-01-000Z-mobile-short-list-covered.png)
![](screenshots/page-2026-10-25T20-43-00-000Z-mobile-bottom.png)

- **Expected:** Below md, with rows selected, every card's checkbox can be scrolled clear of the fixed bottom selection bar and tapped.
- **Actual:** The bar (about 219px tall at 375x812, three stacked buttons) is `position: fixed` at the bottom and the list has no matching bottom space. Even fully scrolled, the last card's checkbox sits under the bar (bulk19 checkbox top 612 vs bar top 593). On a two-row list the second checkbox cannot be ticked at all once the first is.

## Bug status

| Bug | Status |
|---|---|
| B1 | **FIXED** (commit: 795356deb) — Mobile selection bar covers the last rows' checkboxes |

Re-verified at 375x812 on the learners list (10 rows) and Cohort A's 5 learners: with a row ticked and the page scrolled to the bottom, the last checkbox is clear of the bar and can be ticked. Spot-checked the cohorts list on mobile and the learners, cohorts and members lists on desktop, with no regressions.

![](screenshots/page-2026-10-25T21-00-00-000Z-b1-fixed-mobile.png)

## General notes

- List pages hold 10 rows. The plan assumed 25.
- Bulk action labels read "Register for course" and "Unregister from course" (spec says "for a course") because they reuse the single-learner labels.
- After unticking a row in all-matching mode, the prompt still says "All 29 matching are selected."
- The result headline says "0 rows were not added" when nothing failed (5.2).
- A preview with nothing to add still says "0 new accounts will get a setup email." (3.4)
- The cohort deactivate confirm says "its 0 courses" while the delete line counts "1 course registration". This is also on main (7.6).
- Cohort bulk register wording is "1 is inactive", where the plan said "1 is an inactive cohort" (7.2).
- Plan data drift was handled by substitutions:
  - 6.10: search is a single substring and pages hold 10 rows, so the "solo" learner cannot share a page with bulk20/21. bulk22, registered individually first, was used instead.
  - 6.11: import01 and cohortimp were emailed inside the 15-minute resend window, so pending, ada and cohortimp were used.
  - 7.4: A was registered for Course Hid in 7.2 and B in the seed, so unregistering A+B was correctly not a skip. The skip path was covered with A+C.
  - 8.1: Ben was already in A and B had been emptied, so Ada was added to B first.
- The Resend setup email confirm cannot foresee cooldown skips. This is by design; they appear only in the result.

status: ok
reason: 1 bug — 1 fixed, 0 unresolved; report rendered, screenshots verified
