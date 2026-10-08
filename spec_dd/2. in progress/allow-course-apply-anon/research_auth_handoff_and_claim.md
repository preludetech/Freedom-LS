# Research: authentication handoff and claim for an anonymous application

Topic: how a visitor goes from "I have filled in the application and typed my email" to "I am logged in and the application is mine", using the auth machinery FLS already has.

Installed allauth: 65.15.1 (`.venv/lib/python3.13/site-packages/allauth/`). Allauth source paths below are relative to that directory. Earlier research on the same machinery, not repeated here: `spec_dd/3. done/2026-09-27_07:08_more-prominent-signup-button/research_allauth_capabilities.md`.

Web sources:
- Settings reference: https://docs.allauth.org/en/latest/account/configuration.html
- Adapter reference: https://docs.allauth.org/en/latest/account/adapter.html
- Signals reference: https://docs.allauth.org/en/latest/account/signals.html
- Release notes (65.x): https://docs.allauth.org/en/dev/release-notes/recent.html and https://docs.allauth.org/en/dev/release-notes/2025.html

Decisions already taken and not re-opened: `next` is carried by stock allauth/Django behaviour, with no custom `next`-threading (bugfix-shitty-allauth-decisions spec); email verification catches typos, so there is no second email field (better-registration spec); `ACCOUNT_PREVENT_ENUMERATION` stays on.

## 1. How intent survives today (answer to question 2)

The chain, confirmed from code:

1. An anonymous request to `apply` hits `acquisition_login_required` (`accounts/decorators.py`). It calls `redirect_to_auth(next_url=request.get_full_path(), auth_url=acquisition_auth_url(request))`. That is `/accounts/signup/?next=/.../apply/<slug>/` when `is_open_for_signup`, and the login page otherwise. For htmx it returns 204 with `HX-Redirect`.
2. The signup and login pages keep `next` in a hidden `redirect_field` (`base/templates/account/signup.html` line 70, `login.html` line 42). The signup/login switch buttons use allauth's `passthrough_next_redirect_url`, so `next` survives switching pages. The failed-login callout uses `url_with_next ... email=form.data.login`, so the typed email is prefilled into signup via allauth's `SignupView.get_initial` (`account/views.py` ~line 171, reads `?email=`). Login has no equivalent prefill: `LoginView` has no `?email=` initial.
3. `SignupView.form_valid` calls `complete_signup(redirect_url=self.get_success_url())` (`account/internal/flows/signup.py`). `user_signed_up` is sent (this is where `referral_tracking` writes `SignupAttribution`). Then `perform_login` builds a `Login(redirect_url=next, signup=True)`.
4. With `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` and an unverified address, `EmailVerificationStage.handle` (`account/stages.py:145`) sends the confirmation mail and returns the "verification sent" response. Because the stage returned a response, `LoginStageController.handle` calls `stash_login`, which serialises the whole `Login`, **including `redirect_url`**, into `request.session["account_login"]`.
5. The emailed confirmation link carries no `next`. When the link is opened, `ConfirmEmailView` -> `verify_email_and_resume` -> `login_on_verification` (`account/internal/flows/email_verification.py:106`). With `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` it calls `stage.exit()` and resumes the stashed `Login`, but only if the stashed login's user is the user being verified. `adapter.login` and `post_login` then run, and `get_login_redirect_url(request, redirect_url)` uses the stashed `redirect_url` first. `user_logged_in` is sent from `post_login`.
6. The browser lands on `next`. If the middleware finds incomplete additional registration forms (`RegistrationCompletionMiddleware`), a GET to `next` is redirected to `accounts:complete_registration?next=<path>`. The completion view re-emits `next` as a hidden field and, after a valid submit, redirects through `_safe_post_completion_redirect` (`url_has_allowed_host_and_scheme`).

Tests that guarantee this today (`accounts/tests/test_deferred_login.py`): `test_signup_arm_express_interest_round_trip` and `test_signup_arm_records_interest_only_for_the_stashed_course` pin signup -> verification -> landing with a session-stashed intent. The completion-view tests pin the open-redirect fallback and the hidden `next` field. The header-link and login/signup page tests pin `next` carry-over.

