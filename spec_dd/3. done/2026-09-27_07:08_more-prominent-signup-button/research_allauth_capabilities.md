# Research: django-allauth capabilities for login/signup switching and unknown-email detection

Installed version: **django-allauth 65.15.1** (`.venv/lib/python3.13/site-packages/allauth/__init__.py:11`).
Installed `axes`: present, version not pinned to a specific file read, but source at
`.venv/lib/python3.13/site-packages/axes/` — confirmed installed and wired into
`AUTHENTICATION_BACKENDS` / `MIDDLEWARE` (see §4).

Official docs: https://docs.allauth.org/en/latest/ (this install predates the `docs.allauth.org`
rename cutover but the API matches the "latest" docs tree; the settings referenced below are all
still current there). Config reference: https://docs.allauth.org/en/latest/account/configuration.html

---

## 1. Login/signup templates, `next` propagation, email prefill

**Templates** (source, not yet overridden in this repo — confirm with
`freedom_ls/**/templates/account/login.html` / `signup.html` if a project override exists):
- `.venv/lib/python3.13/site-packages/allauth/templates/account/login.html`
- `.venv/lib/python3.13/site-packages/allauth/templates/account/signup.html`

`login.html` renders a plain sentence + link: *"If you have not created an account yet, then please
<a href="{{ signup_url }}">sign up</a> first."* directly above the form (not styled as a button).
`signup.html` mirrors it: *"Already have an account? Then please <a href="{{ login_url }}">sign
in</a>."* Neither template gives the counterpart link any visual prominence (no button styling) —
this is exactly the gap the spec is targeting.

**`next` propagation is automatic and bidirectional.** Both `signup_url` and `login_url` are built by
`get_entrance_context_data()` in
`.venv/lib/python3.13/site-packages/allauth/account/internal/templatekit.py:13-40`, which calls
`passthrough_next_redirect_url(request, reverse("account_signup"), REDIRECT_FIELD_NAME)` (and the
login equivalent). `REDIRECT_FIELD_NAME` is Django's `"next"`. So: a learner sent to
`/accounts/login/?next=/courses/apply/...` who clicks "sign up" is taken to
`/accounts/signup/?next=/courses/apply/...` — the `next` value survives the switch with **zero
custom code**. This also means "clearer login/signup switching" (e.g. turning the existing link into
a prominent button) is a template-only change; the URL-building/redirect machinery already does the
right thing.

**Email prefill into signup is supported, but only via `?email=`, not automatically from the login
form.** `SignupView.get_initial()`
(`.venv/lib/python3.13/site-packages/allauth/account/views.py:171-182`) reads
`request.GET.get("email")`, validates it, and sets it as the initial value of the `email` (and
`email2`, if enabled) field. So a link built as
`{{ signup_url }}&email={{ request.GET.login|urlencode }}` (or equivalent) will prefill signup's
email field. **Nothing in stock allauth carries the email typed into the login form over to the
signup link** — the login template's `signup_url` only carries `next`. To prefill from what the
learner typed at login, a project-level template/view change is needed: read `form.cleaned_data`
(or raw POST) for the `login` field on a failed attempt and append `?email=...` to `signup_url` in
the login template context (or override `get_context_data`).

Separately, `SignupView.get_context_data()` also prefills from
`request.session.get("account_verified_email")` (set by e.g. email-verification-by-code flows) —
irrelevant here but worth knowing it's a second prefill path.

---

## 2. Features that blur login/signup, and interaction with `ACCOUNT_PREVENT_ENUMERATION`

Settings source: `.venv/lib/python3.13/site-packages/allauth/account/app_settings.py`.

- **`ACCOUNT_LOGIN_BY_CODE_ENABLED`** (default `False`; not set in `settings_base.py`, so it's
  currently **off**). When on, `login.html` shows a "Send me a sign-in code" button
  (`login.html:45-49`) alongside the password form. Flow logic:
  `.venv/lib/python3.13/site-packages/allauth/account/internal/flows/login_by_code.py`.
  Crucially, `LoginCodeVerificationProcess.send_by_email()` (lines 98-112) branches on whether a
  matching user exists: if yes, it emails a real code; **if no, it silently calls
  `send_unknown_account_mail()`** instead of a code, and in both cases calls
  `add_sent_message()` with the *same* "a code was sent" success message
  (`account/messages/login_code_sent.txt`). This is deliberate enumeration prevention: the visitor
  cannot tell from the response whether their email had an account. There is no `ACCOUNT_SIGNUP_BY_CODE`
  setting in this version — only `ACCOUNT_LOGIN_BY_CODE_ENABLED` and, separately,
  `ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED` (controls whether signup's *own* email-confirmation
  step uses a 6-digit code vs. a clickable link; unrelated to login).

