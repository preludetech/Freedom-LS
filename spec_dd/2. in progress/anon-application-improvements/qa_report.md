# Frontend QA report: anon-application-improvements

## Methodology

- Manual walk of the plan (`3. frontend_qa.md`) with Playwright MCP against a dev server on port 8718, on branch `anon-application-improvements`.
- Mailpit was read through its API to check emails.
- "Fresh browser" steps used fresh browser contexts.
- Desktop (1920x1080) ran §1–§7. Mobile (375x812) and tablet (768x1024) ran §7 only. §7 is the layout section: notice, status page with error, claim confirm, dashboard.
- The dev DB was empty and bootstrapped. Seed data was set up by the QA data helper.
- In 3.3 step 3, the POST was sent with Playwright's request API, carrying the session cookie and CSRF token.
- Screenshots are in `screenshots/` beside this report. Every image referenced below exists there.

## Diff scoping

Class: FULL, because templates changed. Nothing was skipped.

Changed files considered:
- `freedom_ls/course_applications/templates/course_applications/*.html`
- `freedom_ls/course_applications/templates/course_applications/partials/claim_link_notice.html`
- `freedom_ls/learner_interface/templates/learner_interface/dashboard.html`
- `freedom_ls/course_applications/*.py`
- `freedom_ls/course_access/backends.py`
- `freedom_ls/accounts/forms.py`
- `freedom_ls/learner_interface/views.py`
- migration 0007

## Smoke gate

Pass. Pages checked:
- `/`
- `/courses/functionality-demo-application-gated-course/detail/`
- `/applications/apply/functionality-demo-application-gated-course/`

No failure URL or reason.

## Results table

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 1.1 | desktop | pass | One email sent on the details step; body says the link confirms the address and returns them to the application, button "Continue your application", no review wording. Info-tinted notice with "Send the link again" and "Wrong address? Change it" on pages 1 (also after reload), 2, 3 and Check your answers. | ![](screenshots/page-2026-10-18T16-23-13-885Z.png) ![](screenshots/page-2026-10-18T16-25-17-640Z.png) |
| 1.2 | desktop | pass | Change form prefilled; name-only change sent no email; new address got exactly one email and the notice named it; old link in a fresh context is invalid. Returned to page 3 (furthest page reached). | none |
| 1.3 | desktop | pass | Resend toast shown, same page, answers intact, one more email. Earlier link in a fresh context still opens the confirm page. | ![](screenshots/page-2026-10-18T16-25-56-555Z.png) |
| 1.4 | desktop | pass | Submit sent no email. Status page names the address, has "Send the email again" and a one-field change form. | ![](screenshots/page-2026-10-18T16-26-11-694Z.png) |
| 2.1 | desktop | pass | Claim in a second context: confirm page, set-password, landed on page 2 signed in with no notice. Dashboard shows the course Incomplete with Continue application. Original browser goes to login; reused link is invalid. | ![](screenshots/page-claim-confirm-draft.png) ![](screenshots/page-claim-landed-draft.png) ![](screenshots/page-claim-dashboard.png) |
| 2.2 | desktop | pass | Admin filter "email verified: Verified" lists qa_claim_draft@email.com, Submitted unticked. | ![](screenshots/page-2026-10-18T16-27-23-295Z.png) |
| 3.1 | desktop | pass | Change to qa_change_b: toast, status page names the new address, one email with subject "Finish your application for ...". Old link invalid; new link opens the confirm page. | ![](screenshots/page-2026-10-18T16-27-49-523Z.png) |
| 3.2 | desktop | pass | Case-only change: 302 to status, no toast, no email. Invalid and empty values: 422 with field errors, no toast or email. | ![](screenshots/page-2026-10-18T16-28-12-457Z.png) |
| 3.3 | desktop | pass | Fresh context on the status URL goes to login. Submitted application shows pending review with no change form. POST change-email for a verified application returns 404; GET from the owning session returns 405. | ![](screenshots/page-held-submitted-status.png) |
| 4.1 | desktop | pass | Collision page says the unfinished application will be discarded and the user will be signed in. Confirm lands on the submitted status page. No AnonymousApplicant row left; one CourseApplication. | ![](screenshots/page-claim-confirm-collision.png) |
| 4.2 | desktop | pass | Confirm page says it replaces the account's unfinished application. Confirm lands on the incoming draft page 2; dashboard lists the course once as Incomplete. | none |
| 4.3 | desktop | pass | Login toast says the existing application was kept; dashboard shows one application Pending review; no AnonymousApplicant row in admin. | ![](screenshots/page-login-adopt-kept.png) |
| 4.4 | desktop | pass | Login toast says the unfinished application was replaced by the one just started; dashboard lists the course once as Incomplete; page 1 shows the session draft's name. | ![](screenshots/page-login-adopt-replaced.png) |
| 5.1 | desktop | pass | Second course's details step opened empty. Dashboard lists both drafts, second course first, with Continue application. Page HTML has none of the applicant's details. | ![](screenshots/page-2026-10-18T16-30-30-861Z.png) |
| 5.2 | desktop | pass | Applied course shows "View my application"; form-less course shows "Apply now". Fresh context has no Your applications panel. | none |
| 5.3 | desktop | pass | After submitting the first course, the panel shows only the second draft; the first course's "View my application" goes to the status page. | none |
| 6 | desktop | pass | Form-less course: confirmation shown with no email yet; submit sends one email and shows the status page with the change form. | none |
| 7.1 | desktop | pass | No horizontal scroll. Sent state has info tint; not-sent state has warning tint. | ![](screenshots/layout-desktop-notice-not-sent.png) ![](screenshots/layout-desktop-notice-sent.png) |
| 7.2 | desktop | pass | Status page with field error; no horizontal scroll. | ![](screenshots/layout-desktop-status-field-error.png) |
| 7.3 | desktop | pass | Claim confirm with collision sentence; no horizontal scroll. | ![](screenshots/layout-desktop-claim-collision.png) |
| 7.4 | desktop | fail | No horizontal scroll, but the Your applications list is indented ~17px from its heading. See B1. | ![](screenshots/layout-desktop-dashboard-two-drafts.png) |
| 7.1 | mobile | pass | No horizontal scroll; both actions wrap onto their own lines inside the callout. "Send the link again" is 34px high. | ![](screenshots/layout-mobile-notice-not-sent.png) ![](screenshots/layout-mobile-notice-sent.png) |
| 7.2 | mobile | pass | Fits 375px; no horizontal scroll. | ![](screenshots/layout-mobile-status-field-error.png) |
| 7.3 | mobile | pass | Fits; no horizontal scroll. | ![](screenshots/layout-mobile-claim-collision.png) |
| 7.4 | mobile | fail | No horizontal scroll, but rows start at x~40 while heading and hero start at x=16. See B1. | ![](screenshots/layout-mobile-dashboard-two-drafts.png) |
| 7.1 | tablet | pass | No horizontal scroll; actions sit side by side in the callout. | ![](screenshots/layout-tablet-notice-not-sent.png) ![](screenshots/layout-tablet-notice-sent.png) |
| 7.2 | tablet | pass | No horizontal scroll. | ![](screenshots/layout-tablet-status-field-error.png) |
| 7.3 | tablet | pass | No horizontal scroll. | ![](screenshots/layout-tablet-claim-collision.png) |
| 7.4 | tablet | fail | No horizontal scroll, but rows start at x~48 while heading and course cards start at x=24. See B1. | ![](screenshots/layout-tablet-dashboard-two-drafts.png) |

