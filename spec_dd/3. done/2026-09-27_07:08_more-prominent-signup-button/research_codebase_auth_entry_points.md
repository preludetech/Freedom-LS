# Research: auth entry points for the "apply → login page → gave up" problem

Read-only codebase research for `spec_dd/1. next/more-prominent-signup-button/idea.md`.

## 1. Every path that sends an unauthenticated visitor to login vs. signup

### The apply flow, traced exactly

- `course_detail` (`freedom_ls/learner_interface/views.py:702`) is **anonymous-safe** — it renders for
  logged-out visitors. For a not-registered visitor it renders the access backend's CTA
  (`decision.cta_label` / `decision.cta_url`, `freedom_ls/course_access/backends.py:41`).
  - Free course → `cta_url` = `learner_interface:initiate_course_access` ("Enrol for free").
  - Application-gated course → `cta_url` = `course_applications:apply` ("Apply now") —
    `freedom_ls/course_applications/backends.py:155-167` (`ApplicationCourseAccessBackend.get_access`).
- Both `initiate_course_access` (`learner_interface/views.py:844`) and `apply`
  (`freedom_ls/course_applications/views.py:58`) are decorated **`@login_required`** — plain vanilla
  Django, no custom wrapper.
- An anonymous click on either CTA therefore hits `django.contrib.auth.decorators.login_required`,
  which calls `redirect_to_login(request.get_full_path(), settings.LOGIN_URL, REDIRECT_FIELD_NAME)`.
  There is **no `LOGIN_URL` override** in `config/settings_base.py` (confirmed by grep) — Django's
  default `/accounts/login/` is used, which is allauth's `account_login` view.
  **So: clicking "Apply now" or "Enrol for free" while logged out always lands on the login page**,
  with `?next=<apply-or-initiate-url>`, never on signup. This is the exact mechanism the idea
  describes: an unauthenticated applicant is sent to sign-**in**, not sign-**up**.
- `course_applications:apply` itself, once authenticated, is also `login_required`; for a
  form-bearing application it drops the visitor onto the first form page
  (`_start_application`, `apply.html`, `check_your_answers.html`).
