# Research: the anonymous course application flow as it is today

Groundwork for `idea.md`: (A) send the claim email after the applicant details step instead of
after submit; (B) show an anonymous applicant's incomplete application at the top of the dashboard.
Source: code in `freedom_ls/course_applications/`, `freedom_ls/form_engine/`,
`freedom_ls/learner_interface/`, plus the finished spec
`spec_dd/3. done/2026-10-12_18:37_ananomous-course-applications/1. spec.md`.

## Names to reuse (from the finished spec and code)

`AnonymousApplicant`, applicant details step (URL name `applicant_details`, view
`applicant_details`, template `applicant_details.html`; `application_details` is only the allauth
rate-limit action), claim link, claim page (`claim.html`, states `confirm` / `expired` / `resent` /
`invalid`), unverified application (`CourseApplication.user` null; property `is_email_verified`),
session map (`course_applications/anonymous_session.py`), allowed sitting
(`form_engine/session_access.py`), `claims.py`, `applicant_email.py`, erasure. Dashboard
contribution: `DashboardContribution` / "applications panel" / "Your applications" panel
(`course_applications/partials/dashboard_applications.html`). `domain_vocabulary.md` has no entries
for these terms; `docs/` has no glossary file, but `docs/product/{authentication,admin-interface,
security-and-data-handling,signup-attribution,webhooks}.md` already use "anonymous applicant",
"claim link" and "unverified application".

## 1. The claim email today

- Sent by `send_application_claim_email(request, applicant)` in `course_applications/emails.py`.
  Returns bool. Templates: `course_applications/email/application_claim_message.{html,txt}`
  (subject/prefix via allauth `get_adapter(request).send_mail`). Context: course, `claim_url`,
  site name, `user=None`.
- Call sites (all in `course_applications/views.py`), each only once the application is submitted:
  1. `application_check_answers` POST, after `form_progress.complete()` and
     `record_application_submitted`, for a form course (only when `app.anonymous_applicant` set and
     not verified).
  2. `_anonymous_apply` POST on a form-less course (creating the application is the submission),
     after `record_application_submitted`.
  3. `application_status` POST: manual "Send the email again", only for an unverified application
     with an applicant (404 otherwise).
  4. `claim_application` POST on an expired token: "send a new link".
- NOT sent by `applicant_details`. That view saves `AnonymousApplicant` (`form.save()`),
  `remember_anonymous_applicant`, and for a form course calls `_start_application` (creates the draft
  `CourseApplication` with user null and a `FormProgress` with user null),
  `allow_anonymous_form_progress`, redirects to `_resume_url`. For a form-less course it redirects
  to `apply`, which shows `apply.html` and only on its POST creates the application and sends.
