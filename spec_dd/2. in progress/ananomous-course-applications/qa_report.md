# QA report: anonymous course applications

The run recorded 27 test results (including three viewport passes of the layout section). 25 passed and 2 failed (1.4 and 6.3). Two bugs were documented: B1 (the unverified status page offers Back to dashboard to an anonymous applicant) and B2 (the admin labels an unclaimed application as `CourseApplication(None, <course uuid>)`). The smoke gate passed.

## Methodology

The run drove the dev server on port 8784 with Playwright MCP at 1920x1080 for the functional sections and at 375x812, 768x1024 and 1280x800 for the layout section. Mailpit was read through its API. Screenshots were collected into `spec_dd/2. in progress/ananomous-course-applications/screenshots/`, and every referenced image exists beside this report.

Two URL substitutions were made against the test plan. The plan's `/courses/<slug>/` URL is the login-required resume redirector, and the public page is `/courses/<slug>/detail/`. The plan's URLs also omit the `/applications/` prefix, so that prefix was added.

Native `required` attributes block an empty submit in the browser, so the server-side 422 branches were exercised with the form set to `noValidate`.

## Diff scoping

Class: FULL. Files that triggered it:

- `freedom_ls/course_applications/templates/course_applications/applicant_details.html`
- `freedom_ls/course_applications/templates/course_applications/application_status.html`
- `freedom_ls/course_applications/templates/course_applications/apply.html`
- `freedom_ls/course_applications/templates/course_applications/claim.html`
- `freedom_ls/course_applications/templates/course_applications/email/*`
- `freedom_ls/course_applications/templates/course_applications/partials/applicant_details_field.html`
- `freedom_ls/accounts/templates/cotton/consent-checkboxes.html`
- `freedom_ls/base/templates/account/signup.html`
- `freedom_ls/base/templates/allauth/layouts/manage.html`
- `freedom_ls/course_applications/views.py`
- `freedom_ls/course_applications/claims.py`
- `freedom_ls/course_applications/admin.py`
- `freedom_ls/form_engine/views.py`
- `freedom_ls/form_engine/admin.py`
- `freedom_ls/accounts/forms.py`
- `freedom_ls/accounts/models.py`
- plus tests, migrations, docs and qa_helpers

Desktop, mobile and tablet passes all ran. Nothing was skipped.

## Smoke gate

Status: pass. Pages checked:

- `http://127.0.0.1:8784/` (anonymous home with the branch badge `ananomous-course-applications`; signed in as the claimed applicant it rendered the dashboard with the application listed)
- `http://127.0.0.1:8784/applications/apply/functionality-demo-application-gated-course/your-details/` (primary changed page, 200 with the details form)
- `http://127.0.0.1:8784/admin/` (signed in as demodev@email.com)

## Test results