## Design check

no design states tested

## B1: Dashboard "Your applications" list is indented from its heading

Manifestations:
- 7.4, desktop
- 7.4, mobile
- 7.4, tablet

![](screenshots/layout-desktop-dashboard-two-drafts.png)
![](screenshots/layout-mobile-dashboard-two-drafts.png)
![](screenshots/layout-tablet-dashboard-two-drafts.png)

Expected: the application rows line up with the "Your applications" heading and the course sections' left edge, as every other dashboard section does.

Actual: the `<ul>` in `course_applications/partials/dashboard_applications.html` keeps a default left padding, so the rows start ~24px right of the heading (x 40 vs 16 on a phone, 48 vs 24 on a tablet). On small screens this narrows the cards. The partial is unchanged on this branch, so signed-in learners on main are affected too.

## Bug status

- **FIXED** (commit: 188fdd02) — Dashboard "Your applications" list is indented from its heading. The `<ul>` now has `list-none ml-0`. Re-verified in the browser: rows line up with the heading at 375px (16/16), 768px (24/24) and 1920px (352/352), and on a signed-in learner's dashboard at 375px.

![](screenshots/fixed-mobile-dashboard.png) ![](screenshots/fixed-tablet-dashboard.png) ![](screenshots/fixed-desktop-dashboard.png)

## General notes

- The email greeting is a bare "Hi," though a first name was given (1.1).
- "Wrong address? Change it" brings back the details step with both consent boxes unticked, so they must be re-ticked on every address change (1.2).
- The claim confirm page copy stacks "You'll then ..." sentences: "You'll then be taken back to your application. You'll then choose a password...". The order is reversed against the real flow (password first). On the collision page, "taken back to your application" sits next to "This unfinished application will be discarded" (1.3, 4.1).
- After a 422 on the change-address form the URL stays at `/change-email/`, so reloading or revisiting it shows a blank 405 (3.2).
- The test plan's course URL `/courses/<slug>/` is login-required. The anonymous course page is `/courses/<slug>/detail/`. The plan should be updated.
- The §7.1 not-sent state was produced by clearing `claim_email_sent_at` through the data helper, not by stopping mail delivery, because Mailpit is shared. The send-failure path is covered by the test suite.
- Rate limits were not checked (dev turns them off), as the plan says.
- Claimed AnonymousApplicant rows stay in admin after a claim (qa_claim_draft and qa_held_draft shown verified). Observation only.
- Mobile: the notice's "Send the link again" button is 34px high, under a 44px touch target.
- A hidden "Couldn't load your notifications" alert sits in the DOM (`display:none`). It is not a problem; it is recorded because a text scrape picks it up.

status: ok · reason: 1 bug — 1 fixed, 0 unresolved; report rendered, screenshots verified
