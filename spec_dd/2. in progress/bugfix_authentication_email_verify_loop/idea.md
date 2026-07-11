# Bugfix: authentication email-verification loop

## Original report

I recently tried to demo the project and email verification did not work.

Scenario:

- Visited the site as an unauthenticated user
- Navigated to a "free" course
- Chose to enrol for free
- Was asked to log in / create an account
- Tried registering with an email that was **already on the system**
- Got a password-reset email
- Followed the email link and it asked me to fill in a form to reset my password
- Filled it in
- Kept trying to verify email, but it just didn't work

## What the research found

The single reported symptom is actually a **chain of distinct defects** in the
unauthenticated → "enrol for free" → sign-up path. Full detail (with `file:line` and
allauth source citations) lives in the research files next to this idea:

- `research_auth_flow_map.md` — every sign-in/sign-up/verify/reset pathway, and where each can dead-end.
- `research_allauth_enumeration_pitfalls.md` — allauth behaviour + known upstream issues (version `65.15.1`).
- `research_suspect_specs.md` — which recent spec introduced the reachable regression, and the QA gap.

### Root cause of the "loop"

With this project's allauth config (`ACCOUNT_EMAIL_VERIFICATION="mandatory"`,
`ACCOUNT_LOGIN_ON_PASSWORD_RESET=True`, `ACCOUNT_PREVENT_ENUMERATION=True`):

1. Signing up with an email that already exists does **not** error (enumeration prevention).
   Allauth sends an "account already exists" email that points the user at the **generic
   "forgot password" page**, and shows the same "check your email" screen as a real signup.
2. Completing a password reset via the emailed link **does not mark the email address
   verified** (allauth's link-based reset only encodes the user id, not the email).
3. Because verification is mandatory, the reset-triggered auto-login
   (`ACCOUNT_LOGIN_ON_PASSWORD_RESET`) re-enters the email-verification stage, is blocked, and
   fires *yet another* verification email instead of logging the user in. Every subsequent
   login/reset attempt hits the same gate → the "loop". (A 180s resend cooldown means some of
   those attempts send no email at all, while still showing "check your email".)

This loop is an **allauth-layer gap** (settings pre-date the recent specs), but it was made
**reachable for ordinary users** by the `2026-07-01_19:44_home_page` spec, which opened public
browsing and routed the anonymous "enrol for free" CTA into sign-up. `2026-07-03_07:52_courses_coming_soon`
is **ruled out** — for a published/free course its changes are no-ops on this path.

## Scope — make auth rock solid

Auth must be reliable now and going forward, so this bugfix covers **all** the defects the
research surfaced on these pathways, not just the headline loop:

1. **The verification loop (primary).** After a password reset, the user must end up
   **logged in** rather than bounced back into mandatory verification.
   **Chosen approach:** make a completed password reset **mark the account's email verified**,
   so `ACCOUNT_LOGIN_ON_PASSWORD_RESET` logs the user straight in. This is the smallest change
   that closes the loop, keeps link-based reset, and **preserves enumeration prevention**.
   (Completing a reset proves control of the inbox, so treating it as verification is safe for
   this single-email-per-user model.)

2. **Lost enrolment intent.** On the existing-email branch, the `?next=` course-enrol target is
   silently dropped (allauth returns before `get_success_url()`). Once a user recovers their
   account they should land back on the course they were trying to enrol in, not at `/`.

3. **Misleading verification UX.** The "verification sent" screen shows identical copy whether a
   real verify link, an "account already exists" reset email, or **no** email (cooldown) was
   sent. Users need honest messaging and a clear, reachable way to **resend verification** /
   recover when stuck.

4. **Site-scoped reset dead-end (prod-only, lower confidence).** The site-scoped `UserManager`
   can make a reset-key link resolve to `DoesNotExist` in production (masked in dev by
   `FORCE_SITE_NAME`). Confirm whether this is real and, if so, ensure reset links resolve the
   correct user regardless of the current request's site.

The goal is that **every** sign-in/sign-up/verify/reset pathway — direct and via the course CTA,
new user and existing email — reliably lands the user in the right authenticated state.

## How to work (from the original report)

Fix this using **TDD**:

- Use Playwright to reproduce and find the bugs. Do a thorough review of **all** sign-in/sign-up
  pathways. Consider every situation, including:
    - accessing the sign-up page directly (not through a course CTA)
        - sign up with a new user
        - trying to sign up with an email already on the system
    - accessing the sign-up page through a course CTA (e.g. course-reg attempt while not signed in)
        - sign up with a new user
        - sign up with an email already in the system
- Write tests to expose each bug (**RED**)
- Get the tests to pass (**GREEN**)
- Don't forget to **refactor**

## SDD process retro (light-touch, part of this worktree)

The recent specs didn't cause the underlying loop, but the SDD process should have caught that
the new CTA-into-signup journey exposed it. The gap: every QA workflow in those specs used a
**fresh, never-used email** for every sign-up, so the "existing account tries to sign up again"
branch was never exercised — even though `better-registration`'s own threat model had already
flagged enumeration prevention as a known concern.

The fix is **not** "check authentication on every spec" — most changes don't touch auth. It's to
make **QA scoping more thorough and careful**: when a change touches some functionality, explicitly
reason about *what else is affected and what could reasonably break* — including unintended
side-effects — and go and check those, not just the golden path. Improve the SDD QA-planning
skill/guidance to encourage this side-effect / failure-mode thinking. Keep it proportionate —
don't be excessive.

## Note

This idea is intentionally high-level. The precise fix mechanics (which adapter/flow methods to
override, exact tests, messaging copy) belong in the spec/plan, not here.