A `next` pointing at a claim URL survives exactly like the existing express-interest `next` (`course_interest.deferred_express_interest`). That view is already the project's pattern for a GET-safe deferred action: session stash set on the way out, a `@login_required` GET view that acts only if the stash matches, then redirects.

Limitations of the chain:

- **Same browser only.** The `redirect_url` lives in the session-held stash. If the verification link is opened in another browser or device, `login_on_verification` finds no stash, nothing logs in, `next` is lost, and the visitor lands on `LOGIN_URL` (`EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL` defaults to it).
- **15-minute window.** `unstash_login` discards a stashed `Login` older than `ACCOUNT_LOGIN_TIMEOUT` (default 15 minutes, `account/app_settings.py:573`, not overridden in `config/`). Opening the link later than that, even in the same browser, still verifies the address but does not log in, and `next` is lost.
- **Confirmation click.** `ACCOUNT_CONFIRM_EMAIL_ON_GET` is False, so opening the link shows a page with a confirm button (POST). That is one more screen than "click the link".
- Our own session stash (the pattern in `course_interest/views.py`) has neither the 15-minute nor the stash-loss limit. It lives for the session (`SESSION_COOKIE_AGE`, 2 weeks in production), so it outlives allauth's login stash. Only the `next` redirect depends on allauth's stash.
- Email-already-registered via the signup page: with `ACCOUNT_PREVENT_ENUMERATION` allauth treats the submit as a fake login (`flows.signup.prevent_enumeration`). No account is created, the visitor sees the same "verification sent" page, and the address receives an "account already exists" mail whose only link is password reset (no `next`). So a returning user who is sent to signup never gets `next` honoured. They must go back and use Log in. This matters for the recommendation below.

## 2. Handoff options compared (answer to question 1)

| | (a) signup page, email prefilled, `next` = claim URL | (b) account lookup, then login or signup | (c) allauth login by code | (d) emailed claim link |
|---|---|---|---|---|
| Works with mandatory verification | Yes, it is the existing path | Yes | Yes. A code is an email proof: `LoginCodeVerificationProcess.finish` calls `verify_email_indirectly` and logs in | Yes, and the link itself proves ownership |
| Works with login on email confirmation | Yes (same browser, within 15 min) | Same as (a) for the signup arm | Not relevant; the code logs in | Not relevant, but it bypasses allauth's login unless built to |
| Survives `complete_registration` forms | Yes (tested pattern) | Yes | Yes. A code login is a normal `perform_login`, so the middleware applies | Only if the link logs in through allauth, which is custom code |
| Screens for a new applicant | Signup form (email prefilled; name, password x2, optional terms) -> verification-sent -> email -> confirm button -> (completion forms) -> landing: 4 to 6 | Same as (a) after one extra decision | Not available to new applicants | 2 to 3 (check email, click) |
| Screens for a returning applicant | Signup page first, then Log in button, then login form: 3+ and `next` survives the switch | Login form, 1 | Request code -> code entry -> landing | n/a |
| Enumeration | Safe | Violates the stance (below) | Safe: unknown email gets an "unknown account" mail with the same visible response | Safe only if sent identically for known and unknown |
| New code to write | Small | Small, but wrong | Setting + templates; no applicant path | Largest: security-sensitive custom flow |

**(a) Redirect to signup with email prefilled and `next` -> claim URL.** This is the minimum that reuses everything: it is what `acquisition_auth_url` already does for an applicant who clicks Apply while anonymous, plus `?email=` which allauth already reads and `url_with_next` already builds for the failed-login callout. The prefilled email is editable. Its weakness is the returning-user case above (signup page, then Log in). The signup page's prominent "Log in" button (`signup.html`) already carries `next`, but not the email, since `LoginView` has no email initial.

