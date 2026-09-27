A would-be learner clicked "Apply now" on a course, landed on the login page, had no account, submitted the login form several times and gave up without signing up or applying. We need to stop that from happening.

## Why it happens

"Apply now" (`course_applications:apply`) and "Enrol for free" (`learner_interface:initiate_course_access`) are plain `@login_required` views, and express interest sends anonymous visitors through `redirect_to_auth`. All three send them to `account_login`, never to `account_signup`. The login page is allauth's stock `account/login.html`, which FLS does not override. The only route to signup is one sentence of body text above the form, plus the header's Sign up button, which looks exactly like the Login button beside it.

`ACCOUNT_PREVENT_ENUMERATION` means a failed login for an unknown email shows the same "email or password incorrect" message as a wrong password. So the visitor never learns they need an account, and nothing on the page points them to signup.

`next` already survives every switch between login and signup (`url_with_next`, covered by `test_header_auth_links_carry_next.py`), so a visitor who finds the signup link does end up back on the apply page. The problem is that they don't find it.

## What we will do

1. **Send acquisition calls to action to signup.** When an anonymous visitor clicks "Apply now", "Enrol for free" or express interest, they land on the signup page with `next` set, not on the login page. Coursera, edX and Khan Academy do the same for enrol and join buttons (`research_login_signup_ux_patterns.md`). Every other `@login_required` redirect still goes to login, because those visitors are most likely returning users. When signups are closed for the site (`SiteSignupPolicy.allow_signups`, via `AccountAdapter.is_open_for_signup`), these calls to action go to login as they do today.
2. **Make the switch between login and signup impossible to miss.** Override `account/login.html` so that "New here? Create an account" is a visible button-weight call to action, not a sentence of body text. The signup page gets the same treatment for "Already have an account? Log in". Each page's heading makes clear which one the visitor is on.
3. **Nudge after a failed login without revealing whether the account exists.** Keep the generic error, and show a prominent "New here? Create an account" callout beside it on every failed attempt, whatever the email. The signup link carries the email the visitor typed, so they don't retype it. Allauth's `SignupView` already prefills from `?email=` (`research_allauth_capabilities.md`).

All of this has to be accessible: the error and the callout are announced to screen readers, and the calls to action are real links with clear labels.

## Names

- `acquisition_auth_url(request)`: the auth page an acquisition call to action sends an anonymous visitor to. Signup while the site is open for signups, otherwise `None`, which `redirect_to_auth` resolves to login.
- `acquisition_login_required`: the `@login_required` counterpart for acquisition calls to action. Same contract, except that the anonymous redirect goes to `acquisition_auth_url` instead of `LOGIN_URL`.
- `url_with_next` (existing tag) also takes extra query parameters, so the failed-login callout can build the signup link with both `next` and `email`.

## Constraints

- Keep `ACCOUNT_PREVENT_ENUMERATION = True`. Nothing the visitor sees may depend on whether the email has an account.
- Don't add custom `next`-threading. Vanilla `@login_required` plus allauth's passthrough already carry `next`, and an earlier custom version was reverted (`spec_dd/3. done/2026-07-17_09:12_bugfix-shitty-allauth-decisions/`).

## Out of scope

- **Recording people who still get stuck** so staff can follow up. That has its own idea, `failed-login-follow-up`, because the privacy trade-offs need settling first.
- **Identifier-first or login-by-code flows**, which would remove the login/signup split altogether. They are a bigger change to authentication. `research_allauth_capabilities.md` covers what allauth offers here (`ACCOUNT_LOGIN_BY_CODE_ENABLED` and its enumeration-safe unknown-account email).

## Research

- `research_codebase_auth_entry_points.md`: every path that sends an anonymous visitor to login or signup, what the pages render today, and signup gating.
- `research_login_signup_ux_patterns.md`: evidence and reference products on login/signup confusion, enumeration-safe error messages, and accessibility.
- `research_allauth_capabilities.md`: allauth 65.15.1 templates, `next` propagation, email prefill, and hook points for failed logins.
