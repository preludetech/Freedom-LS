# Suspect specs review

Scope: determine what each of the two suspect specs changed, and how plausible each change is
as the cause of: unauthenticated user clicks "enrol for free" → routed to login/signup →
signs up with an email **already on the system** → receives a password-reset email (allauth
`ACCOUNT_PREVENT_ENUMERATION`) → resets password → gets stuck in an email-verification loop.

All paths below are relative to the project root
`/home/sheena/workspace/lms/freedom-ls-worktrees/bugfix_authentication_email_verify_loop`.

---

## 1. Spec: `2026-07-01_19:44_home_page` ("Public browsing for unauthenticated users")

### What it changed

Source: `spec_dd/3. done/2026-07-01_19:44_home_page/{idea.md,1. spec.md,2. plan.md}`.

This spec is the one that **created the entire unauthenticated → CTA → login/signup → intent
survives** journey the bug report describes. Concretely, per its plan:

- **Made three surfaces public** by removing `@login_required`: `student_interface.dashboard`
  (`/`), `student_interface.all_courses` (`/courses/`), `student_interface.course_detail`
  (`/courses/<slug>/detail/`) — Phases 2–4.
- **Added the "Enrol for free" / "Apply now" CTA wording and made the CTA URL backend-owned**
  (`course_access/backends.py`, `FreeOnlyCourseAccessBackend.get_access`, Phase 1.1). The
  not-registered CTA renders as `<c-button href="{{ start_url }}">` in
  `student_interface/templates/student_interface/course_detail.html` (currently the CTA block
  at lines ~144–148, confirmed by direct read of the current file). Because
  `initiate_course_access` (`student_interface/views.py:451`) is `@login_required`, an
  anonymous click auto-generates a `?next=<that-url>` redirect into Django's login flow — this
  is the **exact mechanism** an anonymous "enrol for free" click uses to reach
  `/accounts/login/` and from there `/accounts/signup/`.
- **Header Login/Sign-up links now carry `?next=<current-page-path>`**
  (`partials/login_prompt.html`, Phase 2.3) — another route into signup with a meaningful
  `next`.
- **Threaded `next` through the new-user signup path end-to-end (spec §4.3, plan Phase 5.2)** —
  this is the change with the most direct bearing on the bug:
  - `freedom_ls/accounts/middleware.py` (`RegistrationCompletionMiddleware.__call__`,
    lines 118–134) was changed so that when it force-redirects an authenticated user with
    incomplete registration forms to `accounts:complete_registration`, it now **preserves**
    `next` — reading `request.GET.get("next")` (validated with
    `url_has_allowed_host_and_scheme`) or falling back to `request.path`, and appends it as
    `?next=<candidate>` on the redirect target (lines 123–134). Before this spec the redirect
    dropped `next` entirely (per the spec's own description of the "critical gap", §4.3).
  - This middleware runs on **every authenticated request** except an explicit exempt list
    (`EXEMPT_URL_NAMES`, `middleware.py:32-48` — includes `account_login`, `account_signup`,
    `account_email_verification_sent`, `account_confirm_email`, `account_reset_password`,
    `account_reset_password_done`, `account_reset_password_from_key`,
    `account_reset_password_from_key_done`, `accounts:complete_registration`, plus
    static/media prefixes). This exempt list itself predates this spec (added by
    `spec_dd/3. done/2026-05-05_08:18_better-registration/`) — this spec only added the
    `next`-preservation *behaviour* on top of the existing exempt-list mechanism.
- **`accounts/views.py`** (`_safe_post_completion_redirect`, `complete_registration_view`) —
  pre-existing (from `better-registration`), not changed by this spec's plan beyond
  verification; the spec explicitly says the view "already read and re-emit `next`" and only
  the middleware needed a fix (spec §4.3).
- SEO/sitemap/robots.txt work (Phase 6) — unrelated to auth.

### Cross-reference to the auth/enrolment flow — concrete mechanism

This spec is the one that made the **existing-email-at-signup path reachable through the
course-enrolment CTA** in the first place:

1. Before this spec, `student_interface` views were all `@login_required`, so an anonymous
   visitor could not reach a course-detail CTA at all — the login wall came first, with no
   course-specific `next` in play, and the header showed no Login/Sign-up affordance to
   anonymous users (`header_bar.html` hid the whole `<nav>` behind
   `{% if user.is_authenticated %}` before this spec, per spec §1 "Header" and plan §2.3).
2. After this spec, "enrol for free" on any published free course is the **primary, advertised
   route** into signup for a never-before-seen or forgotten-account visitor, and it always
   carries a `next` pointing at `courses/<slug>/access/` (`initiate_course_access`). A returning
   user who forgot they already have an account — or simply mistypes/reuses an email that
   collides with an existing account — is now funnelled into `account_signup?next=…` far more
   often than before.
3. Allauth's `ACCOUNT_PREVENT_ENUMERATION = True` (`config/settings_base.py:345`, pre-existing,
   **not modified by this spec**) means a signup POST with an already-registered email does
   **not** surface a "this email is taken" error. It instead proceeds as if the signup
   succeeded (same "check your email" landing) while, server-side, allauth sends a different
   email to the existing address — for a verified account this is effectively a password-reset
   invite. This is standard allauth enumeration-prevention behaviour and is **not new**; what is
   new is that this spec makes it *reachable from the enrolment CTA with a live `next`
   attached*.