**(b) Look up whether the typed email has an account and route to login vs signup.** Recommend against. Per `docs/product/authentication.md`, "responses do not distinguish 'email not registered' from 'password incorrect'", and even the failed-login prompt to create an account is "the same whatever email was typed, so it gives nothing away". An anonymous form that answers "this email has an account" or "this email is new" with a different next screen is an account-existence oracle for any address, and it is not covered by `ACCOUNT_RATE_LIMITS` (those key on signup and login failure, not on a new apply endpoint). Allauth itself goes to length to avoid this (`prevent_enumeration`, identical "code sent" message for unknown accounts). The only enumeration-safe version is to send everyone to the same page (a) and let them choose using the existing switch buttons. That is (a).

**(c) Login by code.** `ACCOUNT_LOGIN_BY_CODE_ENABLED` defaults False and is not set in `config/settings_base.py`. `freedom_ls/base/templates/account/login.html` already carries the "Send me a sign-in code" block, gated on `LOGIN_BY_CODE_ENABLED`, and `account/email/login_code_*` email templates exist in `freedom_ls/accounts/templates/`. Allauth 65.15 has **no signup-by-code**. Release notes: 65.13.0 added `ACCOUNT_LOGIN_BY_CODE_TRUST_ENABLED`; 65.15.0 added `ACCOUNT_LOGIN_BY_CODE_SUPPORTS_RESEND` and dashed code formats; 65.1.0 added signup by passkey, which is passwordless but not a code. In `flows/login_by_code.py`, `send_by_email` only generates a code when a user exists. For an unknown email it sends `send_unknown_account_mail` (a signup link, with no `next`) and shows the same "code sent" message. So (c) is not a path for a new applicant, who is the person this feature exists for. For a returning user it is a good path (no password; one code gives verification and login; `finish(redirect_url)` honours `next`) but it is a site-wide change to the login screen that this feature should not be the vehicle for. Revisit separately. Enabling `LOGIN_BY_CODE_REQUIRED` or the trust option are further, unrelated policy changes.

**(d) Emailed magic claim link.** This duplicates what allauth's confirmation mail and `LOGIN_ON_EMAIL_CONFIRMATION` already provide, and a bearer link that both proves email ownership and logs in is exactly the risk allauth's own comment in `login_on_verification` explains (replayable login links, links leaking into logs and analytics). It would also create accounts outside the signup form, so the signup policy, consent and `SignupAttribution` rules would be bypassed or re-implemented. Not recommended.

### Recommendation for question 1

Use (a), with the applicant's typed email prefilled, and make the claim independent of `next` so the weak points of the chain do not lose the application:

- Keep the draft application (and a draft-held capability, such as an id in the session, using the same session-stash pattern as `course_interest`) separate from the `next` redirect. `next` only chooses where the browser lands; it points to a GET-safe deferred view (like `deferred_express_interest`).
- Run the claim from an idempotent function triggered by the `user_logged_in` signal as well as from that landing view (see section 5). Then a verification link opened late, or a returning user who logs in through the switch button, still claims on the first successful login in the browser holding the session.
- Add the typed email to the Login link on the signup page for this flow, so a returning applicant does not retype it (optional; login has no `?email=` initial today, so this needs a small view or template change and is only a convenience).
- Do not branch on whether the email has an account.

## 3. The claim rule (answer to question 3)

Rule: a draft application is bound to a user only when all of these hold:

1. **The claimant holds the draft.** The draft's id/token is in the claimant's own session (or signed cookie). Possession is required, because the draft's email is attacker-controlled text: anyone can type anyone's address. Matching on email alone, for example from the `email_confirmed` signal over all unclaimed drafts, would let a stranger attach an application to a victim's account the moment the victim signs up or confirms. Do not claim by email match alone.
2. **The user has a verified `EmailAddress` equal to the draft's email**, compared on the normalised address, on the current site. A `User` is site-scoped, so claim only drafts for the request's site. "Verified" means `EmailAddress.verified=True` for that user and address. Under `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` an authenticated user's login address is verified; a secondary address added later counts only if verified.
3. **The claim is an atomic, single-use transition**: lock the draft, check it is unclaimed, set the owner, and drop the session capability in the same transaction.

Failure cases:

