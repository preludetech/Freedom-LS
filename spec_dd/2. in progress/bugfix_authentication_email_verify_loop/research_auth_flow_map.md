# Auth flow map

Scope: map every code path an unauthenticated user can take from "click enroll on a free
course" through signup/login/verification/password-reset, with emphasis on the
existing-email + enumeration-prevention branch that the reported bug lives in. All allauth
internals referenced below are read from the installed package at
`.venv/lib/python3.13/site-packages/allauth/` (this is a vendored/pinned dependency, not
project code, but its exact behavior is load-bearing for the bug and is cited by path).

## 0. Relevant settings (config/settings_base.py:326-350)

```
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*", "first_name*", "last_name"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = "mandatory"          # settings_base.py:338
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True        # settings_base.py:339
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True            # settings_base.py:340
ACCOUNT_ADAPTER = "freedom_ls.accounts.allauth_account_adapter.AccountAdapter"  # :342
ACCOUNT_FORMS = {"signup": "freedom_ls.accounts.forms.SiteAwareSignupForm"}     # :343
ACCOUNT_PREVENT_ENUMERATION = True                # settings_base.py:345
ACCOUNT_RATE_LIMITS = {"signup": "5/m/ip,3/m/key"}  # dev: settings_dev.py:61 sets this to False
```

Combined meaning for the reported scenario:
- Every account requires a **verified email before login can complete** (`mandatory`).
- A successful email confirmation click **logs the user in immediately** (no separate login step needed) — `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION`.
- A successful password reset **also attempts to log the user in immediately** — `ACCOUNT_LOGIN_ON_PASSWORD_RESET`. Critically, this reset-triggered login is **not exempt from mandatory email verification** (see §3 below) — it goes through the exact same `LoginStageController` stage pipeline as any other login.
- `ACCOUNT_PREVENT_ENUMERATION=True` means signing up with an email that already has an account **does not error and does not create a second account** — it silently diverts into a "pretend this was a normal signup" response (§2), which is where the password-reset email in the bug report actually comes from.
- `settings_dev.py:107` sets `FORCE_SITE_NAME = "DemoDev"` — in dev, `get_cached_site()` always resolves the same Site regardless of Host header (see §6), which would mask a class of site-mismatch bugs that could otherwise surface in prod.

No project settings override `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`, `ACCOUNT_EMAIL_CONFIRMATION_COOLDOWN`, or `CONFIRM_EMAIL_ON_GET` — all allauth defaults apply (`CONFIRM_EMAIL_ON_GET=False`, confirm-email resend cooldown 180s — see §3).

## 1. Custom adapter (freedom_ls/accounts/allauth_account_adapter.py)

`AccountAdapter(DefaultAccountAdapter)` overrides:
- `send_mail()` (line 57) — adds branding context + forces 8-bit MIME encoding. Does not change verification/reset semantics.
- `save_user()` (line 136) — fires a `user.registered` webhook after `super().save_user()`. Only called on the **genuine** new-user path (`SignupForm.save()`, allauth `forms.py:430-439`) — **never** called on the existing-email/enumeration path, since that path never calls `form.save()` (see §2).
- `send_notification_mail()` (line 158) — injects `user` into context, otherwise passthrough.
- `is_open_for_signup()` (line 169) — site-scoped signup gate via `SiteSignupPolicy`/`config.ALLOW_SIGN_UPS`. Not part of the loop.

Not overridden (defaults from `allauth/account/adapter.py` apply verbatim): `send_account_already_exists_mail()` (adapter.py:657-668), `respond_email_verification_sent()` (adapter.py:694-695), `get_login_stages()` (adapter.py:796-800), `should_send_confirmation_mail()`.

## 2. Signup form(s)

`freedom_ls/accounts/forms.py:38` `SiteAwareSignupForm(SignupForm)`:
- Adds `first_name`/`last_name`, an `_hp` honeypot (line 51), and conditional T&C/Privacy checkboxes based on `SiteSignupPolicy`.
- Overrides `custom_signup()` (line 133) to write `LegalConsent` rows. This is only reached from `SignupForm.save()` → `self.custom_signup(request, user)` (allauth `forms.py:408-409, 437`) — i.e. **only on the genuine new-user path**.
- Does **not** override `clean_email`, `validate_unique_email`, `try_save`, or `save` — the existing-email detection and short-circuit is 100% inherited allauth base-class behavior (allauth `forms.py:364-439`).