- **"Login by code for unknown email"**: as above — allauth already treats an email with no account
  as a first-class (if silent) case in the login-by-code flow, sending an "unknown account" mail
  rather than a code, without changing the visible response. This is effectively allauth's closest
  built-in analogue to "detect an unknown email and react differently" while staying
  enumeration-safe, and could be a model for how FLS's own recording hook should behave (log
  server-side, keep the response identical).

- **`ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS`** (default `True`; not overridden in `settings_base.py`, so
  active). Read in `.venv/lib/python3.13/site-packages/allauth/account/app_settings.py:531-532`.
  Governs `send_unknown_account_mail()`
  (`.venv/lib/python3.13/site-packages/allauth/account/internal/flows/signup.py:72-80`), which is
  called from **both** `login_by_code.py` (unknown email requests a code) and
  `internal/flows/password_reset.py:89-94` (`request_password_reset()`: if no `users` match the
  submitted email, send the "no account" mail instead of a reset link). In both call sites the
  outward response is identical to the "account exists" case — a generic "check your email" success
  message — so `PREVENT_ENUMERATION`-style safety is preserved regardless of this setting's value;
  the setting only controls whether the *courtesy* "you have no account here, want to sign up?"
  email actually gets sent.

- **No built-in identifier-first flow.** allauth does not ship a "type your email first, then we
  decide whether to show you a password field or a signup form" UX. The nearest things are (a) the
  login-by-code flow (still requires knowing in advance whether you want login-by-code vs.
  password), and (b) the signup's `?email=` prefill (still requires a separate decision of which
  page to land on). Building a true identifier-first flow would be custom FLS work layered on top of
  these primitives, not a stock allauth feature.