4. The `next` value that was attached to the *original* signup POST (from the CTA click) is a
   **hidden form field on the signup form** — the project's `account/signup.html`
   (`freedom_ls/base/templates/account/signup.html`) retains the `redirect_field` per spec §4.3
   / plan Phase 5.1. But allauth's enumeration-prevention branch does not perform a normal
   signup-success redirect that would consume that hidden field — it just renders the generic
   "verification email sent" page. The password-reset email the *existing* account receives is
   generated by an entirely separate allauth code path
   (`allauth/account/internal/flows/signup.py: send_unknown_account_mail` →
   password-reset email) that has **no knowledge of the `next` the visitor typed into the
   signup form** minutes/hours earlier. So the course-enrolment intent (`next=…/access/`) is
   **silently dropped** at the exact moment enumeration prevention kicks in — the user later
   clicks a password-reset link from their inbox (a fresh, unrelated GET request, likely in a
   different browser tab) that carries no `next` at all.
5. On completing the password reset, `ACCOUNT_LOGIN_ON_PASSWORD_RESET = True`
   (`config/settings_base.py:340`, pre-existing) drives allauth's `perform_password_reset_login`
   → `perform_login` → `LoginStageController`, which (by default) still re-runs the
   **mandatory email-verification stage** (`ACCOUNT_EMAIL_VERIFICATION = "mandatory"`,
   `config/settings_base.py:338`) for the `Login` object, because
   `perform_password_reset_login` does not pass an override for `email_verification` (allauth
   `internal/flows/password_reset.py:22-35`, confirmed by direct read). If the pre-existing
   account's `EmailAddress.verified` is not `True` at that point (e.g. a stale/incomplete prior
   signup, or any state where the account exists but was never confirmed), the login is
   **not** completed as a full Django-authenticated session — the user is bounced back into
   the email-verification flow instead. If the user then re-attempts sign-in/verification with
   the same "next"-carrying links from the *original* signup attempt still open in a tab, or if
   any cached/incomplete `RegistrationCompletionMiddleware` session state
   (`CACHE_SESSION_KEY`, `middleware.py:73,156-169`) or the `next`-preservation logic added by
   this spec interacts with an account stuck mid-verification, the visible symptom is a
   repeating bounce between "verify your email" and the originally-intended destination —
   i.e. the reported "email-verification loop". **This exact mechanical chain (steps 4–5)
   needs runtime reproduction to pin down precisely which redirect closes the loop** — that is
   a fix-phase task, not something this research file resolves — but every component in the
   chain up to and including "the visitor reaches signup-with-existing-email via the CTA with a
   `next` that then gets dropped" is a direct, traceable consequence of this spec's changes.
6. Separately, and more directly implicating this spec's own new code: the
   `RegistrationCompletionMiddleware` fix (`accounts/middleware.py:118-134`) now re-attaches
   `next` to **every** forced redirect to `complete_registration` for **any** authenticated
   user with incomplete registration forms, using `request.GET.get("next") or request.path`
   with no loop/repeat-visit guard beyond the existing session cache
   (`_is_complete_cached`/`_mark_complete`, lines 156-169). If a user in the middle of the
   existing-email/password-reset chain becomes authenticated in a state the middleware
   considers "incomplete" (e.g. additional registration forms not yet satisfied for what the
   middleware believes is a *new* signup, when in fact it is a *pre-existing* account), the
   `next` value keeps being carried and reattached across repeated visits to the same
   destination, so if that destination itself keeps failing to complete (e.g. because of the
   mandatory-verification interaction in step 5), the loop is **stable and repeating** rather
   than failing loudly — which matches "stuck in a loop" rather than "gets an error".

### Files/areas most implicated

- `freedom_ls/accounts/middleware.py` — `RegistrationCompletionMiddleware.__call__`
  (lines 85-134), specifically the `next`-preservation logic added by this spec
  (lines 118-134).
- `freedom_ls/student_interface/templates/student_interface/course_detail.html` — CTA anchor
  (`~144-148`), the entry point for the deferred-login `next`.
- `freedom_ls/student_interface/partials/` / `partials/login_prompt.html` — header
  Login/Sign-up `next` threading (Phase 2.3).