- `course_interest` (express-interest on a coming-soon course) is the one flow that does **not**
  use `login_required` for its POST endpoints (`freedom_ls/course_interest/views.py:36-104`) — it
  branches manually on `request.user.is_authenticated` and calls
  `redirect_to_auth(request, next_url=...)` (`freedom_ls/accounts/utils.py:110-139`) so an htmx POST
  gets a `204 + HX-Redirect` instead of a 302 a htmx XHR would swap into the page. The target is
  still the **login** page (`redirect_to_auth`'s `auth_url` defaults to `settings.LOGIN_URL`), via a
  GET-safe `deferred_express_interest` landing view (`course_interest/urls.py`,
  `course_interest/views.py:107-127`) that replays the interest-recording after sign-in.
- `RegistrationCompletionMiddleware` (`freedom_ls/accounts/middleware.py`) also uses
  `redirect_to_auth`, but only for **already-authenticated** users with incomplete post-verification
  forms — irrelevant to a visitor with no account at all.

### Where the "next" is preserved (and where it isn't)

- `django.contrib.auth.login_required`'s redirect and allauth's own login/signup forms both honour
  `?next=`. `freedom_ls/accounts/templatetags/accounts_tags.py:15` (`url_with_next`) wraps allauth's
  `passthrough_next_redirect_url` so that **every** login/signup link on the page — the header's
  Login/Sign-up buttons (`login_prompt.html`) and allauth's own in-form "sign up first" /
  "sign in" links — carry the same validated `next` forward. This is recent, deliberate work
  (`spec_dd/3. done/2026-09-18_14:10_bug-authentication-next-target-sometimes-lost/`) that replaced
  an earlier, reverted custom "next-threading" hack
  (`spec_dd/3. done/2026-07-17_09:12_bugfix-shitty-allauth-decisions/idea.md`) — read that idea.md if
  touching this area again; it explicitly warns against re-adding custom next-machinery and says
  "vanilla `@login_required` + allauth already handle the redirect perfectly well."
  `freedom_ls/accounts/tests/test_header_auth_links_carry_next.py` is the regression suite proving:
  a visitor who clicks Apply while logged out and lands on `/accounts/login/?next=<apply-url>` sees
  **two** links to signup that both carry `next=<apply-url>` (the in-form link and the header
  button), and signing up through either lands them back on the apply page after email
  confirmation.
- **So the "next" is already preserved end-to-end** if the visitor does eventually click signup.
  The reported failure mode (repeatedly submitting the login form, then giving up) happens
  *before* that: they never notice/click the signup link at all.

### `login_prompt.html` (header, anonymous state)

`freedom_ls/base/templates/partials/login_prompt.html`:
```
{% url_with_next "account_login" as login_url %}
<div class="flex items-center gap-2">
    <c-button href="{{ login_url }}">Login</c-button>
    {% if allow_signups %}
        {% url_with_next "account_signup" as signup_url %}
        <c-button href="{{ signup_url }}">Sign up</c-button>
    {% endif %}
</div>
```
Rendered by `header_bar.html` (`freedom_ls/base/templates/partials/header_bar.html:22`) for every
anonymous page view, so both buttons are visible on the login page itself (in the header), not just
on the course page. `allow_signups` comes from the context processor described in §3. Both buttons
are equally weighted `<c-button>`s — Login is not visually more prominent than Sign up in the header.
Note: an in-flight worktree change (untracked in git status, same idea folder) may already be
touching this file — check current working-tree diff before editing.

## 2. What the login page renders today

- **`account/login.html` is NOT overridden anywhere in the project.** `Glob` for
  `**/templates/account/login.html` found only allauth's own template
  (`.venv/lib/python3.13/site-packages/allauth/templates/account/login.html`). No project-level
  override exists in `freedom_ls/base/templates/`, no per-theme override, nothing.
- Allauth's default login template (read in full) already puts a signup nudge **above the form**:
  > "If you have not created an account yet, then please **sign up** first." (the "sign up" text is
  the `signup_url` link, `next`-aware per §1). It also has a `{% element h1 %}Sign In{% endelement %}`
  heading and, if enabled, passkey/login-by-code buttons. There is no other visual emphasis (no
  color, no button, no repetition) pointing at signup — it's a single sentence of body text before
  the form.
- **`account/signup.html` IS overridden**: `freedom_ls/base/templates/account/signup.html`. It also
  puts "Already have an account? Then please **sign in**." above the form, styled identically
  (`text-primary underline` link). It additionally renders `SiteAwareSignupForm`'s
  `accept_terms`/`accept_privacy` checkboxes, an honeypot field (invisible), and (if enabled)
  passkey-signup / social-account buttons.
- Both `login.html` (allauth default) and `signup.html` (project override) extend
  `account/base_entrance.html`, which is **not overridden** either — only allauth's own copy exists.
  So the "entrance" chrome (page shell around login/signup) is 100% allauth stock; FLS's only
  customisation is the signup form template itself, for the terms/privacy checkboxes.
- **Theming/template-shadowing mechanism**: `freedom_ls/themes/` (`default/`, `first_class/`) each
  ship a `theme.md` + a single `theme.css` file (CSS custom properties / Tailwind tokens) — themes in
  this codebase are **CSS-only**, not a template-override mechanism. Template overrides work via
  ordinary Django `TEMPLATES` app-dirs precedence: `freedom_ls/base/templates/account/signup.html`
  shadows allauth's `account/signup.html` because `base` is an installed app whose templates dir is
  searched before allauth's. There is no separate "themes app" template-shadowing layer to know
  about beyond that.
- `django-allauth`'s `{% element %}`/`{% slot %}` tags (`ds:allauth`/allauth's own "elements"
  templating) drive the button styling (`tags="prominent,signup"` etc.) — the visual weight of the
  "Sign Up" button on the signup page and the "Sign In" button on the login page comes from that
  `prominent` tag, standard on both. Neither page's *own* CTA button is styled less prominently than
  the other's; it's the **cross-links** (sign up from login, sign in from signup) that are plain body
  text, not buttons.