- **`ACCOUNT_PREVENT_ENUMERATION`** (`True` in `settings_base.py:419`, and default `True`) is read at
  `app_settings.py:37-39`. It is consulted piecemeal, not as one central switch:
  - Login form (`LoginForm._clean_with_password`,
    `.venv/lib/python3.13/site-packages/allauth/account/forms.py:210-224`) **always** raises the
    same generic `"email_password_mismatch"` error
    (`"The email address and/or password you specified are not correct."`,
    `.venv/lib/python3.13/site-packages/allauth/account/adapter.py:67-69`) whether the email is
    unknown or the password is simply wrong — this generic wording is not conditional on
    `PREVENT_ENUMERATION` at all; there is no separate "unknown email" message shown at the login
    screen in any configuration. This is why the visitor "kept retrying" with no external signal
    that the account didn't exist.
  - Signup form's `clean()` (`forms.py:381-407`) and `try_save()` (`forms.py:411-…`): when
    `PREVENT_ENUMERATION` is on and the submitted signup email/phone already has an account, allauth
    does **not** show "email already taken" — it sets `account_already_exists = True` and, on save,
    calls `flows.signup.prevent_enumeration()` (`internal/flows/signup.py:65-69`), which performs a
    fake "login" (creates a `Login(user=None, ..., signup=True)` and proceeds through the normal
    post-signup redirect/messaging) so the response is indistinguishable from a real new signup.
  - Password reset (`request_password_reset`, `internal/flows/password_reset.py:89-94`): same
    generic success message whether or not a user was found; only the unknown-account courtesy email
    differs (gated by `EMAIL_UNKNOWN_ACCOUNTS`, see above).

  Net effect for the "clearer switching" idea: **enumeration prevention is baked deeply into every
  response path**, so any new UX (prominent signup button, prefill, etc.) is safe to build without
  weakening it — as long as new code doesn't add a *new* response that reveals account existence
  (e.g. don't render "no account found, redirecting you to signup" text).

---

## 3. Hook points for detecting "login failed, no account for that email"

**Best hook: `AccountAdapter.authentication_failed(request, **credentials)`.**
Defined as a no-op in `DefaultAccountAdapter`
(`.venv/lib/python3.13/site-packages/allauth/account/adapter.py:750-751`) and called from
`DefaultAccountAdapter.authenticate()` (`adapter.py:730-748`) whenever Django's
`authenticate(request, **credentials)` returns no user. `credentials` is the same dict
`LoginForm.user_credentials()` builds (`forms.py:148-170`) — for this project's
`ACCOUNT_LOGIN_METHODS = {"email"}` config it will contain `{"email": "<what they typed>",
"password": "<what they typed>"}`. This is called on **every** failed login attempt (unknown email
*or* wrong password for a known email), so `freedom_ls.accounts.allauth_account_adapter.AccountAdapter`
can override it to:
1. Look up whether `credentials.get("email")` matches a `User` (case-insensitively, matching
   `filter_users_by_email` semantics in `auth_backends.py:74-85`).
2. If no match, record a "failed sign-in, unknown email" event, capturing `request` (for
   `request.GET.get("next")`/`request.POST.get("next")`, IP, user agent, path) alongside the email.
3. Call `super().authentication_failed(request, **credentials)` (currently a no-op, but future-proof).

**Does this leak anything to the visitor?** No. `authentication_failed()`'s return value is ignored —
`adapter.authenticate()` still returns `None` and the caller (`LoginForm._clean_with_password`,
`forms.py:219-223`) always raises the same generic `email_password_mismatch` validation error
regardless of what `authentication_failed()` does internally (see §2). As long as the override
doesn't call `add_message`, raise, or otherwise touch the response/session, it is purely a
server-side side-channel — safe under `PREVENT_ENUMERATION`.

**Rate-limit hook (`pre_authenticate`)**: `DefaultAccountAdapter.pre_authenticate()`
(`adapter.py:719-728`) runs *before* the credential check and enforces `ACCOUNT_RATE_LIMITS
["login_failed"]` via a cache key of `f"{site.domain}:{login.lower()}"`
(`_get_login_attempts_cache_key`, `adapter.py:697-700`, using `credentials.get("email", ...)`). It
raises `too_many_login_attempts` (still a generic message) before `authentication_failed` would ever
run, if the per-email/per-IP rate limit is already exhausted — so under sustained retries from one
visitor, `authentication_failed` stops firing once the `login_failed` rate limit trips (10/m/ip,
5/5m/key per this project's config) and the generic "too many attempts" error is shown instead. Any
recording logic added to `authentication_failed` should be aware it may under-count once the visitor
is rate-limited — the rate limiter itself, plus axes (§4), still see every attempt.

**`LoginForm.clean()` / `_clean_with_password()`** (`forms.py:176-224`) is where the
`email_password_mismatch` / `username_password_mismatch` validation error is actually raised, after
`adapter.authenticate()` returns `None`. It's a valid alternate hook (subclass `LoginForm`, override
`clean`) but `authentication_failed` is more targeted and doesn't require re-registering
`ACCOUNT_FORMS["login"]`.

**Signals**: allauth's own `allauth.account.signals` module
(`.venv/lib/python3.13/site-packages/allauth/account/signals.py`) has **no login-failure signal** —
only `user_logged_in`, `user_signed_up`, `password_set/changed/reset`, `email_*`, and
`authentication_step_completed` (fired on *successful* steps only). The only failure signal in play
is **Django's own `django.contrib.auth.signals.user_login_failed`**, fired by Django's
`django.contrib.auth.authenticate()` (which allauth calls internally) when every backend in
`AUTHENTICATION_BACKENDS` returns `None`. Its signal handler receives `sender`, `credentials`
(sanitized), and `request`. Django's sanitization (`django.contrib.auth._clean_credentials`)
**scrubs any credential key whose name matches `password`/`api`/`token`/`key`/`secret`/`signature`
(case-insensitive)** to `"********************"` — `email` and `login` keys pass through unscrubbed,
so the signal receiver can read the submitted email but never the password. This signal fires once
per `authenticate()` call, i.e. once per submitted login attempt, same cardinality as
`authentication_failed`. Given axes already listens to this exact signal (§4), a project receiver on
`user_login_failed` is a viable alternative to overriding `authentication_failed`, with the
difference that `authentication_failed` is scoped to allauth's own login view/flows while
`user_login_failed` also fires for `/admin/login/` and anywhere else `authenticate()` is called.

**`AccountAdapter.pre_login` / `is_open_for_signup`**: `pre_login` (`adapter.py:490-502`) only runs
*after* a successful authentication (checks `user.is_active`) — not useful for unknown-email
detection. `is_open_for_signup` (overridden already in
`freedom_ls/accounts/allauth_account_adapter.py:161-186`) is unrelated to login failure but relevant
to constraint #5 below.

---

## 4. `django-axes`

**Installed and active.** `.venv/lib/python3.13/site-packages/axes/` exists;
`config/settings_base.py:141` lists `"axes"` in `INSTALLED_APPS`, `:168` adds
`"axes.middleware.AxesMiddleware"`, `:320` puts `"axes.backends.AxesStandaloneBackend"` first in
`AUTHENTICATION_BACKENDS`. Config block at `settings_base.py:326-349`
(`AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1`, `AXES_LOCKOUT_PARAMETERS=[["ip_address","username"],
"username"]`, `AXES_RESET_ON_SUCCESS=True`,
`AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT=False`,
`AXES_CLIENT_IP_CALLABLE="freedom_ls.accounts.utils.get_client_ip"`,
`AXES_LOCKOUT_TEMPLATE="accounts/lockout.html"`).

Axes listens to Django's `user_login_failed` signal
(`.venv/lib/python3.13/site-packages/axes/signals.py:26-28`) and, via
`AXES_HANDLER` (default `axes.handlers.database.AxesDatabaseHandler`, not overridden here), persists
an `AccessAttempt` row per failing (username, ip_address, user_agent) combination
(`.venv/lib/python3.13/site-packages/axes/models.py:38-51`) with fields:
- `username` (from `credentials[AXES_USERNAME_FORM_FIELD]`, default `get_user_model().USERNAME_FIELD`
  — which is `"email"` for this project's custom `User` model
  (`freedom_ls/accounts/models.py:81`) — so it correctly captures the submitted email even when no
  account exists),
- `ip_address`, `user_agent`, `http_accept`,
- `path_info` (the request path — e.g. `/accounts/login/`, not the `next` target),
- `attempt_time`, `failures_since_start`,
- `get_data` / `post_data` (raw querystring/POST body, with `password` and anything in
  `AXES_SENSITIVE_PARAMETERS` — default `["username", "ip_address"]`, plus `password` is *always*
  cleansed — masked to asterisks via `cleanse_parameters()` in
  `.venv/lib/python3.13/site-packages/axes/helpers.py:402-425`).

There's also an opt-in `AccessFailureLog` model (`models.py:24-35`, one row per failure incl. whether
it triggered a lockout) gated by `AXES_ENABLE_ACCESS_FAILURE_LOG` (default `False`, not set in this
project, so **not** currently populated).