`registration_forms.py` is unrelated to the signup form — it defines `RegistrationFormProtocol` for the **post-verification** `additional_registration_forms` step (§5/§7), not the allauth signup form.

### 2a. Allauth base-class mechanics for "email already exists" (existing-email signup)

- `SignupForm.clean_email()` → `validate_unique_email()` → `flows.manage_email.email_already_exists(value)` (allauth `forms.py:364-379`).
- `email_already_exists()` (allauth `internal/flows/manage_email.py:205-226`) calls `assess_unique_email()` (same file, `:137-`), which — because `ACCOUNT_PREVENT_ENUMERATION=True` and `ACCOUNT_EMAIL_VERIFICATION=mandatory` — returns `None` (not `True`/`False`) for a conflicting email, meaning "conflict exists, but hide it." This sets `form.account_already_exists = True` and does **not** raise a form validation error, so the form validates successfully with no visible error to the user.
- `assess_unique_email()` finds the conflict via `filter_users_by_email()` (allauth `account/utils.py:242-281`), which unions two sources: (a) allauth's own `EmailAddress` table (global, not site-scoped), and (b) `User.objects.filter(email=...)` — **this second source uses the project's custom `UserManager`** (`freedom_ls/accounts/models.py:52-60`), which is **site-scoped** via `_thread_locals.request` (see §6). Because `EmailAddress` is unscoped and `User.email` is DB-globally-unique (`models.py:96`), the union still finds the conflict in practice — but this is a latent inconsistency worth the fixer's attention (see "Suspicious loops" §S4).
- `SignupView.form_valid()` (allauth `views.py:143-156`):
  ```python
  def form_valid(self, form):
      self.user, resp = form.try_save(self.request)
      if resp:
          return resp                      # <-- existing-email branch returns HERE
      redirect_url = self.get_success_url()  # <-- only reached for a GENUINE new signup
      return flows.signup.complete_signup(self.request, user=self.user,
                                           redirect_url=redirect_url, by_passkey=form.by_passkey)
  ```
- `SignupForm.try_save()` (allauth `forms.py:411-428`): if `self.account_already_exists`, it **does not create a User row**, and calls `flows.signup.prevent_enumeration(request, email=email, phone=phone)` (allauth `internal/flows/signup.py:65-69`):
  ```python
  def prevent_enumeration(request, email=None, phone=None):
      login = Login(user=None, email=email, phone=phone, signup=True)
      return perform_login(context.request, login)
  ```
  Note: **no `redirect_url` is passed to `Login(...)` here**, unlike the genuine-signup path's `complete_signup(..., redirect_url=redirect_url, ...)` (allauth `internal/flows/signup.py:90-113`). This is the concrete code location where the `?next=` / deferred-enrollment target is silently dropped for the existing-email branch (see "Suspicious loops" §S1).
- `perform_login()` → `resume_login()` → `LoginStageController.handle()` (allauth `internal/flows/login.py:86-117`, `account/stages.py:113-135`) runs the stage pipeline with `login.user=None`. `EmailVerificationStage.handle()` (`stages.py:145-163`) sees `not has_verified_email(None, email)` → True, and calls `send_verification_email_at_login()` → `send_verification_email_at_fake_login()` (allauth `internal/flows/email_verification.py:279-319`) since `login.user` is `None`:
  ```python
  def send_verification_email_at_fake_login(request, login):
      address = EmailAddress(user=None, email=login.email)
      return send_verification_email_to_address(request, address, signup=True)
  ```
  In `send_verification_email_to_address()` (`email_verification.py:225-276`), because `address.user_id` is falsy, it takes the `elif signup: get_adapter().send_account_already_exists_mail(address.email)` branch (line 258-259) — **not** a real confirmation-link send.