- Link/token: `claims.claim_token` = `django.core.signing.dumps(str(applicant.pk), salt=
  "freedom_ls.course_applications.claim")`; `claim_url` builds the absolute URL for
  `course_applications:claim` (`claim/<str:token>/`). Expiry: `read_claim_token` uses
  `allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS` (nothing in `config/` overrides it, so
  allauth's default applies). Expired token: signature still good, `ClaimLink.expired=True`.
- Rate limit (`config/settings_base.py:460-461`): `application_claim_email` = `3/h/key`, key
  `email_rate_limit_key(site, email)` (`applicant_email.py`), consumed inside the send function
  (counts every attempt, including the resend). Over limit or backend error (`OSError`,
  `QueuedEmailNotSentError`) returns False and leaves `claim_email_sent_at` unset. On success sets
  `AnonymousApplicant.claim_email_sent_at`. `settings_dev.py` has `ACCOUNT_RATE_LIMITS = False`.
- Note: the callers at sites 1 and 2 ignore the False return; the status page covers it by checking
  `claim_email_sent_at` (shows "We couldn't email ... just now" plus a resend form if null).

### What following the link does (`claim_application`, `claims.py`)

- GET never changes state. It renders "invalid" (identical page, `Cache-Control: no-store`) when:
  bad signature; `applicant.claimed_at` set; no application (`application_of` is None); or
  `not application.is_submitted`. Then "expired" if the token is old. Then, if the email's owner
  (`resolve_claim_owner`: verified `EmailAddress` iexact, else `User._base_manager` email iexact)
  is on another site, "invalid". Otherwise "confirm" (names the address, whether a password will
  be set, and whether the browser is signed in as someone else).
- POST (confirm): if signed in as somebody else, `adapter.logout` first. Then
  `attach_claimed_application(request, application)` in one transaction with `select_for_update`
  on the applicant:
  - no account: `_create_claimed_user` (unusable password, verified primary `EmailAddress`),
    `_write_legal_consents` (`consent_method="application_details_step"`, from the stored version,
    git hash, IP on the applicant), then `attach_to_user`; after commit `announce_user_registered`
    and `user_signed_up` (attribution and sign-up analytics from the claiming request);
  - existing same-site account: verified owner is attached as is; an unverified owner has the address
    verified, password revoked, consent written; no sign-up announced;
  - `attach_to_user` locks the user row, resolves a second application for the same course (a
    submitted one beats a draft, otherwise the one already on the account stays; loser erased via
    `erase_anonymous_applicant` or `_discard_draft`), sets `user` on the `CourseApplication`, the
    `FormProgress`, and the applicant, and `claimed_at`.
  - Uploads: nothing is moved; `QuestionAnswerFile` paths stay under
    `user_uploads/anonymous/<form_progress_id>/...`; consent: see above.
- Afterwards `forget_anonymous_applicant(request, link.applicant)` (current session only), inactive
  user goes to `account_login`, otherwise `adapter.login(request, user)` (rotates the session key),
  then redirect to `account_set_password?next=<status url>` if `must_set_password`, else the status
  page.

### If the link is followed while the application is still a draft (change A)

- Today it renders the "invalid link or already used" page, by design (`not
  application.is_submitted`). With early sending, every link emailed before submit would show that
  until the applicant finishes. DECISION NEEDED: either keep that but give the draft case its own
  message/state (e.g. "finish your application first", ideally with a way back if this browser holds
  the session), or let the claim go through on a draft.
- If a claim were allowed on a draft, things that depend on `is_submitted`/draft and need a decision:
  - `attach_to_user` and its draft-vs-submitted tie-break (`held.is_submitted or not
    application.is_submitted` -> incoming loses): an incoming draft loses to an account's held
    application of any kind; a held draft loses to an incoming submitted one. A claim of a draft
    for a course the account already applied to would erase the new draft.
  - `FormProgress.user` is set at claim, so the sitting stops being session-allowed
    (`owned_form_progress` only serves user-less, non-completed sittings in the session's list).
    The form-page views use `owned_applications`, which for the claimant's own signed-in session
    resolves by `user=request.user`, so continuing signed in works; the original browser's
    anonymous session no longer resolves it (applicant has `user` set, filtered out by
    `user__isnull=True`), so it would get redirect-to-login via `_owned_application` (see 4).
  - Redirect target after claim is the status page; `application_status` redirects a draft back to
    `_resume_url`, so a signed-in claimant lands on their form page. Fine.
  - Email-claim fires `user.registered`, attribution, `LegalConsent` writes for a not-yet-submitted
    application, so a user and consent rows exist for applicants who may never submit. (Staff
    visibility: the draft application then belongs to a real `User`.)
  - `read_claim_token` and the "no submitted application -> invalid" rule are relied on by
    `claim_application` and are tested (see section 6).
  - Early sending also changes `claim_application`'s "expired" resend and the status page copy
    ("received ... a reviewer will look at it"), which assume a submitted application.
  - Rotated/duplicated applicants: the details step can create or re-address the applicant; every
    link for the same applicant pk stays valid, since the token only encodes the pk. A changed email
    changes what the same older token lands on (the token carries the pk, not the address), so
    an old link sent to the previous mailbox would, if allowed on a draft, claim to the NEW
    address. Today this cannot happen because a link only goes out at submit, after which the
    details step redirects to status (`app.is_submitted`) and the address is frozen. With early
    sending this is a real hole: DECISION NEEDED (bind the token to the address, or invalidate on
    change, or freeze).

### If the link is followed in a different browser

- Works today and needs no session: the claim looks up everything from the token and the DB.
  The user is logged in in the new browser; the origin browser's session map still lists the
  applicant but `remembered_anonymous_applicant(s)` / `anonymous_applicant_for_course` /
  `owned_applications` filter `user__isnull=True`, so it stops resolving. The origin browser then
  sees an anonymous visitor with nothing (`apply` would send it to the details step to start a new
  applicant; a stale status URL redirects to login).
- For a submitted application this is the intended behaviour (state "ready for review", the
  claimant continues signed in). For a draft (change A), the claimant in the new browser would
  have to continue the draft there, which is workable because it is by `user`, but the answers
  already typed in the first browser are not lost (they sit on the DB sitting).
- Uploaded files and answers are all DB-side; only the session pointers are browser-specific.

## 2. How the in-progress anonymous application is stored

- DB models (`course_applications/models.py`): `AnonymousApplicant` (SiteAwareModel; course FK,
  `email` lowercased, names, consent evidence, nullable `user`, `claimed_at`,
  `claim_email_sent_at`); `CourseApplication` (nullable `user`; nullable OneToOne
  `anonymous_applicant`; OneToOne RESTRICT `form_progress`; `is_submitted` = no sitting or sitting
  has `completed_time`; `is_email_verified` = `user_id is not None`). `form_engine.FormProgress`
  (nullable `user`) holds the answers; draft until `complete()` stamps `completed_time`.
- Session (`SESSION_ENGINE` not set, so Django's DB-backed sessions):
  - `course_applications_anonymous_applicants`: dict course id -> applicant pk
    (`anonymous_session.py`: `remember_/forget_anonymous_applicant`,
    `anonymous_applicant_for_course`, `remembered_anonymous_applicants`, `owned_applications`).
  - `form_engine_anonymous_form_progress`: list of allowed user-less sitting pks
    (`form_engine/session_access.py`: `allow_anonymous_form_progress`, `owned_form_progress`,
    which serves only non-completed sittings). It is used by the form_engine upload/download
    endpoints; the application pages use `owned_applications` instead, plus the rule in
    `_owned_application_with_form` that a submitted user-less application's sitting is 404.
- Only ids are in the session, never answers or the email. So the session is just a pointer; the
  draft state is fully DB-side and survives anything that keeps the session cookie.
- Lifetime: `SESSION_COOKIE_AGE = 1209600` (2 weeks) in `config/settings_prod.py:51`; dev/base use
  Django's default (also 2 weeks). `SESSION_SAVE_EVERY_REQUEST` and `SESSION_EXPIRE_AT_BROWSER_CLOSE`
  are not set, so the expiry is fixed 2 weeks from the last time the session was modified (not
  extended by reads), the cookie persists across browser close. Prod cookie: Secure, HttpOnly,
  SameSite Lax. Session login rotates the key, which is why `adopt_anonymous_applications_on_login`
  (`receivers.py`, on `user_logged_in`) must read the map during the signal; it attaches applications
  whose address the new user has verified and then clears both session pointers.
- Retention/cleanup: none. Spec says explicitly "Automatic purging: out. Anonymous applicants,
  drafts and unverified applications are kept until an operator erases them" (admin delete on
  `AnonymousApplicantAdmin`, `erase_anonymous_applicant`, `erase_unclaimed_applicants_with_the_
  users_address` on user delete, QA reset commands). `fls_run_housekeeping` / `housekeeping.py`
  only runs `clearsessions` (expired sessions); it does not touch applicants. An expired session
  orphans the draft: the DB rows stay, the browser can no longer reach them, and the applicant
  starts again at the details step (a new `AnonymousApplicant` row and a second draft for the same
  email).

## 3. Resending and re-entering the details step

- Resend paths: (a) status page POST (`application_status`), shown only for an application that is
  submitted-or-form-less (a draft is redirected to its form before the page renders, so a draft has
  no resend today); both buttons post to the same view; (b) claim page POST when expired. Both go
  through `send_application_claim_email`, so both spend `application_claim_email` (3/h per
  site-and-email key). No separate cooldown.
- Re-entering the details step (`applicant_details`): the session's applicant for the course is
  loaded and the form is bound to it (same `AnonymousApplicant` row, edited in place, no second
  row). If the application is already submitted it redirects to status. Rate limit
  `application_details` = `5/m/ip,5/h/key`: spent (`consume_or_429`, after a dry-run check) only when
  the normalised email is new or differs from the stored one (`would_spend`); a name-only change is
  free and never refused. A honeypot trip spends the bucket. In-flight double-click guard: a cache
  key (`_details_in_flight_key`, 10 s) so two first POSTs create one applicant.
- Same email: nothing is spent, nothing is sent (nothing is sent anyway today). Different email:
  the stored email is overwritten, one `application_details` unit spent; the claim email has not
  been sent, so there is no old link out there. After change A there would be: a link already sent
  to the old mailbox (see section 1 hole) and the need to resend to the new address (and a decision
  whether a changed address should send again automatically, which spends `application_claim_email`
  for the new key; and whether the old key's bucket matters). The first POST also needs a decision on
  ordering: the claim email would be sent from inside `applicant_details`, after `form.save()`,
  before the redirect.
- A mistyped email today cannot be corrected after submit (spec open question); with early
  sending it can be corrected during the draft via the details step (reachable from page 1's
  Previous).

## 4. Dashboard / home page

- URL name `learner_interface:dashboard`, view `learner_interface/views.py: dashboard` (line
  ~616), template `learner_interface/dashboard.html`. Same view and template for anonymous and
  authenticated visitors; no login redirect.
  - Anonymous: `learner_interface/partials/anonymous_hero.html` instead of the "Welcome back"
    greeting; no In progress / History sections (`_dashboard_inputs` sets `is_auth`; In progress
    is built only when `is_auth`; `_requested_section` 404s for those sections when anonymous);
    discovery sections only.
  - The panels are NOT fetched for anonymous visitors: `dashboard` builds `dashboard_panels` only
    `if inputs.is_auth`, and the template wraps the panel loop in `{% if user.is_authenticated %}`.
- Authenticated "continue your application": `ApplicationCourseAccessBackend
  .get_dashboard_contributions(user)` in `course_applications/backends.py` calls
  `queries.get_active_applications(user)`, which returns `CourseApplication.objects.filter(
  user=user).select_related("course", "form_progress")`, and returns one `DashboardContribution`
  (`template_name="course_applications/partials/dashboard_applications.html"`, `context=
  {"applications": apps}`). The view `render_to_string`s it per contribution; the template block
  is a "Your applications" section: submitted rows link to `course_applications:status` with
  "Pending review"; draft rows show a warning `c-chip` "Incomplete", "Finish your application to
  have it reviewed." and a `c-button` "Continue application" linking to `course_applications:
  status` (the status view redirects a draft to `_resume_url`, i.e. the page the applicant left).
  Placement: after the greeting, before the sections (so "at the top"). `learner_interface` never
  imports `course_applications`; this is the only coupling, and `queries.py` says
  "learner_interface must NOT import from here". `get_active_applications` and
  `get_application_for_course` return empty/None for anonymous users with no query.
  There is no context processor for it: `learner_management/context_processors.py` only exposes
  `can_access_educator_interface`.
- What it would take for an anonymous session (change B):
  - the contribution methods take only `user`; they have no request, so they cannot see the
    session. Options: widen `get_dashboard_contributions` to receive the request (or a session
    map) -- a signature change on the `CourseAccessBackend` interface in `course_access/backends.py`
    and its default/Free-only implementations; or have `learner_interface` call a new hook;
    or a context processor / template tag in `course_applications`. The dashboard `if inputs.is_auth`
    gate and the template's `user.is_authenticated` wrap must be loosened.
  - the query: `owned_applications(request)` (`anonymous_session.py`) already resolves a request's
    applications for an anonymous session; for the panel it needs `select_related("course",
    "form_progress", "anonymous_applicant")`, and should keep only drafts (and submitted unverified,
    if wanted; those are no longer reachable by form pages, only the status page).
  - links: the existing template's `course_applications:status` link already works for an
    anonymous session whose map holds the applicant: `application_status` uses
    `owned_applications(request)` and redirects a draft to `_resume_url` (form page).
    `application_form_page` / `application_check_answers` also use `owned_applications`. No
    template change needed beyond the data. The `app.is_submitted` row ("Pending review") would be
    inaccurate for an unverified application (nobody is reviewing until the claim).
  - login bounces: `_owned_application` redirects a non-owner anonymous visitor to
    `redirect_to_auth` (login with `next`) rather than 404, for `application_status`,
    `application_form_page` and `application_check_answers`. So a stale dashboard link (session map
    entry points at a claimed or erased applicant, or a session that expired) would bounce to the
    login page. `anonymous_applicant_for_course` / `owned_applications` filter out claimed and erased
    applicants, so a panel built from them will not contain stale rows; the bounce only happens
    for a link opened from another tab after a claim or in another browser. `apply` and
    `applicant_details` themselves never bounce an anonymous visitor on an application-gated
    course (a non-gated course goes to `redirect_to_acquisition_auth`).
  - Also: `course_detail` and other CTAs use `get_application_for_course(user=request.user)`, which
    returns None for anonymous users, so the course page still says "Apply now" while the dashboard
    shows an in-progress application. Not required by the idea; note for consistency. `apply` already
    resumes via the session.
  - `adapt` for `HX-Target` section swaps (`_requested_section`) is not involved: the panel is not
    a section.

## 5. Staff-facing unverified flag

- `CourseApplicationAdmin` (`course_applications/admin.py`): boolean column `is_email_verified`
  ("Email verified"), filter `email_verified`, `applicant_email`/`applicant_name` from the
  applicant when `user` is null, a leading "Unverified email" summary row. `FormProgressAdmin` and
  `QuestionAnswerFileAdmin` (`form_engine/admin.py:276-287`, `:393-395`) show "Unverified" or
  "Unverified: <email>" for user-less sittings. `AnonymousApplicantAdmin` is read-only with delete =
  erasure.
- Early sending changes nothing in the flag (it keys on `user_id is None`). But a draft is an
  `unverified` `CourseApplication` today too, since the draft is created at the details step with
  user null; so staff already see drafts flagged. The flag does not distinguish "link sent" from "not
  sent"; `claim_email_sent_at` is not displayed in admin (verify before relying on it). Whether staff
  should see drafts at all is unchanged by A.
- Claiming a draft (if allowed) would turn it from unverified to verified before it is submitted,
  so staff's "verified" would no longer imply "submitted".

## 6. Existing tests (file names under `freedom_ls/`)

- `course_applications/tests/`: `test_views.py` (apply, details step, status, claim, check-answers
  paths), `test_claims.py`, `test_emails.py`, `test_anonymous_session.py`, `test_receivers.py`
  (login adoption, erasure receivers), `test_forms.py`, `test_models.py`, `test_queries.py`,
  `test_backends.py` (dashboard contribution), `test_admin.py`, `test_erasure.py`, `helpers.py`,
  `playwright/test_application_form_flow.py`.
- `form_engine/tests/`: `test_session_access.py`, `test_views.py`, `test_uploads.py`,
  `test_models.py`.
- `learner_interface/tests/views/test_dashboard.py`, `learner_management/tests/test_context_processors.py`
  (for the educator-interface flag only), `learner_management/tests/test_queries.py`,
  `qa_helpers/tests/management/commands/test_qa_reset_course_application.py`,
  `test_qa_create_clean_applicant.py`.
- Tests that encode today's behaviour and will need rewriting: claim of a not-yet-submitted
  application renders "invalid" (`test_views.py` / `test_claims.py`); no email is sent on the
  details step; anonymous dashboard shows no panel (`test_dashboard.py`, `test_backends.py`).

## Summary of decisions the later spec must make

1. What a claim link does when the application is still a draft (reject with a clearer state, or
   claim a draft); `attach_to_user`'s tie-break and consent/`user.registered` timing depend on it.
2. Token binding when the email changes after a link was sent (token holds only the applicant pk).
3. Whether changing the email at the details step resends automatically, and how that interacts
   with `application_claim_email` (3/h per address).
4. How the session reaches the dashboard panel: `get_dashboard_contributions(user)` has no request.
5. Panel wording for an anonymous draft and for an unverified submitted application.
6. Session expiry (2 weeks, not extended on read) leaves orphaned drafts; no cleanup exists.

status: ok
