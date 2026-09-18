# Research: which events to send to GA4, and how

Scope note: this covers *which events* and *by what mechanism*. The base `gtag.js` integration
(measurement-ID setting, page views) is a separate worker's output; this file assumes it exists and
that "no measurement ID → nothing is sent" is already the pattern (mirroring `POSTHOG_API_KEY`, see
`freedom_ls/deployment/config.py:24-28` and `freedom_ls/base/templates/_base.html:84-93`).

## 1. GA4 recommended events relevant to FLS's funnel

GA4's recommended-events catalogue defines fixed names and parameters that unlock standard reports
([Google: recommended events](https://developers.google.com/analytics/devguides/collection/ga4/reference/events),
[Analytics Help: recommended events](https://support.google.com/analytics/answer/9267735?hl=en)):

| GA4 event | Standard parameters | Relevance to FLS |
| --- | --- | --- |
| `sign_up` | `method` (string, e.g. registration channel) | Account creation. Direct fit. |
| `login` | `method` | Direct fit, but see §3 — FLS fires no webhook on login today, and allauth's login view is a plain server render with no natural "fire once" hook without extra code. |
| `generate_lead` | `currency`, `value` (both optional/typically omitted for a non-monetised lead) | Best fit for a course application or an expression of interest — GA's own docs pitch this event for "a user submits a form to receive information" or similar, which is exactly `CourseApplication` and `CourseInterest`. |
| `tutorial_begin` / `tutorial_complete` | none required | Intended for app onboarding, but the funnel shape (begin → complete) maps cleanly onto **course start** and **course completion** if FLS chooses to reuse it rather than treat a course as a "tutorial" in the copy sense. Given `docs/product` already avoids "curriculum"/"course" ambiguity, treat this as a GA4 *event name* borrowed for its funnel shape, not a claim that FLS calls a course a tutorial. |
| `begin_checkout` / `purchase` | `currency`, `value`, `items[]` | **Not applicable today.** `spec_dd/2. in progress/course-prices/idea.md` is display-only — "Payment processing is out of scope, we just need to show you the prices for now." There is no checkout flow anywhere in the codebase to instrument. Do not build this now; note it for when payment processing ships. |

Google's general guidance: implement recommended events with their exact names/parameters to get
standard reports "for free," rather than inventing custom event names for the same concepts
([Google: recommended events](https://developers.google.com/analytics/devguides/collection/ga4/reference/events)).

## 2. FLS's actual flows, mapped to candidate events

| Flow | FLS model / vocabulary | Where it happens | Request shape | Candidate GA4 event |
| --- | --- | --- | --- | --- |
| Account creation | `User` (allauth) | `AccountAdapter.save_user()`, `freedom_ls/accounts/allauth_account_adapter.py:126-146` — fires `fire_webhook_event("user.registered", ...)` inline, `commit=True` branch | Full-page POST (allauth signup form) + redirect | `sign_up` |
| Email verification | allauth `EmailAddress` confirm | Not investigated in depth; no existing webhook event or FLS hook found for it | Full-page GET (confirmation link) | Not recommended for v1 — no existing signal to hang off, and it duplicates `sign_up` intent for most flows. |
| Login | `User` via allauth | No FLS-side hook found (no `user.logged_in` webhook event; `FLS_WEBHOOK_EVENT_TYPES` has only 3 entries — `freedom_ls/base/webhook_event_types.py:1-5`) | Full-page POST + redirect | `login` — lowest priority; would need a **new** hook (e.g. `user_logged_in` signal receiver, the same signal `referral_tracking`'s planned login-flush uses per `spec_dd/1. next/referral-attribution-over-time/1. spec.md` §"Login") |
| Course application (application-gated course, no form) | `CourseApplication` | `_start_application()`, `freedom_ls/course_applications/views.py:37-54`; row creation **is** the submission (`CourseApplication.is_submitted`, `models.py:72-83`) | Full-page GET (CTA is a plain link) → `get_or_create` → redirect | `generate_lead` |
| Course application (with an application form) | `CourseApplication` + `FormProgress` | Started at `_start_application` (draft); true submission is `form_progress.complete()` inside `application_check_answers`, `freedom_ls/course_applications/views.py:236-249` | Full-page POST (check-your-answers page) + redirect | `generate_lead`, fired at **submission** (`complete()`), not at draft-start — draft-start is "began an application," not a lead |
| Expression of interest (coming-soon course) | `CourseInterest` | `partial_express_interest` (`freedom_ls/course_interest/views.py:58` per referral-attribution research) and `deferred_express_interest` (`:116`) | **HTMX** partial (`partial_express_interest` is a partial view; the deferred variant follows an auth detour) | `generate_lead` — a softer lead than an application, may warrant its own custom-event name instead of overloading `generate_lead`, see §6 |
| Course registration / course start | `LearnerCourseRegistration` | Self-service: `initiate_course_access`, `freedom_ls/learner_interface/views.py:811-875`, `update_or_create` on the `created` branch; announced via `_ensure_and_announce` → `fire_webhook_event("course.registered", ...)`, `freedom_ls/learner_progress/signals.py:122-154`, connected off `post_save` on `LearnerCourseRegistration` (also fires for cohort-driven registration fan-out, `signals.py:157+`) | Full-page POST (self-registration button) + redirect for the learner path; Django admin for staff-driven registration (also fires the same webhook, i.e. it does **not** distinguish learner- vs staff-initiated — see the "in play" caveat in the referral-attribution spec, which treats admin-driven registration as *not* learner-initiated for its own purposes) | `tutorial_begin` (borrowed name) — but see caveat below |
| First content access (arguably the "real" course start) | `CourseProgress.started_at` | Stamped once, on first topic/form view, in `view_course_item`, `freedom_ls/learner_interface/views.py:1013-1021` (`if course_progress.started_at is None: course_progress.started_at = now`) | Full-page GET, `login_required` | Alternative candidate for `tutorial_begin` — registration and first-access are two different moments (`created_at` vs `started_at` on `CourseProgress`, per the domain glossary) and only one should be chosen for v1 (see §6) |
| Topic / activity read | `TopicProgress` | Recorded per placement in the player; not investigated at the same depth here | HTMX/full-page, per-item | Not recommended for v1 — too granular, no existing FLS-side aggregation signal, high volume |
| Form (quiz) submission, pass/fail | `FormProgress`, `CourseFormAttempt` | `form_attempt_completed` signal → `recalculate_course_progress_on_form_attempt`, `freedom_ls/learner_progress/signals.py:96-119`; no webhook event exists for this today | Player submission (form pages), shape not fully traced here | Not recommended for v1 — no existing webhook precedent, and per-quiz volume is high; a `level_up`/custom event could follow once course start/finish are proven out |
| Course completion | `CourseProgress.completed_time` | `course_finish` view, `freedom_ls/learner_interface/views.py:1595-1636` — sets `completed_time` and fires `fire_webhook_event("course.completed", ...)` **in the same branch**, deliberately: "the stamp and the webhook share this branch deliberately: an announced completion cannot be taken back, so neither may happen without the other" (comment at `views.py:1613-1615`) | Full-page GET (learner navigates to the finish URL), `login_required` | `tutorial_complete` (borrowed name) |

## 3. Client-side vs server-side (Measurement Protocol), and the webhook system as a source

**Client-side (`gtag('event', ...)` in the rendered response).**
- Pros: no server secret to manage; reuses `_ga`'s own `client_id`/session automatically, so the event
  joins cleanly to the same visit that will show up in GA4's session/traffic-source reports; simplest
  to wire onto a one-shot flag (session key or Django message set at the point of action, read and
  cleared by the next full-page render, similar to how `django.contrib.messages` already carries
  one-shot success text, e.g. `application_check_answers`'s `messages.success(...)` at
  `course_applications/views.py:240-244`).
- Cons: ad blockers and privacy extensions strip `gtag.js`/GA's endpoint outright, so any event routed
  only this way loses some fraction of real conversions
  ([RudderStack: server-side tracking](https://www.rudderstack.com/blog/how-to-overcome-ga4-server-side-tracking-challenges/)).
  It also does not fire for actions with no full-page render immediately after them — several of FLS's
  candidate events are HTMX partials or POST+redirect flows, so the "next full page" carrying the
  one-shot flag has to be chosen carefully (e.g. after `initiate_course_access`'s redirect, or after
  `application_check_answers`'s POST redirect to the dashboard).

**Server-side via GA4 Measurement Protocol.**
- Pros: fires regardless of ad blockers, from a background task or a plain view, independent of what
  the browser did; reuses `django.tasks`/`default_task_backend`, the same async-dispatch mechanism FLS
  already uses for webhooks (`freedom_ls/webhooks/events.py:35-39`), so it composes with the existing
  house pattern instead of adding a new one.
- Cons: needs a GA4 **API secret** in addition to the measurement ID (a second credential to source
  from an environment variable, per this project's "never hardcode credentials" rule); needs the
  visitor's `client_id` (the `_ga` cookie value) threaded from wherever the browser last saw it through
  to the server call, or the event lands as a disconnected session with `(not set)` attribution
  ([RudderStack: server-side tracking](https://www.rudderstack.com/blog/how-to-overcome-ga4-server-side-tracking-challenges/)).
  FLS's webhook payloads (see below) do not currently carry a `client_id` at all, so wiring this up is
  not "free" — it needs a new plumbing step (e.g. a hidden field or cookie read at the point each
  webhook-firing view runs) before Measurement Protocol calls would attribute correctly.
- The standard production compromise is hybrid: client-side for anything with a synchronous request/
  response the browser sees, Measurement Protocol as a "safety net" for actions that happen off the
  main request-response cycle (payment redirects, async confirmations)
  ([RudderStack: server-side tracking](https://www.rudderstack.com/blog/how-to-overcome-ga4-server-side-tracking-challenges/);
  [Analytico: server-side purchase accuracy](https://www.analyticodigital.com/insights/server-side-tracking-purchase-revenue-accuracy)).
  FLS has no such off-cycle action today (no payment gateway, no async webhook-confirmed purchase), so
  this hybrid's strongest argument for Measurement Protocol does not currently apply.

**FLS's own webhook/event system is directly reusable as the source of truth.**
`freedom_ls/webhooks/events.py`'s `fire_webhook_event(event_type, payload)` already does exactly the
job Measurement Protocol needs done: validate an event type, persist a `WebhookEvent` row keyed to a
site, and enqueue an async dispatch task (`freedom_ls/webhooks/events.py:10-39`). Three event types
exist today (`freedom_ls/base/webhook_event_types.py:1-5`):

- `user.registered` — fired from `AccountAdapter.save_user()`.
- `course.registered` — fired from `_ensure_and_announce()`, reacting to `post_save` on
  `LearnerCourseRegistration`/`CohortCourseRegistration`/`CohortMembership`.
- `course.completed` — fired from `course_finish()`, in the same branch as the completion stamp.

These three already cover **sign-up, course start (registration) and course finish** — three of the
four events this spec's user framing names ("course applications, course starts, new sign ups"). The
fourth, course applications, fires **no** webhook event today (confirmed independently by
`spec_dd/1. next/referral-attribution-over-time/research_attributable_events.md` §7: "`CourseApplication`
and `CourseInterest` fire no webhook event at all today").

Two ways to use this system for GA4, in increasing order of coupling:
1. **A new `WebhookEndpoint`-style consumer**, or a small dedicated subscriber, that reacts to
   `WebhookEvent` rows (or hooks the same `fire_webhook_event` call sites) and calls the Measurement
   Protocol API. This reuses the existing async dispatch, retry/circuit-breaker infrastructure
   (`WebhookDelivery`, `check_circuit_breaker`) essentially for free, but still hits the `client_id`
   problem above — none of the three payloads today carry one.
2. **Client-side only, still keyed to the same three moments**, fired from the same three call sites
   (or the templates their redirects land on) via a one-shot flag, without touching the webhook system
   at all. Lower effort, no new credential, no `client_id` plumbing, but loses events blocked by ad
   blockers or fired from a context with no next page render (none of the three current call sites
   are HTMX, so this gap does not bite yet — see the table in §2).

## 4. PostHog precedent

No custom PostHog capture calls exist anywhere in the codebase — a repo-wide search for
`posthog.capture` and `posthog\.` returns only the client library setup in
`freedom_ls/base/templates/_base.html:84-93` (`posthog.init(...)` with `defaults: '2025-11-30'`, i.e.
PostHog's own autocapture defaults) and the `POSTHOG_API_KEY`/`POSTHOG_API_HOST`/`POSTHOG_UI_HOST`
settings in `freedom_ls/deployment/config.py:24-28`. **FLS has no precedent for hand-instrumented
custom analytics events of any kind** — PostHog today is autocapture-only, gated the same
key-present/key-absent way this GA4 work is expected to follow. This means there is no existing
in-repo pattern to copy for "how FLS fires a custom analytics event from a view"; the closest
analogous pattern in the codebase is the webhook system (§3), not an analytics SDK call.

## 5. Overlap with `referral-attribution-over-time` (`spec_dd/1. next/`)

That spec (not yet built) adds `AttributionTouch` and `Conversion` models in
`freedom_ls/referral_tracking/`, fed by UTM/referral-code cookies, to answer "which partner code was in
play when this person converted" — for **payout purposes**, entirely inside FLS's own database. Its own
research (`research_attributable_events.md`) independently walked the same four moments this file
covers (signup, application, interest, registration) and reached the same facts: `registered_at`/
`created_at` are `auto_now_add` and frozen on reactivation, and no webhook event exists for
applications or interest today.

**The boundary:** referral-attribution is about crediting a *referral partner* for a conversion,
recorded server-side, forever, for a payout query — a different consumer than GA4, which wants
*marketing-channel* attribution (organic/paid/social/UTM campaign) joined through its own `client_id`
and its own session model, on its own retention schedule. They read overlapping raw signals (UTM
params, the same four "someone converted" moments) but serve different purposes and must not be
conflated:
- GA4's UTM handling is automatic once `gtag.js` is loaded (part of the separate base-integration
  worker's scope) and needs no new FLS model.
- `referral_tracking`'s cookie and `AttributionTouch`/`Conversion` models are FLS's own, privacy-
  sensitive, consent-gated-eventually record — this GA4 work should not read from or write to that
  app, and should not be blocked on it landing (it is still in "1. next", unbuilt).
- If/when both exist, the natural shared hook points are the *same four call sites* (`save_user`,
  `_start_application`/`application_check_answers`, `course_interest` views,
  `initiate_course_access`/`_ensure_and_announce`) — each system attaches its own side effect there
  independently; neither should call into the other's app (`referral_tracking`'s own spec deliberately
  keeps zero new inbound edges from itself, per its "no dependency" decision).

## 6. Recommendation: first set of events, and sending mechanism

**Send first, client-side, keyed to FLS's three existing webhook moments plus one addition:**

| Event | GA4 name | Fire point | Mechanism |
| --- | --- | --- | --- |
| New sign-up | `sign_up` | `AccountAdapter.save_user()`, same branch as `fire_webhook_event("user.registered", ...)` | One-shot flag read on the next rendered page (post-signup redirect) |
| Course start | `tutorial_begin` (borrowed name) or a plain custom name (see caveat) | `_ensure_and_announce()`, same branch as `fire_webhook_event("course.registered", ...)` | One-shot flag on the redirect target |
| Course completion | `tutorial_complete` | `course_finish()`, same branch as `fire_webhook_event("course.completed", ...)` | Fires directly in the page `course_finish()` renders — no redirect needed, the completion page itself is the "next page" |
| Course application submitted | `generate_lead` | `application_check_answers()`, on the branch that calls `form_progress.complete()` (form-gated), **and** `_start_application()`'s creation branch for the no-form case (submission and creation coincide there per `CourseApplication.is_submitted`) | One-shot flag on the redirect (dashboard, or the no-form confirmation page) |

Rationale for client-side first: none of these four fire points is an HTMX partial (checked in §2 —
`CourseInterest`'s views are the HTMX ones, and interest is deliberately deferred, see below), each
already ends in either a full-page redirect or a full-page render, so a one-shot flag costs no new
credential, no `client_id` plumbing, and no new async infrastructure. It also matches the "if unset,
nothing is sent" simplicity the user asked to mirror from PostHog.

**Hold back for a later pass:**
- **`login`** — no existing FLS hook fires anything today; the lowest-value of the four the user named,
  and adding a `user_logged_in` receiver purely for GA is new infrastructure this spec should not
  introduce on day one, especially since `referral_tracking`'s own future login hook (its spec's
  "Login" requirement) is the more natural place such a receiver would eventually live.
- **`CourseInterest` (expression of interest on a coming-soon course)** — real signal, but its two fire
  points are HTMX partials with no natural full-page redirect to carry a one-shot flag, and it would
  need either an HTMX out-of-band script trigger or its own small mechanism. Bundle this into the
  `generate_lead` work once the pattern for application submission is proven, rather than solving two
  event-emission shapes (full-page + HTMX) in the same first pass.
- **Topic/quiz-level events** — no existing FLS signal at that granularity, unproven volume/value,
  and GA4 has no recommended event that fits cleanly (a quiz pass/fail is closer to a custom event than
  any of the standard ones).
- **`begin_checkout`/`purchase`** — genuinely not applicable; `course-prices` is explicitly
  display-only. Revisit only once a real payment/checkout flow exists.
- **Server-side Measurement Protocol** — hold back entirely for v1. Nothing in FLS's current flows
  happens off the main request/response cycle (no payment redirects, no async-confirmed purchase), so
  the strongest argument for it does not apply yet, and it would require sourcing a second credential
  (the API secret) and inventing `client_id` plumbing FLS's webhook payloads do not currently carry.
  Reconsider once a payment flow lands and its confirmation genuinely happens outside a browser
  request FLS controls.

**Naming caveat for `tutorial_begin`/`tutorial_complete`:** these are GA4's own event *names*, chosen
for their funnel shape (a beginning/completion pair with matching semantics to `CourseProgress.
started_at`/`completed_time`), not a claim that FLS's product vocabulary changes to "tutorial." Nothing
in `docs/product/` or the domain glossary uses "tutorial"; this is GA-facing plumbing only, exactly as
FLS's webhook events are named `course.registered`/`course.completed` in FLS's own vocabulary while
this spec's GA-side code would map them onto GA4's fixed event-name catalogue.

## References

- [Google Analytics: Recommended events](https://developers.google.com/analytics/devguides/collection/ga4/reference/events)
- [Google Analytics Help: [GA4] Recommended events](https://support.google.com/analytics/answer/9267735?hl=en)
- [Google Analytics: Measurement Protocol events reference](https://developers.google.com/analytics/devguides/collection/protocol/ga4/reference/events)
- [RudderStack: How to overcome GA4 server-side tracking challenges](https://www.rudderstack.com/blog/how-to-overcome-ga4-server-side-tracking-challenges/)
- [Analytico: Ensuring purchase revenue accuracy in GA4 & Meta with server-side tracking](https://www.analyticodigital.com/insights/server-side-tracking-purchase-revenue-accuracy)

Codebase references (not web-sourced, cited inline above): `freedom_ls/accounts/allauth_account_adapter.py`,
`freedom_ls/webhooks/events.py`, `freedom_ls/base/webhook_event_types.py`, `freedom_ls/learner_progress/signals.py`,
`freedom_ls/learner_interface/views.py`, `freedom_ls/course_applications/views.py`,
`freedom_ls/course_applications/models.py`, `freedom_ls/course_interest/models.py`,
`freedom_ls/deployment/config.py`, `freedom_ls/base/templates/_base.html`,
`spec_dd/1. next/referral-attribution-over-time/1. spec.md`,
`spec_dd/1. next/referral-attribution-over-time/research_attributable_events.md`,
`spec_dd/2. in progress/course-prices/idea.md`.

status: ok
