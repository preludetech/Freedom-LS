# Idea: most account pages are allauth's stock templates and wording, which confuse learners at the points they are most likely to give up

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (ACCT-3, ACCT-4, ACCT-6, ACCT-7,
ACCT-8, ACCT-9, APP-3, APP-8, DISC-14). allauth 65.18.0.

FLS overrides only `account/login.html` and `account/signup.html`
(`freedom_ls/base/templates/account/`) plus the email templates
(`freedom_ls/accounts/templates/account/email/`). Every other account page is allauth's own
template from `allauth/templates/account/`. Each section below is one problem. Most share a
single fix: override the remaining templates in FLS and write the copy in FLS's voice.

### Signup form accessibility (ACCT-3)

On `/accounts/signup/`:

- Non-field errors (e.g. after a honeypot trip) are a plain `<p class="text-error">` with no
  `role="alert"` (`base/templates/account/signup.html:16-18`). The login page wraps its errors in
  `role="alert"` (`login.html:12`), so screen readers hear why login failed but not why signup did.
- Field errors are a `<p>` placed before the field's own `<p>` (`signup.html:21-24`), so "This
  field is required." for First name sits under the Email input.
- First and last name have no `autocomplete="given-name"` / `"family-name"`
  (`accounts/forms.py:199-200`).
- Nothing gets focus after a failed submit.

### Logout and account management pages (ACCT-4)

`/accounts/logout/`, `/accounts/email/`, `/accounts/password/change/` use allauth's manage
layout. The logout page shows two "Sign Out" buttons (the form's and the manage nav's) plus
"Change Email" / "Change Password". `/accounts/email/` offers "Re-send Verification" and "Remove"
on the single verified primary address, and styles every button as primary. Wording mixes "Log
in" / "Login" with "Sign Out" (`base/templates/partials/logout_button.html:12,14`) and uses Title
Case headings ("Verify Your Email Address", "Confirm Email Address", "Password Reset") against
sentence case elsewhere. Page titles carry no site name.

### Verifying on another device loses `next` (ACCT-6)

Sign up from "Enrol for free" in browser A, so `next` is the course access URL. Open the confirm
link in browser B and confirm. B lands on the login page, then on `/` after login. allauth keeps
`next` in the signup session only; the confirmation key doesn't carry it. Worth deciding whether
FLS stores the pending `next` server side against the address, or at least tells the learner where
to go.

### Stock confirmation and reset copy (ACCT-7, DISC-14)

- Confirm page: "Please confirm that qa-acct-1@email.com is an email address for user
  qa-acct-1@email.com." (`allauth/templates/account/email_confirm.html:16`). The address appears
  twice because the user display is the email.
- Verify page: "Follow the link provided to finalize the signup process ... Please contact us if
  you do not receive..." (`verification_sent.html:12`). US spelling, and "contact us" isn't a link.
- Bad reset token page heading: "Bad Token" (`password_reset_from_key.html:10`).
- Reset and setup page heading "Change Password", with a primary-styled "Cancel". For a
  staff-created learner who has never had a password, "Set your password" fits.
- The account setup email says to use the "Forgot password" page
  (`accounts/templates/account/email/account_setup_message.txt:10`); the login page link says
  "Forgot your password?".
- After "I'm interested" on a coming-soon course, an anonymous visitor lands on a bare "Create an
  account" page with nothing saying why an account is needed for that course.

### Re-clicking a used confirmation link (ACCT-8)

Confirm an address, then open the same link again (people click emails twice). A logged-in,
verified learner sees "This email confirmation link expired or is invalid. Please issue a new
email confirmation request." With HMAC keys, allauth looks the address up with `verified=False`
(`allauth/account/models.py:215`, `EmailConfirmationHMAC.from_key`), so a verified address reads as
invalid. FLS could check for an already-verified address in an overridden `email_confirm.html`
(or view) and say "This address is already confirmed" with a link on. The "Verify Your Email
Address" page also has no resend action; the only way to get a fresh link is to try logging in.

### Adding someone else's address sends them a plain confirm email (ACCT-9)

As learner 5, add learner 1's verified address at `/accounts/email/`. It is accepted as
unverified. FLS's own `config/settings_base.py:438` sets `ACCOUNT_PREVENT_ENUMERATION = True`, and
this project does the same.
Learner 1 receives "[First Class] Confirm your email address" with "Please confirm your email
address" (`accounts/templates/account/email/email_confirmation_message.txt`) and nothing saying
another account added it. Clicking is refused, so there's no takeover, but the email reads as
genuine and learner 5 can resend it at will. The template should say the address was added to an
account and to ignore the email if that wasn't them.

### Claim page says "new account" to an existing account holder (APP-3)

Sign up with an address and don't verify. Apply anonymously with the same address and open the
claim link. The page says "You'll then choose a password for your new account"
(`course_applications/templates/course_applications/claim.html:16-17`). `claim_sets_a_password`
(`course_applications/claims.py:51-59`) is also true for an existing unverified account and for one
with no usable password, and the claim revokes the old password. The copy should tell those
people they are setting a new password for their existing account.

### Set-password page after a claim has no context (APP-8)

After confirming a claim for a new address the learner lands on
`/accounts/password/set/?next=/applications/status/<pk>/`. It is allauth's stock
`password_set.html` in `base_manage_password.html`: a "Set Password" form, then "Change Email",
"Change Password" (meaningless with no password) and a primary-styled "Sign Out". Pressing Sign
Out or leaving leaves an account with no usable password, and the next claim email for that
address says "new account" (above). The page needs a line saying the email is confirmed and a
password finishes the account, with nothing else competing.

## Suggested fix

Override in FLS: `account/logout.html`, `email.html`, `email_confirm.html`,
`verification_sent.html`, `password_set.html`, `password_change.html`,
`password_reset_from_key.html` and the manage layout. Fix the signup error markup and name
autocomplete. Pick "Log in" / "Log out" and sentence case and use them everywhere. Revise the
`email_confirmation_message` and `claim.html` copy as above.

## Downstream workaround

None. The project has no `templates/account/` overrides.