| Case | Outcome |
|---|---|
| Logs in with a different email than typed | No claim. The draft stays unclaimed and held in the session. Tell the applicant plainly that this account's email differs from the one on the application. This reveals nothing about anyone else, since it compares the signed-in user's own addresses with their own draft. Offer to continue as this account only if the product wants a "re-start under this account" path. |
| Signs up with a different email (edits the prefilled field) | Same: no claim. Verification of the new address does not rebind the draft. Alternative to decide: since the claimant holds the draft and has verified an address, rebinding to the verified email would be safe from a security standpoint, but it undermines the point of capturing the typed email (follow-up on abandoned applications) and makes "who is this" ambiguous. Recommend strict match. |
| Verification never completes | The account exists but cannot log in, so no claim. The draft stays unclaimed with a typed, unverified email. That is a retention and privacy question for the spec (an unclaimed draft holds personal data from a person who never proved the address), so it needs an expiry and a purge rule, and the unverified email must not be treated as trusted contact data. |
| Verification link opened in another browser, or after 15 minutes | Verification succeeds; allauth does not log in; `next` is lost. The draft is still in the original browser's session. The next login there claims it via the `user_logged_in` trigger. In the other browser there is nothing to claim. Say so on the "verification sent" side as far as practical. |
| Same draft claimed twice | Same user: idempotent, redirect to the application. Different user: the second fails because the draft is already claimed and the session capability is gone. |
| User already has an application for that course | `CourseApplication` has a unique constraint on site, user and course (`unique_application_per_site_user_course`), and `apply` already short-circuits to the existing application. The claim must not overwrite or duplicate it: keep the existing application, and tell the applicant. |
| Claim triggered by someone else on a shared browser | Session capability belongs to the browser. A different account logging in afterwards fails rule 2 unless it genuinely has the typed address verified. |

## 4. Prefill when signed in (answer to question 4)

Today, for a signed-in user, `apply` creates (or reuses) the `CourseApplication` immediately and, for a course with a form, redirects to the first form page; there is no email field anywhere in the flow. For a signed-in user the account's email is already known, unique per site, and verified.

Recommendation: for a signed-in user the email is shown **read-only** ("Applying as name@example.com") and the end handoff is skipped: no authentication step and no claim, because the application is created under their account from the start as today. Do not make the email editable for a signed-in user: an editable field would reintroduce the mismatch case in section 3 for no benefit. If the product wants an "apply with a different email" path, that is a separate decision and would still need the verified-ownership rule. This also keeps the signed-in path identical to the current tested behaviour.

## 5. Allauth hooks in 65.15 (answer to question 5)

Allauth reference: adapter https://docs.allauth.org/en/latest/account/adapter.html, signals https://docs.allauth.org/en/latest/account/signals.html. Behaviour below was checked against the installed source.

- `DefaultAccountAdapter.get_login_redirect_url(request)` (`account/adapter.py:228`): only the fallback; an explicit `next` or `Login.redirect_url` wins (`account/utils.py:47`). `get_signup_redirect_url` (line 222) is the same for the signup fallback. Neither is the right place for claim logic.
- `get_email_verification_redirect_url(email_address)` (line 255): the post-confirm redirect when `next` is absent. The old name `get_email_confirmation_redirect_url` is deprecated; the adapter still calls it if defined. Not useful for claim, since it runs only on the confirm-view path.
- `pre_login` (line 490): runs before stages and verification, with `user` possibly unverified. Wrong for claim (ownership is unproven). Currently only checks `is_active`.
- `post_login` (line 504): runs after `adapter.login`, and itself sends `user_logged_in`. Returns the redirect response; overriding it is possible, but a receiver is simpler.
- `save_user` (line 320, already overridden in `allauth_account_adapter.py`): fires `user.registered` and `record_sign_up`. Runs at signup, before verification. Wrong for claim.
- Signals (`account/signals.py`): `user_signed_up` fires before verification and login (the `referral_tracking` receiver uses it); wrong for claim. `email_confirmed` fires inside `verify_email` with a `request` and the `EmailAddress`, usable but it also fires when the session lacks the draft and while `request.user` may be anonymous. `user_logged_in` fires from `post_login` with an authenticated `request.user`, with the session intact, for password login, login by code and login-on-confirmation alike.
- The stash (`allauth.account.internal.stagekit.stash_login` / `unstash_login`, session key `account_login`): internal API, not documented as public, holds only the allauth `Login` and expires in 15 minutes. Do not put the application in it or rely on it for claim; use the project's own session stash as `course_interest` does.

