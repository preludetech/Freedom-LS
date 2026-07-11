# allauth enumeration & verification pitfalls

**Installed version (ground truth for this research):** `django-allauth[headless]==65.15.1`, pinned via `pyproject.toml` (`django-allauth[headless]>=65.14.0`) and locked in `uv.lock`. All code-level claims below were verified by reading the actual installed source at
`.venv/lib/python3.13/site-packages/allauth/account/` in this worktree, not just the docs, because the official docs for `ACCOUNT_PREVENT_ENUMERATION` are explicitly flagged by allauth's own maintainers as unclear (see Q1/Q5).

Project's exact config under test (`config/settings_base.py`):
```python
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*", "first_name*", "last_name"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_ADAPTER = "freedom_ls.accounts.allauth_account_adapter.AccountAdapter"
ACCOUNT_PREVENT_ENUMERATION = True
```

---

## 1. What does allauth actually do on signup with an existing email when `ACCOUNT_PREVENT_ENUMERATION=True`?

Traced through `allauth/account/forms.py::BaseSignupForm` and `allauth/account/internal/flows/signup.py` (v65.15.1):

- `clean_email()` → `validate_unique_email()` → `flows.manage_email.email_already_exists(value)` sets `self.account_already_exists = True` if the email is already taken by any account (does **not** raise a validation error to the user — this is the enumeration-safe part).
- `BaseSignupForm.try_save()`:
  ```python
  if self.account_already_exists:
      # Don't create a new account, only send an email informing the user
      # that (s)he already has one...
      resp = flows.signup.prevent_enumeration(request, email=email, phone=phone)
      user = None
  ```
  **No new `User` row and no new `EmailAddress` row are created.** The submitted password is silently discarded — it is never applied to the existing account. This is exactly the ambiguity flagged as confusing in [allauth issue #3657](https://github.com/pennersr/django-allauth/issues/3657): the docs don't make clear that the password the "attacker" (or confused returning user) typed is simply thrown away.
- `flows.signup.prevent_enumeration()` builds a fake `Login(user=None, email=email, signup=True)` and runs it through the normal login-stage machinery (`perform_login` → `EmailVerificationStage`), so the response the browser gets (redirect to "check your email", a 302 to `account_email_verification_sent`) is **indistinguishable** from a real "please verify your new signup" response — that's the actual anti-enumeration mechanism.
- Inside `EmailVerificationStage`, `send_verification_email_at_fake_login()` builds a throwaway `EmailAddress(user=None, email=login.email)` and calls `send_verification_email_to_address(..., signup=True)`. Because `address.user_id` is `None`:
  ```python
  if not address.user_id:
      if skip_enumeration_mails:
          pass
      elif signup:
          get_adapter().send_account_already_exists_mail(address.email)
      else:
          send_unknown_account_mail(request, address.email)
  ```
  → **`AccountAdapter.send_account_already_exists_mail()` is called** (`allauth/account/adapter.py`), which renders the `account/email/account_already_exists` template and sends it. This is **not** the normal email-confirmation email, and **not literally a password-reset email with a working token** — it is a distinct, generic notice.

The actual stock template (`allauth/templates/account/email/account_already_exists_message.txt`) reads:
```
You are receiving this email because you or someone else tried to signup for an
account using email address:
{{ email }}
However, an account using that email address already exists. In case you have
forgotten about this, please use the password forgotten procedure to recover
your account:
{{ password_reset_url }}
```
`password_reset_url` here is the **generic** "request a password reset" page (`account_reset_password`), not a pre-signed reset link — the user still has to submit the "forgot password" form to get an actual working reset-key email. Confirmed in `AccountAdapter.send_account_already_exists_mail()`:
```python
def send_account_already_exists_mail(self, email: str) -> None:
    signup_url = flows.signup.get_signup_url(context.request)
    password_reset_url = flows.password_reset.get_reset_password_url(context.request)
    ...
    self.send_mail("account/email/account_already_exists", email, ctx)
```

**Intended UX** (per docs and code): the person is nudged toward "forgot password" rather than being told outright "this email is taken" (which would leak account existence). This is the documented, intentional trade-off — see [Configuration docs](https://docs.allauth.org/en/dev/account/configuration.html) and the design discussion in [Issue #1307 – "Users' email addresses can be leaked"](https://github.com/pennersr/django-allauth/issues/1307).

---

## 2. Interaction between `ACCOUNT_PREVENT_ENUMERATION` and `ACCOUNT_EMAIL_VERIFICATION="mandatory"`: edge cases that strand users

The docs claim (per [Configuration](https://docs.allauth.org/en/dev/account/configuration.html)):

> "In case of mandatory verification, enumeration can be properly prevented because the case where an email address is already taken is indistinguishable from the case where it is not."

This is true for the *response the browser sees*, but it hides an important asymmetry that only bites when **the pre-existing account's email was never verified** (e.g. an abandoned/incomplete prior signup, or a signup made before this bugfix was in place):

- If the existing account's `EmailAddress.verified` is already `True`: the "account already exists" email → "forgot password" → reset → (with `LOGIN_ON_PASSWORD_RESET=True`) the user is logged straight in. No problem.
- If the existing account's `EmailAddress.verified` is `False` (the account was created but never confirmed): the "account already exists" mail is sent **instead of** a fresh verification email, even though what the account actually needs is *verification*, not *password recovery*. The user is pointed at "forgot password" by the email copy, which does not fix the underlying unverified state (see Q3). This mismatch — telling an unverified user to reset their password rather than re-verify — is exactly the scenario this project's bug report describes.
- The docs' own maintainers acknowledge the wording here is confusing enough that a GitHub issue was opened purely about clarity: [Issue #3657 – "ACCOUNT_PREVENT_ENUMERATION docs are unclear / confusing"](https://github.com/pennersr/django-allauth/issues/3657), which specifically raises the "what happens to the password entered on the second signup attempt" question (answer, per source above: it's discarded) and points out the doc phrasing "email address uniqueness takes precedence over enumeration prevention" is logically backwards as written.
- Additionally, per the docs, if verification is **optional or disabled** (not this project's config, but worth noting for contrast), enumeration can only be prevented by *letting the signup go through*, resulting in **multiple `EmailAddress` rows for the same email across different `User` accounts** (only one of which can ever hold the `verified=True` row, enforced by a DB constraint — see Q4). That is a different, non-applicable failure mode for this project since verification is mandatory here, but it's a documented alternate pitfall of the same setting.

---

## 3. Does resetting a password verify the email address? Does `ACCOUNT_LOGIN_ON_PASSWORD_RESET` bypass mandatory verification?

**No — not with this project's current configuration.** Traced through `allauth/account/internal/flows/password_reset.py` (v65.15.1):

```python
def finalize_password_reset(request, user, email=None):
    ...
    adapter.send_notification_mail("account/email/password_reset", user)
    if app_settings.LOGIN_ON_PASSWORD_RESET:
        return perform_password_reset_login(request, user, email=email)
    return None

def perform_password_reset_login(request, user, phone=None, email=None):
    ...
    login = Login(user=user, email=email)
    return perform_login(request, login)
```

- `finalize_password_reset()` only calls `adapter.set_password(user, password)`. **It never touches `EmailAddress.verified`.**
- `allauth/account/views.py::PasswordResetFromKeyView.form_valid()` calls `finalize_password_reset(self.request, self.reset_user)` **without an `email` argument**, so `email=None` is passed all the way through.
- `perform_password_reset_login()` builds `Login(user=user, email=None)`. Per `allauth/account/models.py::Login.__init__`, when `email_verification` isn't explicitly passed it defaults to `app_settings.EMAIL_VERIFICATION` — i.e. **`"mandatory"`** in this project.
- `perform_login()` → `resume_login()` runs the full `LoginStageController` stage list, which includes `EmailVerificationStage` (`allauth/account/stages.py`):
  ```python
  elif email_verification == EmailVerificationMethod.MANDATORY:
      if not has_verified_email(login.user, login.email):
          send_verification_email_at_login(self.request, login)
          response = get_adapter().respond_email_verification_sent(self.request, login.user)
  ```
  Because the account's email is still `verified=False` (password reset never set it), `has_verified_email()` returns `False`, so **mandatory verification wins over `LOGIN_ON_PASSWORD_RESET`**: instead of being logged in, the user is redirected to `account_email_verification_sent` and a **new, real** confirmation email (tied to the actual user, not a fake login this time) is sent.
- This exact conflict is documented as a known, currently-accepted limitation:
  - [Codeberg Issue #1267 – "Verify email during password reset"](https://codeberg.org/allauth/django-allauth/issues/1267): a user reports precisely this — reset password after an unverified signup, expects to be logged in, instead gets bounced to "resend activation". Maintainer (`pennersr`) response, paraphrased: allauth encodes only the user ID in the reset token, not which email was being reset (a user can have multiple email addresses), so it cannot safely infer "the reset link proves this specific email is owned" without more machinery. The issue was closed as resolved specifically by a **different, opt-in mechanism**: **`ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED`** (see below).
  - [Issue #2084 – "Unable to treat password resets as email verification confirmations"](https://github.com/pennersr/django-allauth/issues/2084) and [Issue #2360 – "Send password reset to verified emails"](https://github.com/pennersr/django-allauth/issues/2360) cover related angles of the same gap.

**The one built-in exception (confirmed in source, already present at v65.15.1):** if `ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True` (default `False`; **currently unset/`False` in this project**), the reset flow goes through `allauth/account/internal/flows/password_reset_by_code.py::PasswordResetVerificationProcess.confirm_code()`:
```python
def confirm_code(self):
    ...
    verify_email_indirectly(self.request, self.user, self.state["email"])
```
`verify_email_indirectly()` (`allauth/account/internal/flows/email_verification.py`) *does* mark the `EmailAddress` as verified as a side effect of successfully entering the reset code — because in the code-based flow the email being reset is explicitly known and confirmed in the same step. **The link-based reset flow (this project's current, default configuration) has no equivalent step.**

---

## 4. Known "email verification loop" bugs/reports: causes

Root causes identified in allauth's own issue tracker, cross-referenced with the source behavior above:

- **Password reset ≠ email verification (this project's exact bug).** [Codeberg #1267](https://codeberg.org/allauth/django-allauth/issues/1267), [GH #2084](https://github.com/pennersr/django-allauth/issues/2084), [GH #2360](https://github.com/pennersr/django-allauth/issues/2360) — see Q3. The user cycles: request reset → set password → bounced to "verify email" → gets a fresh verification email → (if they don't click it, or click it in a different browser/session so auto-login doesn't fire — see below) → next login attempt re-triggers `EmailVerificationStage` again, which re-sends *another* verification email rather than ever completing login. This isn't strictly infinite (clicking the confirmation link does permanently flip `verified=True` in the DB, regardless of session — confirmed via `allauth/account/views.py::ConfirmEmailView` → `verify_email_and_resume()` → `verification.confirm(request)`), but the *messaging* the user receives at each step ("check your email" after a password reset they just completed) reads as a loop and is very easy to get stuck in if they keep using "forgot password" instead of clicking the verification link specifically.
- **`LOGIN_ON_EMAIL_CONFIRMATION` is session-bound.** `login_on_verification()` (`allauth/account/internal/flows/email_verification.py`) explicitly only auto-logs-in "when the user that is in the process of signing up is present in the session" — i.e. same browser/tab that initiated the flow. Its own docstring warns: *"This may not 100% work in case the user closes the browser (and the session gets lost)."* Clicking a confirmation link from an email app on another device, or after the session expired, silently skips auto-login (`stage.abort()` is called) even though the email address itself does get marked verified in the DB. Users then have to log in manually — which, combined with the point above, is often mistaken for "still broken."
- **Accounts created outside the normal signup form have no verification email sent at all.** [Issue #1861 – "Email verification not sent on login for mandatory settings if User and EmailAddress object are created not from signup form (e.g. from `python manage.py shell`)"](https://github.com/pennersr/django-allauth/issues/1861). Relevant if any part of this project's onboarding creates users programmatically (e.g. admin-created accounts, bulk imports, cohort enrolment) without going through the signup form — such users can be permanently stuck at "please verify" with no email ever queued.
- **Multiple `EmailAddress` rows / primary flag confusion.** allauth enforces (migration `0003_alter_emailaddress_create_unique_verified_email.py`, present in installed source) a **partial unique DB constraint**: only one `EmailAddress` row with `verified=True` can exist for a given email address across the whole table (gated by `ACCOUNT_UNIQUE_EMAIL`, default `True`). Combined with `unique_together=("user","email")`, this means duplicate *unverified* rows for the same email across different users are possible (this is exactly the "multiple accounts sharing the same email" case the enumeration docs mention for optional/disabled verification — not directly triggered under this project's mandatory-verification config, but relevant background if `ACCOUNT_EMAIL_VERIFICATION` is ever loosened). A management command `account_unsetmultipleprimaryemails` ships with allauth specifically to clean up "multiple primary emails per user" data drift, implying this has been a recurring real-world data-integrity issue.
- **"Mandatory not actually blocking login" reports** — the inverse bug, e.g. [Issue #3047 – "ACCOUNT_EMAIL_VERIFICATION = 'mandatory' not preventing unverified email login"](https://github.com/pennersr/django-allauth/issues/3047) and [Issue #1490 – "Automatic log in on sign up despite 'mandatory' email verification"](https://github.com/pennersr/django-allauth/issues/1490). Not this project's bug (which is the opposite — user *can't* log in), but worth being aware of if regression-testing a fix: a naive fix could accidentally flip into "mandatory is bypassed entirely," which is its own class of reported issue.
- **Typo'd email at signup = permanent lock-out**, a related but distinct trap: if `ACCOUNT_EMAIL_VERIFICATION="mandatory"` and a user mistypes their email, the verification link goes to an inbox they don't control, and because login is blocked pre-verification they have no ordinary way to reach account settings to fix the typo. Covered generally (not allauth-issue-tracker-specific) in community write-ups, e.g. [technetexperts.com — "Django Allauth Mandatory Email Verification"](https://www.technetexperts.com/django-allauth-email-typo-fix/), which recommends a dedicated unauthenticated "change my email before verifying" recovery view. This is a structurally related but separate failure mode from the enumeration-prevention loop described in this project's bug.

---

## 5. Version-specific notes

- **This project's pin:** `django-allauth[headless]==65.15.1` (from `uv.lock`), constrained by `pyproject.toml` as `>=65.14.0`.
- **`ACCOUNT_LOGIN_METHODS`** (replacing the older `ACCOUNT_AUTHENTICATION_METHOD` string setting: `"username"` / `"username_email"` / `"email"`) was introduced in **65.4.0 (2025-02-06)**, done in a backwards-compatible manner within allauth itself (third-party packages reading the old `AUTHENTICATION_METHOD` attribute directly could break) — per the allauth changelog (`ChangeLog.rst`) on GitHub. This project already uses the new-style `ACCOUNT_LOGIN_METHODS = {"email"}`, so it is on the current settings API, not the deprecated one.
- **`ACCOUNT_SIGNUP_FIELDS`** (replacing `ACCOUNT_EMAIL_REQUIRED`, `ACCOUNT_USERNAME_REQUIRED`, `ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE`, `ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE`) was introduced in **65.5.0 (2025-03-14)**, also backwards compatible. This project already uses `ACCOUNT_SIGNUP_FIELDS`, so likewise on current API.
- Both of the above predate the project's `>=65.14.0` floor, so the installed `65.15.1` and the `>=65.14.0` constraint are consistent with (and require) the new-style settings already in use — no further settings migration is needed on that front.
- **`ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED`** and its `verify_email_indirectly()` side effect (Q3) are **already present in the installed 65.15.1 source** (confirmed by reading `allauth/account/app_settings.py` and `allauth/account/internal/flows/password_reset_by_code.py` directly) — this is not a "need to upgrade" item, it's an available-but-unused opt-in switch in the current pin.
- The official docs page itself (`docs.allauth.org`) mentions an `ACCOUNT_PREVENT_ENUMERATION = "strict"` mode that reportedly lets signups go through even for taken emails specifically to avoid the "silently discard the password" ambiguity. **This string literal `"strict"` does not appear anywhere in the installed 65.15.1 source** (confirmed via full-tree grep of the venv) — i.e. as of this pin, `ACCOUNT_PREVENT_ENUMERATION` behaves as a plain boolean in code even though the docs describe a tri-state. This exact discrepancy is the subject of [Issue #3657](https://github.com/pennersr/django-allauth/issues/3657), which at the time of this research had not yet been resolved/clarified upstream. **Do not rely on `"strict"` as a value with this pinned version** — verify against the changelog before using it if allauth is upgraded.

---

## 6. Recommended, well-known configuration patterns to avoid the loop (options, not a prescribed fix)

These are documented/community-known levers; presented as options for the spec author to weigh, not a recommendation to implement all of them:

1. **Enable `ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True`.** Per [Codeberg #1267](https://codeberg.org/allauth/django-allauth/issues/1267) this is the maintainer-endorsed built-in fix: password reset via a one-time code (rather than a static emailed link) explicitly calls `verify_email_indirectly()` on successful code entry, so a password reset *does* verify the email and `LOGIN_ON_PASSWORD_RESET` then works as expected without a second verification round-trip. Trade-off: changes the reset UX from "click a link" to "enter a code," which is a broader UX change (also affects `ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED`-style flows) and would need its own template/UX review.
2. **Customize `send_account_already_exists_mail()` in the project's existing `AccountAdapter`** (`freedom_ls/accounts/allauth_account_adapter.py` already overrides `ACCOUNT_ADAPTER`) to branch on whether the existing account's email is verified or not, and send copy/links appropriate to each case (e.g. "resend verification" link instead of "forgot password" for an unverified pre-existing account). Requires knowing internally whether the address is verified without leaking that fact to the *requester* if enumeration prevention must be preserved for suspicious/adversarial cases — a genuine design tension the spec should weigh explicitly.
3. **Provide/point to a "resend confirmation email" entry point** reachable without being logged in (allauth ships `account_email_verification_sent` / resend flows) so a user stuck post-password-reset in the mandatory-verification stage has an obvious, documented way forward rather than relying on interpreting a flash message.
4. **Loosen `ACCOUNT_EMAIL_VERIFICATION` to `"optional"`** for login purposes (still send verification mail, but don't block login) — sidesteps the whole class of "verification blocks login after this-or-that flow" bugs at the cost of allowing unverified accounts to use the product. Explicitly a trade-off the docs call out as reducing enumeration-prevention efficacy at signup (Q1/Q2) and is a meaningfully different security posture than the project's current `"mandatory"`.
5. **Do nothing to the reset flow, but make the `EmailVerificationStage` bounce itself login-completing** — i.e. rely on `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION=True` (already set) and ensure the "new" verification email sent during the password-reset detour actually gets clicked in the *same* browser session so `login_on_verification()`'s session check succeeds and the user lands in an authenticated state after one extra click. This requires no code change but is fragile: any session loss (different device/browser, expired session, email client pre-fetching links) breaks it silently (see Q4).
6. **Keep `ACCOUNT_PREVENT_ENUMERATION=True` as-is and treat this as an unverified-account clean-up/UX problem, not an enumeration-setting problem** — since the enumeration behavior on signup is working as documented/intended (Q1), the actual defect is arguably confined to the mandatory-verification vs. password-reset gap (Q3), which is independent of enumeration prevention and would reproduce even with `ACCOUNT_PREVENT_ENUMERATION=False` for any account that is unverified and attempts password reset.

---

## References

- [Configuration — django-allauth (dev docs)](https://docs.allauth.org/en/dev/account/configuration.html)
- [ACCOUNT_PREVENT_ENUMERATION docs are unclear / confusing · Issue #3657](https://github.com/pennersr/django-allauth/issues/3657)
- [Users' email addresses can be leaked · Issue #1307](https://github.com/pennersr/django-allauth/issues/1307)
- [Account enumeration via add email address endpoint · Issue #3318](https://github.com/pennersr/django-allauth/issues/3318)
- [Verify email during password reset · Issue #1267 (Codeberg)](https://codeberg.org/allauth/django-allauth/issues/1267)
- [Unable to treat password resets as email verification confirmations · Issue #2084](https://github.com/pennersr/django-allauth/issues/2084)
- [Send password reset to verified emails · Issue #2360](https://github.com/pennersr/django-allauth/issues/2360)
- [Email verification not sent on login for mandatory settings if User/EmailAddress created outside signup form · Issue #1861](https://github.com/pennersr/django-allauth/issues/1861)
- [ACCOUNT_EMAIL_VERIFICATION = "mandatory" not preventing unverified email login · Issue #3047](https://github.com/pennersr/django-allauth/issues/3047)
- [Automatic log in on sign up despite "mandatory" email verification · Issue #1490](https://github.com/pennersr/django-allauth/issues/1490)
- [Duplicate Email Address in Django AllAuth — Django Forum thread](https://forum.djangoproject.com/t/duplicate-email-address-in-django-allauth/19064)
- [django-allauth ChangeLog.rst (GitHub, main)](https://github.com/pennersr/django-allauth/blob/main/ChangeLog.rst)
- [Django Allauth Mandatory Email Verification (typo/lock-out recovery pattern)](https://www.technetexperts.com/django-allauth-email-typo-fix/)
- Installed source of record for all code-level claims: `.venv/lib/python3.13/site-packages/allauth/` at pinned version `65.15.1` in this worktree (`allauth/account/forms.py`, `allauth/account/internal/flows/signup.py`, `allauth/account/internal/flows/email_verification.py`, `allauth/account/internal/flows/password_reset.py`, `allauth/account/internal/flows/password_reset_by_code.py`, `allauth/account/stages.py`, `allauth/account/models.py`, `allauth/account/adapter.py`, `allauth/account/migrations/0003_alter_emailaddress_create_unique_verified_email.py`).

status: ok