- `freedom_ls/base/templates/account/signup.html` — the project's overridden signup template,
  confirmed to retain `redirect_field` (hidden `next` field) per this spec's Phase 5.1.
- `freedom_ls/student_interface/views.py:451` (`initiate_course_access`) — `@login_required`
  chokepoint that generates the `?next=` for anonymous clicks.

---

## 2. Spec: `2026-07-03_07:52_courses_coming_soon` ("Coming Soon & Hidden Courses")

### What it changed

Source: `spec_dd/3. done/2026-07-03_07:52_courses_coming_soon/{idea.md,1. spec.md,2. plan.md}`.

- New `visibility` field + `CourseVisibility` enum on `Course`
  (`content_engine/models.py`, new migration).
- New `course_interest` app (`freedom_ls/course_interest/`) with `CourseInterest` model,
  `express_interest`/`remove_interest` HTMX POST views, and a shared CTA partial.
- New `VisibilityEnforcingBackend` wrapper applied at `course_access/loader.py`'s
  `get_course_access_backend()` (Phase 2.2) — wraps the configured backend to short-circuit
  `get_access()`/`filter_visible()` for `coming_soon`/`hidden` courses.
- `student_interface/views.py`: `course_detail` gains a hidden-course 404 check
  (`raise_404_if_hidden_unregistered`) and stamps `is_interested`/`is_coming_soon` for the
  coming-soon branch; `initiate_course_access` (`views.py:452-470`) gained a visibility check
  (`raise_404_if_hidden_unregistered`, and a `coming_soon` → redirect-to-detail branch) ahead of
  the existing access-backend logic.
- `course_detail.html` CTA block gained an `{% if is_coming_soon and not is_registered %}`
  branch (confirmed by direct read, lines 138-148) that renders the express-interest HTMX
  partial instead of the generic CTA anchor — **only for `coming_soon` courses**. The
  `{% else %}` branch (published/free/gated/registered) is **byte-for-byte the same CTA anchor**
  this spec's own plan describes as pre-existing (`<c-button href="{{ start_url }}">`).
- Educator course-list visibility column + interest-count/drill-down
  (`educator_interface/views.py`).
- Content-import schema addition (`content_engine/schema.py`).

None of this touches `accounts/`, `allauth`, login, signup, `RegistrationCompletionMiddleware`,
or any settings under `ACCOUNT_*`. The plan's own skill-map explicitly states:

> "Not relevant: `fls:registration` (no sign-up / consent changes)..." (plan.md, "Skill & MCP
> map" section).

### Cross-reference to the auth/enrolment flow — concrete mechanism

For a **published, free course** — the scenario in the bug report ("enrol for free") — this
spec changes nothing about the CTA, its target URL, or the deferred-login mechanics:

- `VisibilityEnforcingBackend.get_access()` (`course_access/backends.py`, per plan §5.1/Task
  2.2) delegates unchanged to the inner backend for `published` courses — the free CTA
  (`cta_label`, `cta_url`) is identical to before this spec.
- `initiate_course_access`'s new visibility checks (`raise_404_if_hidden_unregistered`, the
  `COMING_SOON` branch) are both **no-ops for a `published` course** — they only change
  behaviour for `hidden`/`coming_soon` courses.
- The CTA template branch this spec added is gated on `is_coming_soon`, which is `False` for a
  published free course, so the `{% else %}` (original) CTA anchor renders exactly as before.