Cleanest place to run "claim pending application" once the account is verified: a single idempotent function that checks the section 3 rule, called from a `user_logged_in` receiver and from the deferred landing view that `next` points at (the landing view only reports the result and redirects). The receiver covers new signups, returning users, a late verification link, and login by code if it is ever enabled. The landing view covers the redirect and the `complete_registration` hand-through. The function must not run from `user_signed_up`, `pre_login` or `save_user`, because ownership of the typed email is not yet proved there.

Interaction points to keep in mind:
- `RegistrationCompletionMiddleware` exempts `account_*` URL names and `accounts:complete_registration`; a claim landing view is not exempt, so for users with incomplete forms the landing GET is redirected to completion with `next=` set, then returns (tested pattern). A claim run from `user_logged_in` happens before that redirect, so the order does not matter.
- `application_status` and the form pages are `@login_required`, so the claimed application's pages work after claim with no changes.
- htmx: `redirect_to_auth` already turns the handoff into a 204 with `HX-Redirect`, so an htmx submit of the final step works.

## 6. Referral tracking (from the files list)

`referral_tracking` writes a `SignupAttribution` in a `user_signed_up` receiver from a signed first-touch cookie minted on landing (`capture.py`, `signals.py`). An anonymous draft creates no `User`, so it writes nothing. A visitor who lands via an ad, fills in the application anonymously, and signs up in the same browser keeps their first-touch attribution for as long as the cookie lives. A returning user who claims gets no new `SignupAttribution` (none is written for an existing account). A new account verified in another browser is recorded as direct traffic at signup, because the cookie is per browser. No change to referral tracking is needed. Analytics (`record_application_submitted`) should fire when the application is actually claimed or submitted by a user, not when the anonymous draft is saved.

## 7. Closed-signup sites (answer to question 6)

`acquisition_auth_url` returns `account_signup` only when `get_adapter(request).is_open_for_signup(request)` is true, and `SignupView` itself renders `signup_closed` otherwise (`CloseableSignupMixin`). Anonymous application depends on a new visitor being able to create an account to claim into, so on a closed-signup site it must not be offered: an anonymous applicant would fill in the whole form only to dead-end at the end. Recommend that on a site where signups are closed the apply entry behaves exactly as today: the anonymous visitor is sent to the login page with `next` set. Decide the check at the start of the flow, not at the end. A site that closes signups with an anonymous draft already in progress (rare) falls back to login, and the claim works only if the typed email already has an account; that outcome is acceptable and needs no extra code.

## Summary of recommendations

1. Handoff: (a), the signup page with the typed email prefilled, `next` pointing at a GET-safe deferred claim view, and no account-existence lookup (b would break the enumeration stance). Login by code (c) has no new-applicant path and is a separate, site-wide decision; a magic claim link (d) re-implements allauth.
2. Intent: use the existing session-stash plus deferred-view pattern; treat `next` as landing only. Know the 15-minute and same-browser limits of allauth's own stash.
3. Claim rule: draft held in the claimant's session AND the user has a verified `EmailAddress` equal to the draft's typed email on this site; single-use, atomic, idempotent; never claim on email match alone.
4. Signed in: show the email read-only and skip the handoff.
5. Claim trigger: a `user_logged_in` receiver plus the deferred landing view, both calling one function.
6. Closed signups: do not offer anonymous application; keep today's login redirect.

Open points for the spec: whether a signup with a different email should rebind the draft (recommended: no); expiry and purge of unclaimed drafts that hold an unverified email; whether to add the typed email to the signup page's Log in link.

status: ok