## 3. Signup gating

- `freedom_ls/accounts/allauth_account_adapter.py:161-186` — `AccountAdapter.is_open_for_signup`:
  looks up `SiteSignupPolicy._base_manager.get(site=current_site)`; if found, returns
  `policy.allow_signups`; if no per-site row, falls back to `config.ALLOW_SIGN_UPS`
  (`freedom_ls/accounts/config.py`, default `True`).
- `SiteSignupPolicy` (`freedom_ls/accounts/models.py:141-162`): `allow_signups` (bool, default
  True), `require_name`, `require_terms_acceptance`, `additional_registration_forms` (JSONField).
  One row per site (`unique_signup_policy_per_site`). Effective-value helpers live in
  `freedom_ls/accounts/utils.py:90-107` (`get_effective_require_name`,
  `get_effective_require_terms_acceptance`, `get_effective_additional_registration_forms`) — always
  go through these, never re-derive the fallback inline (per
  `claude_plugins/fls-dev/skills/registration/SKILL.md`).
- `signup_policy` context processor (`freedom_ls/accounts/context_processors.py`) exposes
  `allow_signups` to every template by calling `get_adapter(request).is_open_for_signup(request)` —
  this is what `login_prompt.html`'s `{% if allow_signups %}` reads. **When signups are closed for a
  site, the header's Sign-up button simply does not render** (no explanatory message, no disabled
  state) — only "Login" shows. Allauth's own signup view (`account_signup`) would also refuse to
  render/accept a POST when closed (`is_open_for_signup` gates it internally), but there is no
  FLS-authored "signups are closed" messaging anywhere found in this pass.
- Relevant `ACCOUNT_*` settings (`config/settings_base.py:404-441`):
  - `ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*", "first_name*", "last_name"]`
  - `ACCOUNT_LOGIN_METHODS = {"email"}` — email only, no username.
  - `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`, `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True`.
  - `ACCOUNT_ADAPTER = "freedom_ls.accounts.allauth_account_adapter.AccountAdapter"`.
  - `ACCOUNT_FORMS = {"signup": "freedom_ls.accounts.forms.SiteAwareSignupForm"}`.
  - `ACCOUNT_PREVENT_ENUMERATION = True` — **login/reset responses never reveal whether an email
    has an account.** This is the setting that makes "tell the user their email isn't registered"
    structurally hard on the login form itself: a login attempt with an unregistered email gets the
    same generic "incorrect email or password" as a wrong password for a real account. Any UI change
    that tries to say "you don't have an account, sign up instead" directly from the login form's
    error path would need to either violate this enumeration protection or use a different signal
    (e.g. always-present signup nudge, not a conditional one keyed on email existence).
  - `ACCOUNT_RATE_LIMITS = {"signup": "5/m/ip", "login_failed": "10/m/ip,5/5m/key"}`.