**Implication for the spec**: axes already records every failed login attempt, including unknown
emails, with IP/UA/path/timestamp — but **not** the `next` query param (only `path_info`, which is
the login URL itself, and `get_data` which *does* include the full raw querystring, so `next` is
technically recoverable from `get_data` on GET-carried logins, but not cleanly queryable, and
`AccessAttempt` is keyed for lockout bookkeeping, not staff review — it has no "reviewed" workflow,
no relation to a course/enrollment, and rows get reset/cleared on successful login
(`AXES_RESET_ON_SUCCESS=True`) or cooloff expiry). If the goal is "staff can follow up on someone who
tried to apply for a course and gave up," a **purpose-built model** (e.g. in `accounts` or
`learner_management`) populated from the `authentication_failed` hook, storing the email, the `next`
URL, and a timestamp, is more appropriate than trying to repurpose axes' `AccessAttempt`/
`AccessFailureLog` tables, which are designed to be transient security bookkeeping, not a staff
worklist.

---

## 5. Constraints

- **`LOGIN_URL`**: not set explicitly anywhere in `config/settings_base.py` (confirmed via grep) —
  Django's default `"/accounts/login/"` is used, and it lines up with allauth's URL include at
  `config/urls.py:63` (`path("accounts/", include("allauth.urls"))`). Any change to send unauthenticated
  course-application flows to `/accounts/signup/` instead should be done at the call site
  (`login_required`/redirect logic in the course-application view) rather than by changing
  `LOGIN_URL` globally — flipping `LOGIN_URL` to the signup page would break every other
  `@login_required` redirect in the app (admin, educator interface, etc.), which all legitimately
  want existing users routed to login, not signup.

- **Per-site signup closed (`is_open_for_signup`)**: FLS already overrides this in
  `freedom_ls/accounts/allauth_account_adapter.py:161-186` via `SiteSignupPolicy` (falls back to
  `config.ALLOW_SIGN_UPS`). `SignupView` is wrapped by `CloseableSignupMixin`
  (`.venv/lib/python3.13/site-packages/allauth/account/mixins.py:116-137`), which checks
  `is_open()` on **every** dispatch and renders `account/signup_closed.html` if closed. **This is a
  hard constraint on "send people to signup instead of login": if the site's `SiteSignupPolicy` (or
  the global `ALLOW_SIGN_UPS` fallback) has signups disabled, redirecting a not-yet-registered
  visitor to `/accounts/signup/` will dead-end them on the closed-signup page instead of getting
  them to a course application.** Any new "prominent signup button" or auto-redirect-to-signup logic
  must check `get_adapter(request).is_open_for_signup(request)` first and fall back to login (or a
  "contact us" message) when signup is closed for that site.

- **Headless mode**: `allauth.headless` is **not installed** — `INSTALLED_APPS` only has `"allauth"`
  and `"allauth.account"` (`settings_base.py:139-141`); the `HEADLESS_*` settings and the
  `_allauth/` URL include are commented out (`settings_base.py:145-149,403,453,455`;
  `config/urls.py:69`). So none of this needs to account for allauth's headless/API-token flows —
  everything here is the classic server-rendered Django view flow.

---

status: ok