| Test | Viewport | Status | Notes |
|---|---|---|---|
| 1.1 | desktop | pass | Apply now on the public detail page goes to the details step with no login or signup. Fields, two consent checkboxes linking to terms and privacy (target=_blank), no password field, honeypot hidden. ![](screenshots/page-2026-10-12T13-50-05-354Z.png) |
| 1.2 | desktop | pass | With noValidate the server returns 422 with required errors on Email, First name and both consents; invalid email message shown; typed values kept; no Mailpit message and no AnonymousApplicant created. ![](screenshots/page-2026-10-12T13-50-44-358Z.png) |
| 1.2-honeypot | desktop | pass | `fax_number=x` returns 422 with the callout "We could not process this application…". Plan expected "sign-up" wording (see General notes). No AnonymousApplicant created. ![](screenshots/page-2026-10-12T13-51-06-137Z.png) |
| 1.3 | desktop | pass | Valid details (email trimmed and lowercased) land on page 1 of the application with page links 1 2 3. Previous shows the details prefilled, checkboxes unticked; Next returns to the same application. ![](screenshots/page-2026-10-12T13-51-26-098Z.png) |
| 1.4 | desktop | **fail** | Pages, upload (download, remove, re-upload), check-your-answers, edit and submit all work; status page shows received copy and emailed-link sentence; one correct Mailpit message; apply and details URLs redirect to status. FAIL: the status page shows a Back to dashboard button (href `/`) for an anonymous visitor; the plan expects a back-to-course button instead (B1). Reopening page 1 of the submitted application gives 404 (see General notes). ![](screenshots/page-2026-10-12T13-53-25-123Z.png) |
| 1.5 | desktop | pass | Fresh context: status, page 1 and check-your-answers 302 to login; file URL 404. Signed-in non-owner: status 404, file 404. Nothing exposed. |
| 3.1 | desktop | pass | GET on the claim link renders the confirm page with one Confirm button, Cache-Control no-store; reloads identical; no User created by the GETs. ![](screenshots/page-2026-10-12T13-55-24-235Z.png) |
| 3.2 | desktop | pass | Confirm signs in and redirects to set-password with next=status; status shows pending-review copy; dashboard lists the application; user, verified email and two LegalConsent rows exist. Reopened claim link shows invalid. ![](screenshots/page-2026-10-12T13-55-40-575Z.png) ![](screenshots/page-2026-10-12T13-55-58-762Z.png) |
| 2 | desktop | pass | Form-less course: details step, confirmation page (Submit application, Previous), status page with emailed-link sentence. Back button and a second POST both land on the same status page; one email, one application row. ![](screenshots/page-2026-10-12T13-56-24-989Z.png) |
| 3.3 | desktop | pass | Existing-user email: Confirm signs in directly on the status page with no set-password; first name unchanged; no new LegalConsent rows; application attached and verified. |
| 3.4 | desktop | pass | Other-site email behaves like section 2; the claim link renders the invalid page already on GET (no Confirm); visitor stays signed out; no user created; application stays unverified. |
| 3.5 | desktop | pass | Inactive user: Confirm redirects to login, still signed out; application attached to the inactive user, verified, claimed_at set. ![](screenshots/page-2026-10-12T13-57-47-856Z.png) |
| 3.6 | desktop | pass | Tampered token shows invalid; four-day-old token shows expired with Send a new link; pressing it sends one new email; the new link confirms as in 3.2. ![](screenshots/page-2026-10-12T13-58-37-053Z-expired.png) |
| 4 | desktop | pass | Signed-in applicant: Apply now goes straight to page 1 with no details step and an empty left footer slot; details URL redirects into the application; the form-less course shows View my application. |
| 5 | desktop | pass | With require_name and require_terms_acceptance off the details step drops the checkboxes and makes first name optional; with allow_signups off the details step is unchanged while `/accounts/signup/` shows Sign Up Closed. Policy restored. ![](screenshots/page-2026-10-12T13-59-37-644Z-policy.png) |
| 6.1 | desktop | pass | Applications changelist shows an Email verified column with ticks and crosses and the anonymous applicant in the Applicant columns. ![](screenshots/page-2026-10-12T14-00-24-162Z.png) |
| 6.2 | desktop | pass | Email verified filter (Verified / Unverified) works; search by email finds the row. |
| 6.3 | desktop | **fail** | Change page shows the expected summary rows. FAIL (cosmetic): page title, breadcrumb and delete-confirmation listings label the application `CourseApplication(None, 53fc7929-...)` (B2). |
| 6.4 | desktop | pass | Form progress records changelist shows Applicant = Unverified: email; change page has summary row and Application link. Search box does not match the anonymous email (see General notes). ![](screenshots/page-2026-10-12T14-02-25-420Z-form-progress-change.png) |
| 6.5 | desktop | pass | Question answer files changelist shows the unverified applicant; Download returns 200 image/png. |
| 6.6 | desktop | pass | Anonymous applicants changelist has the expected columns, no Add button, search works; change page is read-only with a Delete link. ![](screenshots/page-2026-10-12T14-02-21-311Z-anon-applicant-change.png) |
| 6.7 | desktop | pass | Single delete confirmation lists 1 applicant and 1 application; delete succeeds and both are gone. ![](screenshots/page-2026-10-12T14-02-55-452Z-anon-delete-confirm.png) |
| 6.8 | desktop | pass | Bulk delete lists 2 applicants and 2 applications; after confirming, applicants, applications, form progress record and file are all gone. ![](screenshots/page-2026-10-12T14-03-25-721Z-bulk-delete-confirm.png) |
| 6.9 | desktop | pass | Deleting the claimed user lists and removes form progress, answers, file, consents, signup attribution, applicant, application and email address. User change page showed the two Legal consents rows. ![](screenshots/page-2026-10-12T14-03-32-205Z-user-delete-confirm.png) ![](screenshots/page-2026-10-12T14-02-54-389Z-user-change-consents.png) |
| 7 | mobile (375x812) | pass | No horizontal scroll on the five pages; footer buttons stack full width with Next above Previous; consent labels on one line. The status page shows Back to dashboard (B1). ![](screenshots/page-2026-10-12T14-05-00-839Z-mobile-details-errors.png) ![](screenshots/page-2026-10-12T14-05-01-357Z-mobile-claim-confirm.png) ![](screenshots/page-2026-10-12T14-05-01-763Z-mobile-claim-expired.png) ![](screenshots/page-2026-10-12T14-05-02-270Z-mobile-claim-invalid.png) ![](screenshots/page-2026-10-12T14-05-02-649Z-mobile-status-unverified.png) |
| 7 | tablet (768x1024) | pass | No horizontal scroll on any of the five pages; Previous and Next on one row; consent labels on one line. ![](screenshots/page-2026-10-12T14-05-03-618Z-tablet-details-errors.png) ![](screenshots/page-2026-10-12T14-05-04-164Z-tablet-claim-confirm.png) ![](screenshots/page-2026-10-12T14-05-04-522Z-tablet-claim-expired.png) ![](screenshots/page-2026-10-12T14-05-04-927Z-tablet-claim-invalid.png) ![](screenshots/page-2026-10-12T14-05-05-377Z-tablet-status-unverified.png) |
| 7 | desktop (1280x800) | pass | No horizontal scroll on any of the five pages; footer buttons on one row; consent labels on one line. ![](screenshots/page-2026-10-12T14-05-06-257Z-desktop1280-details-errors.png) ![](screenshots/page-2026-10-12T14-05-06-868Z-desktop1280-claim-confirm.png) ![](screenshots/page-2026-10-12T14-05-07-320Z-desktop1280-claim-expired.png) ![](screenshots/page-2026-10-12T14-05-07-687Z-desktop1280-claim-invalid.png) ![](screenshots/page-2026-10-12T14-05-08-098Z-desktop1280-status-unverified.png) |

