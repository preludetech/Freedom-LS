# Research: every rate limit / lockout / throttle a visitor can hit

Scope: inventory every throttle reachable through the browser, what it renders today, and how to
provoke it in QA. Allauth version installed: 65.15.1 (confirmed against
`spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/4. plan.md:54`, cross-checked directly against
`.venv/lib/python3.13/site-packages/allauth/`).

---

## The master table

| # | Limit (scope) | Configured where | Rule in effect | What triggers it | HTTP status | Template / response rendered today | Branded? |
|---|---|---|---|---|---|---|---|
| 1 | allauth `signup` | `config/settings_base.py:430-433` (`ACCOUNT_RATE_LIMITS["signup"]`) | `5/m/ip` (overrides allauth's own default `20/m/ip`, `allauth/account/app_settings.py:293`) | 6th `POST /accounts/signup/` from one IP inside 60s | **429** | `rate_limit(action="signup")` decorator on `SignupView.dispatch` (`allauth/account/views.py:133`) → `ratelimit.consume_or_429` → `respond_429` (`allauth/core/ratelimit.py:53-64`) → looks for `config.urls.handler429` (does not exist, see below) → falls back to `allauth.core.internal.ratelimit.handler429` → tries to render `429.html` → `TemplateDoesNotExist` (no `429.html` exists anywhere in this repo **or** in the allauth package) → falls back to a **hardcoded literal HTML string** returned via bare `HttpResponse` | **Bare.** No CSS, no nav, no theme, plain `<html><h1>429 Too Many Requests</h1>...</html>` |
| 2 | allauth `login` (every login attempt, success or failure) | Not overridden — allauth default `30/m/ip` (`allauth/account/app_settings.py:295`) | `30/m/ip` | 31st `POST /accounts/login/` from one IP inside 60s | **429** | Same decorator/fallback chain as #1 (`rate_limit(action="login")` on `LoginView.dispatch`, `allauth/account/views.py:90`) | **Bare**, same as #1 |
| 3 | allauth `login_failed` | `config/settings_base.py:430-433` override `"10/m/ip,5/5m/key"` (states explicitly what allauth would otherwise compute from deprecated `ACCOUNT_LOGIN_ATTEMPTS_LIMIT`/`_TIMEOUT`, which this project does **not** set — confirmed absent from both settings files) | `10/m/ip` **and** `5/300s` per email (key = `f"{site.domain}:{login}"`, `allauth/account/adapter.py:697-700`) | 11th failed login from one IP inside 60s, or 6th failed attempt against one email within 5 minutes | **200** (not 429) | `AccountAdapter.pre_authenticate` (`allauth/account/adapter.py:719-728`) raises `ValidationError("too_many_login_attempts")` when `ratelimit.consume(...)` returns falsy. `LoginForm` catches this as an ordinary form error and **re-renders `account/login.html`** (allauth's stock template — FLS does not override `account/login.html`, only its layout, `freedom_ls/base/templates/allauth/layouts/entrance.html`) with the message **"Too many failed login attempts. Try again later."** | **Branded shell** (FLS's entrance layout/header), but this is a **form validation error on the ordinary login page**, not a distinct error page. Confirmed empirically: `spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/qa_report.md:145-149` — "the eleventh spray attempt returns the login form with 'Too many failed login attempts...' — not the lockout page, no 429" |
| 4 | allauth `reset_password` (request a reset email) | Not overridden — default `"20/m/ip,5/m/key"` (`allauth/account/app_settings.py:287`) | 21st reset request from one IP/min, or 6th for one email/min | `POST /accounts/password/reset/` | **429** | Explicit `ratelimit.consume_or_429(...)` in `PasswordResetView.form_valid` (`allauth/account/views.py:541-548`) → same bare 429 fallback as #1 | **Bare** |
| 5 | allauth `reset_password_from_key` (the link the reset email sends) | Not overridden — default `"20/m/ip"` (`allauth/account/app_settings.py:291`) | 21st visit/submit of a reset-confirm link from one IP/min | `GET`/`POST` on `PasswordResetFromKeyView` | **429** | `rate_limit` decorator on `dispatch` (`allauth/account/views.py:577`) → same bare 429 fallback | **Bare** |
| 6 | allauth `change_password` | Not overridden — default `"5/m/user"` (`allauth/account/app_settings.py:281`) | 6th password-change POST by one signed-in user/min | `POST /accounts/password/change/`, **login required** | **429** | `login_required` + `rate_limit` decorators on `PasswordChangeView.dispatch` (`allauth/account/views.py:444-445`) → same bare 429 fallback | **Bare** — and this one is reachable by a signed-in learner mid-course (account settings) |
| 7 | allauth `manage_email` | Not overridden — default `"10/m/user"` (`allauth/account/app_settings.py:285`) | 11th email-management POST by one signed-in user/min | `POST /accounts/email/`, **login required** | **429** | `login_required` + `rate_limit` on `EmailView.dispatch` (`allauth/account/views.py:300-301`) → same bare 429 fallback | **Bare** — reachable mid-course |
| 8 | allauth `reauthenticate` | Not overridden — default `"10/m/user"` (`allauth/account/app_settings.py:289`) | 11th reauth POST by one signed-in user/min | Any flow requiring a fresh password re-entry (e.g. viewing MFA recovery codes), **login required** | **429** | Explicit `ratelimit.consume_or_429` in `BaseReauthenticateView._check_ratelimit` (`allauth/account/views.py:1002-1012`) → same bare 429 fallback | **Bare** — reachable mid-course |
| 9 | allauth `confirm_email` (resend the verification link) | Not overridden — default derives from `EMAIL_CONFIRMATION_COOLDOWN` (default 180s) → `"1/180s/key"` (`allauth/account/app_settings.py:275-278`) | One resend per email per 3 minutes | Any code path that resends a verification email while `EMAIL_VERIFICATION_BY_CODE_ENABLED=False` (this project's setting — link-based, mandatory verification), e.g. `verified_email_required` decorator's automatic resend (`allauth/account/decorators.py:43`) | **No visible response at all** | `handle_verification_email_rate_limit` (`allauth/account/internal/flows/email_verification.py:167-185`): when link-based (not code-based), hitting this limit is deliberately **silent** — the function's own docstring says "it is not an issue if the user runs into rate limits… we can just silently skip sending additional verification emails." No error, no message, no page change. | N/A — nothing renders differently |
| 10 | allauth `request_login_code` | Default `"20/m/ip,3/m/key"` (`allauth/account/app_settings.py:297`) | — | **Unreachable in this project.** `LOGIN_BY_CODE_ENABLED` defaults `False` (`allauth/account/app_settings.py:547-548`) and is never set in `config/settings_base.py` or `config/settings_dev.py` | — | — | N/A |
| 11 | allauth `verify_phone` | Default `"1/30s/key,3/m/ip"` (`allauth/account/app_settings.py:303`) | — | **Unreachable through normal navigation.** `PHONE_VERIFICATION_ENABLED` defaults `True`, but `ACCOUNT_LOGIN_METHODS = {"email"}` (`config/settings_base.py:403`) and `ACCOUNT_SIGNUP_FIELDS` (`config/settings_base.py:396-402`) carry no `phone` field, so no UI path ever collects a phone number to verify | — | — | N/A |
| 12 | allauth `change_phone` | Default `"1/m/user"` (`allauth/account/app_settings.py:283`) | — | Same as #11 — unreachable, no phone field in signup/login config | — | — | N/A |
| 13 | **django-axes lockout** (not allauth) | `config/settings_base.py:318-341` — `AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1` (hour), `AXES_LOCKOUT_PARAMETERS=[["ip_address","username"],"username"]`, `AXES_RESET_ON_SUCCESS=True`, `AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT=False`, `AXES_CLIENT_IP_CALLABLE="freedom_ls.accounts.utils.get_client_ip"`, `AXES_LOCKOUT_TEMPLATE="accounts/lockout.html"` | 5 failed logins for the **same (ip_address, username) pair together**, OR 5 failed logins for the **same username alone regardless of IP** (the flat entry is what catches an address-rotating spray against the Django `/admin/login/` too — see the comment at `config/settings_base.py:320-328`) | 5th failed `POST /accounts/login/` (or `/admin/login/`) for a locked pair/username | **429** (`AXES_HTTP_RESPONSE_CODE` default in the installed axes version, `.venv/lib/python3.13/site-packages/axes/conf.py:161`; FLS does not override it) | `axes/helpers.py:518-519` — `render(request, settings.AXES_LOCKOUT_TEMPLATE, context, status=429)` → `freedom_ls/accounts/templates/accounts/lockout.html`, which `{% extends "allauth/layouts/entrance.html" %}` (FLS's own branded shell → `allauth/layouts/base.html` → `_base.html`) | **Branded.** Heading "Too many sign-in attempts" with a padlock icon, body copy, a "Back to sign in" button and a "Reset it now" password-reset link. Confirmed rendered and screenshotted in `spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/qa_report.md:92-121`, and pinned by `freedom_ls/accounts/tests/test_lockout_page.py` |

### Django's own error handlers
`config/urls.py` defines **no** `handler400/403/404/429/500`. There is no `429.html` anywhere in the
repo (`Glob **/429.html` — zero matches, checked project-wide including `.venv`). This is exactly
the gap the idea document names: nothing currently intercepts allauth's `respond_429()` fallback, so
every "hard 429" row in the table above (rows 1, 2, 4, 5, 6, 7, 8) renders the same bare, unbranded,
un-themed literal string.

---

## 1. django-allauth `ACCOUNT_RATE_LIMITS`

**Configured scopes** (`config/settings_base.py:430-433`):
```python
ACCOUNT_RATE_LIMITS: dict[str, str] | bool = {
    "signup": "5/m/ip",
    "login_failed": "10/m/ip,5/5m/key",
}
```
This is a **partial override** — allauth merges it over its own computed default dict with
`ret.update(rls)` (`allauth/account/app_settings.py:305`), so every scope not named here still
applies at allauth's default value. The full default dict, read directly from
`allauth/account/app_settings.py:279-304`:

```python
{
    "change_password": "5/m/user",  # pragma: allowlist secret
    "change_phone": "1/m/user",
    "manage_email": "10/m/user",
    "reset_password": "20/m/ip,5/m/key",  # pragma: allowlist secret
    "reauthenticate": "10/m/user",
    "reset_password_from_key": "20/m/ip",  # pragma: allowlist secret
    "signup": "20/m/ip",                       # <- overridden by FLS to 5/m/ip
    "login": "30/m/ip",
    "request_login_code": "20/m/ip,3/m/key",
    "login_failed": "10/m/ip,{LOGIN_ATTEMPTS_LIMIT}/{LOGIN_ATTEMPTS_TIMEOUT}s/key",  # <- overridden
    "confirm_email": "1/{EMAIL_CONFIRMATION_COOLDOWN}s/key",
    "verify_phone": "1/30s/key,3/m/ip",
}
```
`login_failed`'s computed default is `"10/m/ip,5/300s/key"` (from `LOGIN_ATTEMPTS_LIMIT=5`,
`LOGIN_ATTEMPTS_TIMEOUT=300`), and `parse_duration` maps `5m` → `300.0`
(`allauth/core/internal/ratelimit.py:52-64`), so FLS's explicit `"10/m/ip,5/5m/key"` states the same
number rather than leaving it to the deprecated pair — confirmed by
`freedom_ls/accounts/tests/test_login_rate_limit.py:31-39`. `confirm_email`'s default is
`"1/180s/key"` (`EMAIL_CONFIRMATION_COOLDOWN` defaults to 180, `allauth/account/app_settings.py:275`).

**Why `signup` carries no per-key rate**, per the comment at `config/settings_base.py:412-419`: the
signup view's `rate_limit(action="signup")` decorator passes no `key`, so a per-`key` rate on that
scope would raise `ImproperlyConfigured` on every POST (`get_cache_key`,
`allauth/core/internal/ratelimit.py:106-112`). This is why FLS's override is IP-only.

**Mechanics that decide the response** (`allauth/core/internal/ratelimit.py` and
`allauth/core/ratelimit.py`):
- `consume()` is a no-op on plain `GET` requests unless the caller passes `limit_get=True`
  (`ratelimit.py:161-162`) — most of the account views only rate-limit their `POST`.
- Two enforcement styles exist in allauth's own code:
  1. **Hard 429**, via `rate_limit()` decorator or a direct `consume_or_429()` call →
     `respond_429()` (`allauth/core/ratelimit.py:53-64`). This is what rows 1, 2, 4, 5, 6, 7, 8 in
     the master table use.
  2. **Caught `RateLimited` → form/flash-message re-render**, used only for the code-based
     confirmation/resend flows (`allauth/account/views.py:938,1171,1277`) and for
     `login_failed` via `pre_authenticate`'s `ValidationError` (row 3). None of the code-based flows
     are reachable in this project (see rows 10-12).
- `respond_429()` first tries `import_callable(f"{settings.ROOT_URLCONF}.handler429")` —
  `config.urls` defines no `handler429`, so this raises `AttributeError`/`ImportError` and falls
  through to allauth's own `_impl.handler429` (`allauth/core/ratelimit.py:59-64`), which tries
  `render(request, "429.html", ...)` and, finding none, falls back to the hardcoded string
  (`allauth/core/internal/ratelimit.py:184-205`).

**Templates checked for an override and not found:** no `429.html` anywhere in
`freedom_ls/base/templates/`, `freedom_ls/accounts/templates/`, or the allauth package itself (its
shipped template tree has no `429.html` or `account/rate_limit*.html` at all — confirmed by listing
every `.html` under `allauth/templates/`).

---

## 2. django-axes lockout

Settings, all in `config/settings_base.py:318-341`:
- `AXES_FAILURE_LIMIT = 5`
- `AXES_COOLOFF_TIME = 1` (hour — axes' own semantics; confirmed by the inline comment and by
  `3. frontend_qa.md:92`, "Lockouts also last one hour")
- `AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"], "username"]` — two independent rules: the
  nested pair locks only when one address fails against one username five times; the flat
  `"username"` entry locks that username regardless of address, which is what closes the gap on
  `/admin/login/` (allauth's own `login_failed` limit only wraps allauth's login view, not the admin
  login — see the comment at `config/settings_base.py:320-328`)
- `AXES_RESET_ON_SUCCESS = True` — a correct login clears that user's failure count
- `AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False` — continuing to hammer a locked account
  does **not** push the hour further out (axes' own default is `True`, i.e. it would)
- `AXES_CLIENT_IP_CALLABLE = "freedom_ls.accounts.utils.get_client_ip"` — the project's own IP
  resolver (`freedom_ls/accounts/utils.py:20-57`), which returns `TRUSTED_PROXY_IP_HEADER`'s value
  verbatim if that setting names a header, else `REMOTE_ADDR`; raises `PermissionDenied` if the
  configured header is missing/malformed
- `AXES_LOCKOUT_TEMPLATE = "accounts/lockout.html"` — without it axes serves its own bare
  plain-text body "Account locked: too many login attempts" (this literal string is asserted absent
  in `freedom_ls/accounts/tests/test_lockout_page.py:20,52`)

**Response mechanics** (`axes/helpers.py:490-527`): status comes from `AXES_HTTP_RESPONSE_CODE`,
whose default in the installed axes version is **429**
(`.venv/lib/python3.13/site-packages/axes/conf.py:161`) — not overridden anywhere in this project.
When `AXES_LOCKOUT_TEMPLATE` is set, axes calls
`render(request, template, context, status=429)` directly — this is a real Django template render,
not a fallback string. `freedom_ls/accounts/templates/accounts/lockout.html` extends
`allauth/layouts/entrance.html` (FLS's own override, which extends `allauth/layouts/base.html` →
`_base.html`, the site's root shell), so this page is fully branded: header/logo, the padlock icon,
heading "Too many sign-in attempts", body copy, a "Back to sign in" button and a password-reset link.

**QA recipes, read directly from the existing tests:**
- `freedom_ls/accounts/tests/test_lockout_page.py:23-31` — `_lock_out()` posts 5 wrong-password
  logins to `reverse("account_login")` for one real user's email; asserts
  `response.status_code == 429` and `"accounts/lockout.html"` is among the rendered template names.
- `freedom_ls/accounts/tests/test_login_rate_limit.py:24-28` posts to the same URL with
  `{"login": email, "password": "wrong-password"}`.  # pragma: allowlist secret
- Manual QA recipe used previously (`spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/3. frontend_qa.md:60-96`):
  reset with `uv run python manage.py axes_reset` before and after each provocation (it prints
  "N attempts removed"); five wrong-password POSTs for one email locks that (IP, username) pair; a
  **different** email from the same browser/IP still succeeds (proves the nested rule); the same
  locked email still 429s even with the *correct* password until reset; spoofing
  `X-Real-IP`/`X-Forwarded-For` changes nothing because `TRUSTED_PROXY_IP_HEADER` is `None` in dev,
  so `get_client_ip` ignores the header and axes still keys on `127.0.0.1`.

---

## 3. Anything else — grep results across `freedom_ls/` and `config/`

Grepped case-insensitively for `throttl|rate.?limit|ratelimit|RateLimit|429|TooManyRequests` across
all of `freedom_ls/`. Matches, beyond the accounts tests already covered above:

- `freedom_ls/webhooks/delivery.py:157-160,189-195` — handles a **429 response from a remote
  webhook receiver** (outbound delivery retry logic: on `response.status_code == 429` it reads
  `Retry-After` and reschedules; other 4xx marks the delivery permanently failed). This is FLS
  delivering webhooks *to* a downstream system, not a page any learner or visitor sees. Confirmed by
  reading the surrounding function names (`_handle_retryable_failure`, `_handle_permanent_failure`) —
  no HTTP response is returned to a browser here.
- `freedom_ls/deployment/checks.py:324-415` — two `manage.py check --deploy` checks that reference
  rate limiting but do not themselves render anything a visitor sees: `E005` (fails deploy checks if
  the `DatabaseCache` table doesn't exist yet, which "allauth's rate limiting reads... on every login
  and signup") and `E006` (fails if `ALLAUTH_TRUSTED_CLIENT_IP_HEADER` and `TRUSTED_PROXY_IP_HEADER`
  name different headers, which would let allauth's rate limits and axes' lockout key on different
  addresses for the same visitor).
- **Nothing found** in `freedom_ls/course_applications/`, `freedom_ls/course_interest/`, the health
  endpoint (`freedom_ls/health/`), or anywhere resembling an API — no throttling exists on course
  application submission, course interest submission, or any other learner-facing form outside the
  allauth/axes surfaces already tabulated. This project has no DRF/ninja API with its own throttle
  classes (the `NinjaAPI` import in `config/urls.py:29-37` is commented out).

---

## 4. Cache dependency

- **Dev** (`config/settings_dev.py`): no `CACHES` setting at all → Django's built-in default,
  `LocMemCache`, per-process and wiped on restart. **Dev also sets `ACCOUNT_RATE_LIMITS = False`**
  (`config/settings_dev.py:67`), which — because allauth's `RATE_LIMITS` property returns `{}`
  outright when the raw setting `is False` (`allauth/account/app_settings.py:264-265`) — disables
  **every** allauth scope, not just the two FLS names, since `consume()` treats a missing action key
  as "no limit" (`allauth/core/internal/ratelimit.py:163-165`). Axes is **not** affected by this
  setting — axes lockouts remain fully live in plain dev.
- **Production** (`config/settings_prod.py:85`, sourced from
  `freedom_ls/deployment/settings_defaults.py:74-90`): `CACHES = fls_defaults.DATABASE_CACHES` — a
  Postgres-table-backed `django.core.cache.backends.db.DatabaseCache`, `LOCATION="django_cache_table"`,
  `MAX_ENTRIES=50000`. The table is **not** created by a migration; `createcachetable` must run as
  part of the deploy sequence, or the first login/signup raises `ProgrammingError` deep inside the
  auth flow (guarded at deploy-check time by `E005`, `freedom_ls/deployment/checks.py:324-375`).
  Axes itself is configured for its **database handler** (rows in `AccessAttempt`, not this cache) —
  confirmed by the plan note at `spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/4. plan.md:20-22`,
  "axes runs on the database handler and its counters are rows in Postgres."

**What this means for QA:** a plain local dev run (`config.settings_dev`) can hit the **axes
lockout** (row 13) with no extra setup — it is completely independent of `ACCOUNT_RATE_LIMITS`. It
**cannot** hit any of rows 1–9 (every allauth-cache-backed scope), because `ACCOUNT_RATE_LIMITS =
False` zeroes all of them out. Reproducing rows 1–9 requires overriding `ACCOUNT_RATE_LIMITS` for the
run. The prior QA pass for a related spec did this with a **throwaway settings module** (never
committed, deleted after the run):
```python
# config/settings_qa_check.py  (git-ignored / deleted before commit)
from .settings_dev import *  # noqa: F401,F403
ACCOUNT_RATE_LIMITS = {
    "signup": "5/m/ip",
    "login_failed": "10/m/ip,5/5m/key",
}
```
— run the dev server with `--settings=config.settings_qa_check`
(`spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/3. frontend_qa.md:60-81`). No such module exists
in the repo today (confirmed: `Glob config/settings_qa_check.py` → no matches) — it was deleted per
that spec's own cleanup instructions and must be recreated for this spec's QA pass. Note also from
that same QA report: because dev's cache is `LocMemCache` living inside the running server process,
there is **no reset command** for the allauth counters (unlike axes' `axes_reset`) — the only way to
clear them mid-QA-session is to restart the dev server
(`spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/3. frontend_qa.md:94-96`).

---

## 5. Reachable by an authenticated learner mid-course vs. entrance-only

**Entrance-only (signed-out, anonymous visitor):**
- `signup` (row 1), `login` (row 2), `login_failed` (row 3), `reset_password` (row 4),
  `reset_password_from_key` (row 5), and the **axes lockout** (row 13) all sit on
  `/accounts/login/`, `/accounts/signup/`, `/accounts/password/reset/…` — all decorated
  `login_not_required` or naturally unauthenticated flows. These render inside (or, for the bare 429
  fallback, entirely outside) the **signed-out entrance layout**.

**Reachable mid-course by an already-authenticated learner:**
- `change_password` (row 6) — `/accounts/password/change/`, `login_required`.
- `manage_email` (row 7) — `/accounts/email/`, `login_required`.
- `reauthenticate` (row 8) — triggered by any sensitive-action flow (e.g. viewing MFA recovery
  codes) that needs a fresh re-entry of the password, `login_required` in practice.
- `confirm_email` resend cooldown (row 9) — can fire for a signed-up-but-unverified user repeatedly
  hitting a page guarded by `verified_email_required`, but it is silent (see row 9), so there is no
  page for it to need branding on.

These three "hard 429" rows (6, 7, 8) are the ones that most concretely argue against treating the
rate-limit page as purely an entrance-page concern: a learner deep in their account settings, not on
any auth page, can trip the same bare fallback. FLS's account-management pages use
`allauth/layouts/manage.html` (`freedom_ls/base/templates/allauth/layouts/manage.html`), which itself
extends the same `allauth/layouts/base.html` → `_base.html` root shell that `entrance.html` extends —
so the two layouts share the same page chrome (header/branding) and differ only in their content
wrapper (a centered `max-w-2xl` column for entrance vs. a two-column content+nav split for manage).
A rate-limit/429 page built once against `_base.html` (or reusing the pattern
`accounts/lockout.html` already established) would suit both signed-in and signed-out surfaces
without needing two versions.

---

status: ok