- `SiteAwareSignupForm` (`freedom_ls/accounts/forms.py:38-171`): adds `first_name`/`last_name`,
  honeypot `_hp`, conditionally required `accept_terms`/`accept_privacy` checkboxes (only if the
  site's policy requires them **and** the relevant `legal_docs/` doc resolves), and
  `custom_signup()` which writes `LegalConsent` rows. No behaviour here relates to prior
  login attempts or intended destination beyond the standard `next` passthrough.
- Post-verification: `RegistrationCompletionMiddleware`
  (`freedom_ls/accounts/middleware.py`) forces any authenticated, non-superuser user with incomplete
  `additional_registration_forms` to `accounts:complete_registration`
  (`freedom_ls/accounts/views.py:76-113`) before anything else — see
  `claude_plugins/fls-dev/skills/registration/SKILL.md` for the full `RegistrationFormProtocol`
  contract (`applies_to`/`is_complete`/`save`, forbidden `user`/`user_id`/`email` field names).
  Irrelevant to a visitor who has no account yet, but relevant if any fix inserts a step between
  signup and reaching the apply/enrol destination.
- `docs/product/authentication.md` is the canonical prose description of all of the above
  ("Registration", "Security Hardening" sections) — cites `ALLOW_SIGN_UPS`, `REQUIRE_NAME`,
  `REQUIRE_TERMS_ACCEPTANCE` and confirms "**Intended destination is preserved** ... through the
  whole signup flow ... This is what makes the browse-first, log-in-at-commitment flow ... work."

## 4. Existing mechanisms that capture anonymous visitor intent or emails

Searched: `course_interest`, `referral_tracking`, `google_tag`/`course_access/google_analytics.py`,
axes lockout records, allauth's `unknown_account` email.

- **`CourseInterest`** (`freedom_ls/course_interest/models.py`) — `user` (FK, required, not
  nullable), `course`, `created_at`. **Requires an authenticated `User`** — it cannot record an
  anonymous visitor's email or an unresolved sign-in attempt. The anonymous branch of
  `partial_express_interest` (`course_interest/views.py:53-59`) stashes only the `course_slug` in
  the **session** (`_PENDING_INTEREST_SESSION_KEY`) to survive the login round-trip; nothing is
  persisted to the DB until the user actually authenticates. Not usable as-is for "capture the email
  of someone who tried and gave up," because giving up means never authenticating, so no `User`
  row and no session-backed record survives past the session's life (and nothing keys it to an
  email at all — only a course slug).
- **`CourseApplication`** (`freedom_ls/course_applications/models.py`) — same shape: `user` FK
  required, created only post-login via `_start_application`. No anonymous/unauthenticated
  half-formed record exists.
- **GA4 events** (`freedom_ls/course_access/google_analytics.py`): `record_interest_expressed`,
  `record_application_submitted`, `record_course_self_registered`, `record_course_started`,
  `record_course_completed` all fire `COURSE_ACCESS_REQUESTED`/`COURSE_REGISTERED`/etc **after**
  the action succeeds — i.e. after the user is authenticated and the row is created. None of them
  fire at the "clicked Apply but had to log in" moment, and none carry the visitor's email (GA4
  events are pseudonymous by client ID, not email). So GA4 cannot currently answer "who tried to
  apply and gave up," only "how many app starts happened" for people who got through.
- **`referral_tracking`** (`freedom_ls/referral_tracking/`) — per
  `docs/product/signup-attribution.md`, this captures **first-touch landing attribution**
  (UTM/ad-click/referral-code + IP/UA) tied to a signup, written only "submitting the signup form."
  It has nothing about login attempts, and nothing about intended action (apply vs. enrol vs. browse)
  — it's channel attribution, not intent capture. Not a fit for "what they were trying to do."
- **django-axes** (`AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1` hour,
  `AXES_LOCKOUT_TEMPLATE = "accounts/lockout.html"`, `config/settings_base.py:326-349`) —
  axes' `AccessAttempt`/`AccessLog` tables (not project models; library-owned) record the
  **username tried** (here, the submitted email string, whether or not an account exists), IP, and
  timestamp, for every failed login. **This is the closest existing thing to "captured the email of
  someone who tried to sign in without an account"** — axes logs the attempted identifier
  irrespective of whether it resolves to a real account. But: (a) it has no notion of "what they
  were trying to do" (no `next`/intended-destination field on axes' models), (b) it is a
  security/lockout log, not a lead-capture list, with no admin UI built for "follow up with this
  person" workflows in this codebase, and (c) because `ACCOUNT_PREVENT_ENUMERATION=True`, a login
  attempt with an unregistered email fails the same way as a wrong password, so axes cannot itself
  distinguish "no such account" from "wrong password" without querying `User` by email separately.