## Design check

no design states tested

### B1 Unverified status page offers Back to dashboard to an anonymous applicant

Manifestations:

- Test 1.4, desktop
- Test 7, mobile

![](screenshots/page-2026-10-12T13-53-25-123Z.png)
![](screenshots/page-2026-10-12T14-05-02-649Z-mobile-status-unverified.png)

Expected: Per the test plan, the status page an anonymous applicant sees after submitting has a button back to the course and no Back to dashboard button (the visitor has no account and no dashboard).

Actual: `application_status.html` always renders the Back to dashboard button (href `/`), which takes the signed-out visitor to the public home page. The spec is silent on this button, so the plan and the code disagree.

### B2 Admin labels an unclaimed application as CourseApplication(None, <course uuid>)

Manifestations:

- Test 6.3, desktop

![](screenshots/page-2026-10-12T14-02-55-452Z-anon-delete-confirm.png)
![](screenshots/page-2026-10-12T14-03-25-721Z-bulk-delete-confirm.png)

Expected: The admin change page title, breadcrumb and delete-confirmation listings identify an unverified application without printing None. The label must stay free of the email: `AnonymousApplicant.__str__` omits it on purpose because the admin log outlives erasure.

Actual: `CourseApplication.__str__` returns `f"CourseApplication({self.user_id}, {self.course_id})"` and `user_id` is None before the claim, so every admin label reads `CourseApplication(None, 53fc7929-...)`.

## Bug status

**UNRESOLVED** — Unverified status page offers Back to dashboard to an anonymous applicant (reason: product decision; the spec is silent, the test plan expects a button back to the course and no Back to dashboard, and the template always renders Back to dashboard. Decide which, then change `application_status.html` to match)
**FIXED** (commit: 2b303f3f) — Admin labels an unclaimed application as CourseApplication(None, <course uuid>). `CourseApplication.__str__` now prints `CourseApplication(anonymous <applicant id>, <course id>)` for an unclaimed application and keeps `CourseApplication(<user id>, <course id>)` for a claimed one; the label stays free of the email. Re-verified in the browser on the change page and on the anonymous-applicant delete confirmation:

![](screenshots/page-2026-10-12T14-11-05-138Z-B2-reverify-delete-confirm.png)

## General notes

None of these is a bug.

- Honeypot copy: the live message says "We couldn't process this application…" where the plan expected "We couldn't process this sign-up…"; the application wording fits the context.
- The plan expects strangers to get 404 on the status / page / check-your-answers URLs; a cookie-less visitor is instead 302-redirected to the login page whether or not the application exists (documented in `_owned_application`), which discloses nothing. A signed-in non-owner gets 404 as expected.
- Plan step 1.4.8 expects a submitted anonymous application's page 1 to render read-only in the owning session; the code returns 404 on purpose (a visitor session reaches the sitting only while it is a draft).
- The other-site claim link renders the invalid page already on GET, so there is no Confirm to press (stricter than the plan).
- The Form progress records admin search box does not match an anonymous applicant's email.
- The bulk-delete confirmation page itemises the applicants and applications but not the form progress record and file that the receiver removes; they were gone afterwards.
- After a single anonymous-applicant delete the admin redirected to the admin index rather than the changelist.
- Rate limits were not tested (`ACCOUNT_RATE_LIMITS` is off in `settings_dev.py`), per the plan.
- Residue this run left in the dev database: unclaimed anonymous applicants qa_consent@email.com, qa_closed_signup@email.com and qa_layout@email.com, claimed applications for qa_existing_applicant, qa_inactive and qa_resend, and an unsubmitted form-course application for qa_existing_applicant. Mailpit was emptied at the start of the run.

status: ok
reason: 2 bugs — 1 fixed (2b303f3f), 1 unresolved (product decision); report rendered, screenshots verified