The only way this spec could plausibly interact with the reported bug is if the affected course
were mis-tagged `coming_soon` (in which case the user would never see an "enrol for free" CTA at
all — they'd see "I'm interested", contradicting the bug report) or if the `functools.cache`d
loader wrapper (`get_course_access_backend()`) somehow returned a stale/incorrect backend
instance across requests — but that would produce wrong **course-access** decisions, not an
**authentication/email-verification** loop, and there is no code path from
`VisibilityEnforcingBackend` into `accounts`, allauth, or the middleware.

**Conclusion: this spec is not a plausible source of the reported bug.** It is implicated only
in the trivial, ruled-out sense that it touched the same CTA template block and the same
`course_access` module used by the enrolment journey.

---

## 3. Ranked list of most likely regression sources

1. **`freedom_ls/accounts/middleware.py:118-134`** (spec 1, Phase 5.2 / spec §4.3) — the
   `next`-preservation fix on `RegistrationCompletionMiddleware`'s forced redirect. This is new
   logic (not present before spec 1) that runs on every authenticated request for a user with
   incomplete registration forms, re-attaching a validated `next` on each pass. Most concrete,
   spec-1-owned candidate for turning a one-time misroute into a **repeating** loop.
2. **The new anonymous-CTA-into-signup entry point as a whole** (spec 1, Phases 2–5:
   `course_detail.html` CTA, `login_prompt.html` header `next`, `initiate_course_access`
   `@login_required`) — this is what makes "unauthenticated visitor signs up with an
   already-registered email via the enrol CTA" a common, reachable journey for the first time.
   Before spec 1 this journey required a visitor to already be on the login/signup page with no
   course-specific `next` (a much less common entry point, and one that predates the bug being
   noticed).
3. **Interaction between `ACCOUNT_LOGIN_ON_PASSWORD_RESET` + `ACCOUNT_EMAIL_VERIFICATION =
   "mandatory"` + `ACCOUNT_PREVENT_ENUMERATION`** (`config/settings_base.py:338-345`) — all
   **pre-existing**, unmodified by either suspect spec (confirmed: neither plan.md touches
   `settings_base.py` `ACCOUNT_*` keys; only `INSTALLED_APPS` additions). This is the
   allauth-level condition that can leave a user "authenticated by password reset but not
   verified", which is where an email-verification loop would actually originate at the
   allauth layer. Flagged here because it is necessary context for the fix, but it is **not
   attributable to either suspect spec** — it is exposed/reached by spec 1's new journey, not
   created by it.
4. **`courses_coming_soon` (spec 2) — ruled out** for the free-course CTA path (see §2 above).
   Kept in the list only to record that it was checked and found not implicated.

---

## 4. Why the SDD process didn't catch this — QA gaps

### Spec 1 (`home_page`) frontend QA

`spec_dd/3. done/2026-07-01_19:44_home_page/3. frontend_qa.md` and `qa_report.md` define/exercise
10 workflows. Relevant to this bug:

- **Workflow 5 ("Deferred login: free enrol completes intent")** and **Workflow 7 ("New-user
  signup that must complete registration forms")** are the closest scenarios to the bug, but
  both explicitly use **"a fresh, never-used email"** (`frontend_qa.md` line 35: "New signups:
  use a fresh, never-used email each time"; qa_report.md line 173: fresh email
  `qa-newuser-wf7@email.com`). **No workflow signs up with an email that already has an
  account.**
- **Workflow 8 ("Open-redirect rejection")** tests an off-host `next` value, not the
  enumeration-prevention path.
- The QA report's own "Notes on execution" section confirms: *"Email verification is mandatory
  in dev; verification links were retrieved from Mailpit... All verification links used the
  correct host"* — i.e. QA only exercised the **happy-path, single, correct** verification link
  per signup, never a signup attempt against a **pre-existing** account, and never the
  password-reset-via-enumeration-prevention branch at all.
- **Gap:** the spec's own §4.3 ("critical") and the plan's Phase 5.3 test list enumerate
  "Free deferred-login (signup)", "Apply deferred-login (login + signup)", "New-user +
  registration-forms `next` survival", and "Open-redirect rejection" as the required automated
  tests — **none of these test cases covers signing up with an email already registered to an
  existing account**, i.e. the exact allauth `ACCOUNT_PREVENT_ENUMERATION` branch this bug
  travels through. Neither the spec's success criteria (§8) nor its test list (Phase 5.3) name
  this scenario at all — it was never in scope for this spec's own QA plan, automated or
  manual, despite the spec substantially reworking how `next` survives the signup path.

### Spec 2 (`courses_coming_soon`) frontend QA

`spec_dd/3. done/2026-07-03_07:52_courses_coming_soon/3. frontend_qa.md` covers coming-soon
discoverability, the express-interest HTMX flow, hidden-course 404s, and educator drill-downs.
It does not touch login/signup/email-verification at all (consistent with §2 above — this spec
never claims to, and its own plan explicitly marks `fls:registration` as not relevant). There is
no QA gap to note here specific to this bug, because this spec's scope never included the
auth/signup flow.

### Overall process gap

The review/QA step that should have caught this is a **cross-cutting "existing account tries to
sign up again" regression check** — specifically through the *new* CTA-driven entry point spec 1
built. Because `ACCOUNT_PREVENT_ENUMERATION` and mandatory email verification are project-wide
allauth settings that predate spec 1 (added by
`spec_dd/3. done/2026-05-05_08:18_better-registration/`, whose own `threat_model.md` flags
"V7.3 Email enumeration on signup" as **already a known, pre-existing concern**, and separately
warns "password-reset URLs must be exempt" from the completion-middleware, line 41-42/134/173 of
that threat model), a spec that materially changes how anonymous visitors are funnelled into
signup (spec 1) should have re-run that pre-flagged enumeration-prevention scenario end-to-end
through the new CTA path as a regression check. It did not — its QA plan (manual workflows and
the automated test list in the plan) only ever used fresh, unused emails for every signup
scenario, so the one path that combines "new CTA-driven signup entry" with "the project's known,
pre-existing enumeration-prevention branch" was never exercised by either spec's QA.

---

status: ok