- `AccountAdapter.send_account_already_exists_mail()` is **not overridden** in this project, so the default runs (allauth `adapter.py:657-668`):
  ```python
  def send_account_already_exists_mail(self, email):
      signup_url = flows.signup.get_signup_url(context.request)
      password_reset_url = flows.password_reset.get_reset_password_url(context.request)
      ctx = {"signup_url": signup_url, "password_reset_url": password_reset_url}
      self.send_mail("account/email/account_already_exists", email, ctx)
  ```
  `get_reset_password_url()` (allauth `internal/flows/password_reset.py:64-68`) resolves to the **password-reset *request* page** (`account_reset_password`, i.e. "enter your email to get a reset link"), **not** a keyed one-click reset link.
  Template used: `freedom_ls/accounts/templates/account/email/account_already_exists_message.html` — content: *"An account with the email address {{ email }} already exists ... If you forgot your password, you can reset it."* with a "Reset Password" CTA button pointing at `password_reset_url`.
- Meanwhile, `EmailVerificationStage.handle()` (`stages.py:160-162`) sets `response = get_adapter().respond_email_verification_sent(...)` regardless of whether an email was actually delivered, and the default adapter redirects to `account_email_verification_sent` (allauth `adapter.py:694-695`). The page rendered there is `allauth/templates/account/verification_sent.html`, whose copy is: *"We have sent an email to you for verification. Follow the link provided to finalize the signup process..."* — **identical wording** to the genuine new-signup case. The email actually sent (`account_already_exists_message.html`) contains a **password-reset link, not a verification link** — there is no way for the user to distinguish the two outcomes from the UI, and the page text actively tells them to look for a "verification" link that does not exist in their inbox (see "Suspicious loops" §S2).

## 3. What "reset password" actually completes to (existing/unverified account)

- User follows the `password_reset_url` from the email above → lands on `account_reset_password` (request form) → enters email again → allauth's `ResetPasswordForm.save()` (allauth `forms.py:631-644`) → `request_password_reset()` (allauth `internal/flows/password_reset.py:89-118`) sends a **second** email, this one with a genuine keyed link (`get_reset_password_from_key_url`), template `freedom_ls/accounts/templates/account/email/password_reset_key_message.html`.
- User clicks that keyed link → `PasswordResetFromKeyView.dispatch()` (allauth `views.py:595-637`) validates via `UserTokenForm` (allauth `forms.py:661-691`), whose `_get_user()` does:
  ```python
  def _get_user(self, uidb36):
      User = get_user_model()
      try:
          pk = url_str_to_user_pk(uidb36)
          return User.objects.get(pk=pk)   # <-- site-scoped UserManager, see §6
      except (ValueError, User.DoesNotExist):
          return None
  ```
  If this lookup fails (`User.DoesNotExist`), the reset key form reports **"invalid_password_reset"** and the user cannot proceed past this point at all (this is a *different*, earlier dead-end than the reported "verification loop" — see §S4).