- **allauth `unknown_account` email** (`freedom_ls/accounts/templates/account/email/
  unknown_account_message.txt` / `_subject.txt`) — this fires on the **password-reset** flow when
  someone requests a reset for an email with no account: "no account with this email address
  exists ... If this was you, you can create an account instead. Create an Account: {{
  signup_url }}". This is allauth's own dead-end nudge for the *forgot password* path, not the
  *login* path — because `ACCOUNT_PREVENT_ENUMERATION` deliberately keeps plain login silent about
  unknown emails, this reset-flow email is the **one place in the codebase where FLS already tells
  someone "you don't have an account, sign up" by email**, but only if they go through "forgot
  password," not from repeatedly failing at the login form itself. It records nothing server-side
  (no model row) — it's a one-shot email, no persisted lead.
- **Conclusion for §4**: nothing in the codebase today persists "an anonymous email address that
  tried to sign in, plus what they were trying to do." The closest primitives are (a) axes' attempt
  log (email, but no intent, and not built for follow-up), and (b) the session-only
  `_PENDING_INTEREST_SESSION_KEY` pattern (intent, but no email, and ephemeral). A new feature to
  "capture email + intended action for failed sign-in" would be new model/view work, not a rewire of
  something existing — though the `redirect_to_auth`/`next_url` plumbing already carries "what they
  were trying to do" as a URL at the moment of redirect (before the login form is even shown), which
  is the one existing signal a new capture feature could hook into.

## 5. Existing product docs on signup/login/applications

- `docs/product/authentication.md` — canonical registration/login/security description (see §3).
- `docs/product/signup-attribution.md` — first-touch channel attribution on signup (see §4);
  explicitly notes "A signup with no tracked landing records as 'direct' / 'none'" and lists
  **Not Built**: no consent gate, no dashboard, no bot filtering, no retention tooling. No mention
  of course applications or login-page conversion at all.
- `docs/product/learner-experience.md` — referenced by authentication.md as owning the
  "browse-first, log-in-at-commitment" flow description; not read in full this pass but named as
  the doc to check for how the acquisition funnel (browse → CTA → login/signup → destination) is
  meant to feel from the learner's side.
- No product doc specifically addresses course-application UX, login-vs-signup routing, or
  give-up/bounce behaviour on the login form — this appears to be genuinely undocumented territory,
  consistent with the idea being a new problem to solve rather than a documented gap.
- Related engineering history worth reading before designing a fix (all in `spec_dd/3. done/`):
  `2026-07-17_09:12_bugfix-shitty-allauth-decisions/idea.md` (explicit warning against re-adding
  custom next-threading machinery — "vanilla `@login_required` + allauth already handle the
  redirect perfectly well"), `2026-09-01_17:04_bug-interested-login-405/2. plan.md` (the
  `redirect_to_auth`/GET-safe-landing-view pattern used for course_interest), and
  `2026-09-18_14:10_bug-authentication-next-target-sometimes-lost/` (the `url_with_next` tag and
  its test suite, `test_header_auth_links_carry_next.py`).

## Domain vocabulary used above

Per `.claude/skills/domain-glossary/SKILL.md` and the model names read: **application** =
`CourseApplication` (`course_applications/models.py`); **course interest** = `CourseInterest`
(`course_interest/models.py`) — "learner's expressed interest in a coming-soon course"; **learner**
= `Learner` (the per-organisation association row) — note that a not-yet-registered `User` clicking
Apply/Enrol is *not yet* a `Learner` at all, only a `User`, until `ensure_learner` runs; **signup** /
**login** are not model-backed terms — they are allauth's own vocabulary (`account_signup`,
`account_login` URL names) and this codebase does not rename them.

status: ok