- Assuming the lookup succeeds and the user sets a new password: `PasswordResetFromKeyView.form_valid()` (`views.py:657-664`) → `form.save()` (`ResetPasswordKeyForm.save()`, `forms.py:657-658`) actually changes the password via `flows.password_reset.reset_password()`, then `flows.password_reset.finalize_password_reset(request, reset_user)` (`internal/flows/password_reset.py:38-61`): <!-- pragma: allowlist secret -->
  ```python
  def finalize_password_reset(request, user, email=None):
      ...
      adapter.add_message(request, messages.SUCCESS, "account/messages/password_changed.txt")
      ...
      if app_settings.LOGIN_ON_PASSWORD_RESET:      # True in this project
          return perform_password_reset_login(request, user, email=email)
      return None
  ```
  `perform_password_reset_login()` (`password_reset.py:22-35`) builds `Login(user=user, email=email)` (**no explicit `email_verification` override** — defaults to the project's mandatory setting) and calls `perform_login()` → `resume_login()` → the **same** `LoginStageController.handle()` pipeline as every other login, including `EmailVerificationStage` (`stages.py:138-163`).
- **This is the crux of the "loop": if the account's `EmailAddress` was never verified** (e.g., the account was created by an earlier abandoned/incomplete signup attempt — exactly the kind of account that would trip the existing-email branch above), `has_verified_email(login.user, login.email)` is `False`, so:
  - The password *was* successfully changed (the "password changed" success message fires), **but the reset-triggered login is intercepted before completing** — `send_verification_email_at_login()` → `send_verification_email_at_real_login()` (`email_verification.py:296-306`) sends a **third**, genuine, confirm-email link (subject to the resend cooldown below), and the response is again `respond_email_verification_sent` → the same generic "verification sent" page as §2.
  - The user is **not logged in** even though they just successfully reset their password. Any subsequent login attempt with the new password (`account_login`) goes through the identical `EmailVerificationStage` gate and is blocked the same way until the email is actually verified — this is the mechanism that produces a login you can never complete purely by resetting your password again.
- Resend/cooldown trap: `send_verification_email_to_address()` (`email_verification.py:225-276`) is gated by `handle_verification_email_rate_limit()` → `consume_email_verification_rate_limit()` (`email_verification.py:148-185`), keyed on the email, using `app_settings.RATE_LIMITS["confirm_email"]`, which defaults to **`1 per EMAIL_CONFIRMATION_COOLDOWN seconds` (180s cooldown)** (allauth `app_settings.py:272-278`) — not overridden anywhere in `config/settings_*.py`. Critically, **`EmailVerificationStage.handle()` (`stages.py:159`) ignores the boolean return value of `send_verification_email_at_login()`** — the "verification sent" response is shown unconditionally, whether or not an email actually went out. So a user who retries login/reset within the 3-minute cooldown window sees "check your email" repeatedly while **no new email is being sent**, with no UI indication of the cooldown (see "Suspicious loops" §S2/§S5).
- `login_on_verification()` (`email_verification.py:106-145`) — the function that actually logs the user in when they click the (eventual) genuine confirm link — only succeeds if the **same session** still has the stashed `Login` object from the stage that requested verification (`LoginStageController.enter(request, EmailVerificationStage.key)`, `stagekit.unstash_login`). If the confirm link is opened in a different session/browser/device (common for email links — mail-client link prefetching, or opening on a phone), the email is marked verified but the user is **not** auto-logged-in (`email_verification.py:139-144`, `stage.abort()`), and they must log in again manually — a *plausible* but separate near-miss, not itself an infinite loop, since the next manual login should now pass `has_verified_email`.

## 4. Course-CTA deferred-signup path (new user vs existing-email user)

Entry point: `freedom_ls/student_interface/views.py:451-497` `initiate_course_access`, decorated `@login_required` (default `LOGIN_URL` resolves to allauth's `account_login`, path `accounts/login/` via `config/urls.py:67-68`).

- **Anonymous GET** → Django's `login_required` redirects to `account_login?next=<initiate_course_access URL>` (verified by `freedom_ls/accounts/tests/test_deferred_login.py:194-210`).
- **Login page → "sign up" link**: allauth's `login.html`/`signup.html` both forward `next` via `NextRedirectMixin` (allauth `account/mixins.py:140-192`) as a hidden `redirect_field` (`{{ redirect_field }}` in the templates), which the project does **not** override (no `freedom_ls/accounts/templates/account/signup.html` — confirmed via glob, allauth's default template is used verbatim).
- **New-user signup via CTA**: `SignupView.form_valid()` → `self.get_success_url()` (reads the forwarded `?next=`) → `flows.signup.complete_signup(request, user=user, redirect_url=next_url, ...)` (allauth `internal/flows/signup.py:90-113`) → `Login(..., redirect_url=redirect_url, signup=True)` → after the (still-mandatory) email-verification stage completes and the user later clicks the confirm link, `login_on_verification()` → `stage.exit()` → `resume_login()` eventually calls `adapter.post_login()`, which honors `login.redirect_url` — the user lands back at `initiate_course_access` and gets enrolled. This path is exercised by `test_deferred_login_free_course_enrolls_and_redirects` (`test_deferred_login.py:213-235`), though that test simulates post-auth state via `force_login` rather than driving the email link end-to-end.
- **Existing-email user via CTA (the bug's actual repro)**: identical to §2's "existing-email signup" branch — `try_save()` short-circuits `form_valid()` at `resp` before `get_success_url()`/`redirect_url` is ever computed (allauth `views.py:143-146`). **The `next=<initiate_course_access URL>` the user arrived with is silently discarded.** Even in the "best case" where the account eventually gets verified and logged in (via §3's password-reset-then-verify chain), nothing in that chain re-derives the original course-enroll intent — the user is dropped at `LOGIN_REDIRECT_URL` (`"/"`, `settings_base.py:379`) or wherever `finalize_password_reset`'s login lands them, not back at the course. This is provable purely from `SignupView.form_valid()` never reaching `get_success_url()` on this branch, independent of whatever ultimately breaks the verification loop.

`RegistrationCompletionMiddleware` (`freedom_ls/accounts/middleware.py`) sits after `AccountMiddleware` in `MIDDLEWARE` (`settings_base.py:148-149`) and exempts (`EXEMPT_URL_NAMES`, lines 32-48) exactly: `account_login`, `account_logout`, `account_signup`, `account_email_verification_sent`, `account_confirm_email`, `account_email`, `account_reset_password`, `account_reset_password_done`, `account_reset_password_from_key`, `account_reset_password_from_key_done`, `accounts:legal_doc`, `accounts:complete_registration`. All allauth entrance/verification/reset views used above are covered, so this middleware itself does not intercept mid-verification — but once a user *is* authenticated and lands anywhere else (e.g. after the reset-triggered login eventually succeeds), it can add one more forced hop through `accounts:complete_registration?next=...` before reaching the course (view: `freedom_ls/accounts/views.py:76-113`). `complete_registration_view`'s POST-redirect uses `_safe_post_completion_redirect()` (`views.py:60-68`), which validates `next` via `url_has_allowed_host_and_scheme` and falls back to `LOGIN_REDIRECT_URL`.

## 5. Post-verification "additional registration forms" (SiteSignupPolicy)

- `freedom_ls/accounts/models.py:165-186` `SiteSignupPolicy` — per-site `additional_registration_forms: list[str]` (dotted paths to `RegistrationFormProtocol` forms, loaded/validated by `freedom_ls/accounts/registration_forms.py`).
- Enforced by `RegistrationCompletionMiddleware.__call__` (`middleware.py:85-134`): for any authenticated, non-exempt request, it computes `get_incomplete_forms(user, dotted_paths)` and — if any are incomplete — redirects to `accounts:complete_registration?next=<original destination>`, caching completion status in `request.session["_registration_completion_state"]` (`CACHE_SESSION_KEY`, line 73).
- This step is **orthogonal** to the email-verification loop (it only ever runs for already-authenticated users, and `dev` settings set `REQUIRE_TERMS_ACCEPTANCE=True` with no `additional_registration_forms` configured by default in `settings_base.py:359`), but it is one more hop the fixer needs to account for when reasoning about "does `next` survive all the way to the course" once a user does get logged in.

## 6. Site-awareness cross-cutting concern

- `freedom_ls/site_aware_models/middleware.py` `CurrentSiteMiddleware` sets `_thread_locals.request = request` for **every** request (including all allauth URLs, since it's registered globally in `MIDDLEWARE`, `settings_base.py:146` — before `AccountMiddleware`).
- `freedom_ls/accounts/models.py:52-60` `UserManager.get_queryset()` filters `User.objects` by `get_cached_site(request)` whenever `_thread_locals.request` is set — i.e. **`User.objects` is always site-scoped**, for every allauth internal query that goes through `get_user_model().objects` (not just project code).
- `email` is a globally-unique DB column (`models.py:96`, no site scoping on the constraint), so at most one `User` row can ever exist for a given email regardless of site — but several allauth internals resolve users via `User.objects.get(pk=...)` / `.filter(email=...)` (`filter_users_by_email`, allauth `account/utils.py:274`; `UserTokenForm._get_user`, allauth `forms.py:668-674`) which, under this project's manager, will return **`DoesNotExist`/empty** if the *current request's resolved site* differs from the *site stored on that user's row* (`User.site` FK, inherited from `SiteAwareModelBase`, `site_aware_models/models.py:53-54`).
- `settings_dev.py:107` (`FORCE_SITE_NAME = "DemoDev"`) pins `get_cached_site()` to a single Site in dev regardless of Host header, which would hide any bug of this shape locally; production has no such pin (`config/settings_prod.py` sets no `FORCE_SITE_NAME`), so `get_cached_site()` falls through to its domain-based resolution (`site_aware_models/models.py:19-` — not fully traced here, out of scope for this map, but is the resolution path that would matter in prod).

## Suspicious loops / dead-ends

- **S1 — Lost enrollment intent on existing-email signup.** `SignupView.form_valid()` (allauth `views.py:143-156`) returns the `prevent_enumeration()` response before ever calling `self.get_success_url()`, so the `?next=<enroll-url>` carried from `initiate_course_access` (`student_interface/views.py:451`) is dropped on the floor whenever the signup email already exists. Even a fully successful eventual login will not return the learner to the course. Verified purely by reading `try_save()`/`form_valid()` control flow (allauth `forms.py:411-428`, `views.py:143-146`) — no test in `test_deferred_login.py` exercises the existing-email branch.
- **S2 — Indistinguishable "verification sent" UX.** `EmailVerificationStage.handle()` (allauth `stages.py:145-163`) renders the exact same `verification_sent.html` copy ("follow the link ... to finalize the signup process") whether (a) a genuine confirm-email link was sent, (b) a "your account already exists, reset your password" email was sent instead (`send_account_already_exists_mail`, adapter.py:657-668, template `account_already_exists_message.html`), or (c) **no email was sent at all** because the 180s resend cooldown suppressed it (`handle_verification_email_rate_limit`, `email_verification.py:167-185`, return value silently ignored at `stages.py:159`). A user who keeps retrying login while genuinely waiting for a "verify your email" link that was never going to arrive (because their address was actually swallowed into the enumeration-prevention branch) has no way to discover this from the UI.
- **S3 — Reset-triggered login re-enters mandatory verification with no escape hatch shown.** `finalize_password_reset()` → `perform_password_reset_login()` (allauth `internal/flows/password_reset.py:22-61`) runs the full `LoginStageController` pipeline, including `EmailVerificationStage`, for a password reset that just succeeded. If the underlying account's email was never verified (plausible precisely for an account that got created by an earlier abandoned/incomplete signup and is now being "re-signed-up" via the course CTA), the user is bounced to the same generic "verification sent" page instead of being logged in — password changed, but no way in. Every subsequent login attempt hits the identical gate (`account_login` → same `LoginStageController`/`EmailVerificationStage` path). This is the most directly evidenced mechanism for "resets password, then is stuck in an email-verification loop that never completes."
- **S4 — Password-reset key link can 404/"invalid" under site mismatch.** `UserTokenForm._get_user()` (allauth `forms.py:668-674`) resolves the reset-link's user via `User.objects.get(pk=pk)`, which is the project's site-scoped `UserManager` (`freedom_ls/accounts/models.py:52-60`). If the request's resolved site (via `CurrentSiteMiddleware`/`get_cached_site`) differs from the `site` FK stored on that user row, the lookup raises `DoesNotExist`, `_get_user` returns `None`, and the reset form reports "invalid_password_reset" — a dead end that looks like an expired/broken link and would push the user to request yet another reset email, repeating indefinitely. This is a *different*, earlier-in-the-chain dead end than S3, but shares the same "keep requesting resets, keep failing" shape. Masked in dev by `FORCE_SITE_NAME` (`settings_dev.py:107`); not masked in prod.
- **S5 — Confirm-link session dependency.** `login_on_verification()` (allauth `email_verification.py:106-145`) only auto-logs-in the learner if the *same session* that triggered `EmailVerificationStage` is still present when the confirm link is clicked (`LoginStageController.enter` + `stagekit.unstash_login`). Clicking the link from a different device/browser/incognito tab (very common with email links) marks the address verified but does **not** log the user in and does **not** carry forward any `redirect_url` — they must log in again manually via `account_login`, at which point (assuming verification now succeeded) they should get through, but they are then subject to §5's `RegistrationCompletionMiddleware`/`complete_registration` hop before ever reaching the course, with no guarantee `next` was preserved that far (see S1 — if `next` was already lost at signup time, it is lost for the rest of the entire chain, including this branch).

## Key files

Project code (must read/likely touch):
- `freedom_ls/accounts/allauth_account_adapter.py` — custom `AccountAdapter`; does **not** currently override `send_account_already_exists_mail`, `respond_email_verification_sent`, or `should_send_confirmation_mail`.
- `freedom_ls/accounts/forms.py` — `SiteAwareSignupForm`; does not override `clean_email`/`try_save`/`save`.
- `freedom_ls/accounts/middleware.py` — `RegistrationCompletionMiddleware`, `EXEMPT_URL_NAMES`.
- `freedom_ls/accounts/views.py` — `complete_registration_view`, `_safe_post_completion_redirect`.
- `freedom_ls/accounts/models.py` — `User`, `UserManager` (site-scoped queryset), `SiteSignupPolicy`.
- `freedom_ls/accounts/utils.py` — `get_signup_policy_for_request`, `get_effective_*` helpers.
- `freedom_ls/accounts/registration_forms.py` — additional-registration-form loader/protocol.
- `freedom_ls/accounts/templates/account/email/account_already_exists_message.html` — the enumeration-prevention email body (password-reset CTA).
- `freedom_ls/site_aware_models/middleware.py`, `freedom_ls/site_aware_models/models.py` — `CurrentSiteMiddleware`, `_thread_locals`, `get_cached_site`, `SiteAwareModelBase`.
- `freedom_ls/student_interface/views.py:451-497` — `initiate_course_access` (the CTA chokepoint).
- `freedom_ls/accounts/tests/test_deferred_login.py` — existing coverage of `next` survival (currently only covers the new-user path + middleware; **no test exercises the existing-email/enumeration branch**).
- `freedom_ls/accounts/tests/test_allauth_signup_policy.py`, `test_signup_form.py`, `test_signup_rate_limit.py`, `test_registration_completion_middleware.py`, `test_complete_registration_view.py` — adjacent existing coverage to check for regressions.
- `config/settings_base.py:326-350`, `config/settings_dev.py:34,61,107`, `config/settings_prod.py:163` — allauth-relevant settings.
- `config/urls.py:67-68` — `allauth.urls` include order (before `freedom_ls.accounts.urls`).

Vendored dependency code (read-only reference, cited for exact mechanics — do not edit):
- `.venv/lib/python3.13/site-packages/allauth/account/forms.py` — `SignupForm` (`try_save`, `save`, `clean_email`), `ResetPasswordForm`, `ResetPasswordKeyForm`, `UserTokenForm`.
- `.venv/lib/python3.13/site-packages/allauth/account/views.py` — `SignupView.form_valid`, `ConfirmEmailView`, `PasswordResetFromKeyView`.
- `.venv/lib/python3.13/site-packages/allauth/account/adapter.py` — `DefaultAccountAdapter.send_account_already_exists_mail`, `respond_email_verification_sent`, `get_login_stages`.
- `.venv/lib/python3.13/site-packages/allauth/account/stages.py` — `LoginStageController`, `EmailVerificationStage`.
- `.venv/lib/python3.13/site-packages/allauth/account/internal/flows/signup.py` — `prevent_enumeration`, `complete_signup`.
- `.venv/lib/python3.13/site-packages/allauth/account/internal/flows/email_verification.py` — `send_verification_email_to_address`, `send_verification_email_at_fake_login`/`_real_login`, `login_on_verification`, rate-limit helpers.
- `.venv/lib/python3.13/site-packages/allauth/account/internal/flows/password_reset.py` — `finalize_password_reset`, `perform_password_reset_login`, `request_password_reset`, URL builders.
- `.venv/lib/python3.13/site-packages/allauth/account/internal/flows/manage_email.py` — `assess_unique_email`, `email_already_exists`.
- `.venv/lib/python3.13/site-packages/allauth/account/utils.py` — `filter_users_by_email`.
- `.venv/lib/python3.13/site-packages/allauth/account/app_settings.py:262-293` — default `RATE_LIMITS` (confirm-email cooldown).
- `.venv/lib/python3.13/site-packages/allauth/templates/account/verification_sent.html`, `.../account/messages/email_confirmation_sent.txt` — the shared "verification sent" copy.

status: ok
