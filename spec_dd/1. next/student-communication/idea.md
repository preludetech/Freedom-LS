# Student Communication

Students and instructors need to be able to communicate through the platform.
Different FLS implementations will want to do this very differently: some use cohorts and
want cohort-level comms, some register learners individually to courses, some want only
broadcast announcements, others want full discussion + direct messaging.

The goal is a **flexible, configurable communication system** that suits the full range of
FLS deployments out of the box, built on lessons from popular LMSs (Canvas, Moodle,
Blackboard Ultra, Google Classroom, Open edX, and creator platforms). It must be
multi-tenant (site-aware) and cohort-optional.

> This is a high-level idea, not a full specification. Decisions below are deliberate; the
> detailed data models, views, and UI belong in the spec/plan phases.

## Research

See the `research_*.md` files in this directory:

- `research_lms_comms_landscape.md` — how popular LMSs handle student↔instructor comms (what they do well/badly).
- `research_comms_patterns.md` — feature & data-model patterns per modality, plus reusable Django packages.
- `research_comms_ux_pitfalls.md` — common UX complaints and a prioritised do's/don'ts checklist.
- `research_flexible_configurable_comms.md` — how to make comms pluggable/configurable for an installable, multi-tenant app.
- `research_prior_*.md` — earlier research carried over from the `messages` draft (messaging tech, messaging UX, notification UX).

## Guiding principles (from research)

1. **Minimise "places to check."** A single unified notification / activity centre is the
   one place a user looks; individual channels surface there and link back to context.
   Fragmentation across separate inboxes/forums/comment threads is the #1 complaint.
2. **Conservative, digest-leaning notification defaults.** Immediate delivery only for
   private/direct messages and critical alerts; everything else defaults to a digest.
   **Digest frequency is configurable** (e.g. immediate / daily / weekly / off) — daily is a
   sensible default but won't suit everyone, so it must be a per-user, per-category,
   per-channel preference and overridable down the config precedence chain. Quiet hours,
   timezone-aware. This is the single biggest driver of notification fatigue and mass
   unsubscribes.
3. **Email is table-stakes — but governed by preferences, never one-per-message.** Email is
   a first-class delivery channel for in-platform activity, but it must never fire an email
   for every message: a per-message email on an active back-and-forth conversation is
   notification spam. Email follows the same per-category, per-channel preferences as the
   in-app centre — **immediate / digest / off**, fully configurable, and any category can be
   turned off completely. The conversational default is a roll-up digest ("you have 5 unread
   messages across 3 conversations") rather than one email per message; immediate email is
   reserved for things that genuinely warrant it (e.g. the first message of a new
   conversation, or critical alerts) and is itself opt-out. This requires getting email
   right: verified addresses, surfaced delivery failures (never silent), SPF/DKIM/DMARC,
   one-click unsubscribe, conservative volume. (See dependency note on async queue below.)
4. **Audience scoping is first-class and cohort-optional.** A single audience abstraction
   targets `project | site | course | cohort | individual`. `project` is the broadest scope —
   the whole multi-site install — and provides the default that all sites inherit and can
   override (e.g. a project-wide announcement, or project-level comms config every site falls
   back to). Installs without cohorts degrade gracefully to project/site/course/individual
   scope with the cohort layer invisible.
5. **Privacy & safeguarding by default.** Role-based visibility (FERPA/GDPR aware);
   explicit "who will see this" labelling on every compose action; peer (student↔student)
   messaging off by default; moderation built in (report → queue, hide/soft-delete, audit
   trail); stricter defaults available for deployments serving minors.
6. **Accessible and mobile-first.** WCAG 2.2 AA, keyboard-navigable, ARIA live regions for
   unread counts, redundant (icon+text+colour) unread state; designed for a 375px viewport.
   HTMX for general interactivity, with **Django Channels / WebSockets for real-time
   delivery** (live unread counts, incoming messages, typing/presence where it helps). The
   real-time layer must degrade gracefully to HTMX polling where WebSockets aren't available,
   so the experience never hard-depends on a live connection.
7. **Pluggable everything.** Channels are optional installed apps; messaging policy and
   notification delivery are swappable backends; per-site behaviour is DB-configurable.

## Channels (in scope)

A shared base (`freedom_ls.comms`) provides config, the audience abstraction, and the
notifications layer. Each channel is an optional sub-app so installs include only what they
need.

1. **Announcements / broadcasts** — instructor (or admin) → audience
   (site/course/cohort/individual). Pinned, schedulable, persistent on the course page (not
   just a one-off email), read/dismissal tracking. Cohort-scoped broadcast is a first-class
   feature, not an afterthought.
2. **Direct messaging** — 1:1 (and small-group) conversations. Instructor↔student enabled
   by default; **peer messaging supported but off by default** via a swappable
   `MessagingPolicy` (`InstructorInitiatedPolicy` default, `OpenPolicy` / cohort-restricted
   opt-in). Threads with read state, chat-style UI.
3. **Discussion forums** — per course (and optionally per cohort), threaded, with Q&A mode,
   instructor "endorse answer", role labels (instructor vs peer), subscriptions, and
   moderation. Course/cohort-scoped visibility.
4. **Contextual / inline feedback** — comments attached to a specific content item or
   submission (generic-FK pattern already used in FLS). Private instructor↔student feedback
   distinct from public discussion; "internal" instructor-only notes supported.
5. **Notifications layer** — unified in-app centre (bell + unread badge), updated in
   **real time over Django Channels / WebSockets** with HTMX polling as a graceful fallback,
   plus email delivery, behind a pluggable backend (in-app / email / webhook-via-existing
   `fire_webhook_event`, with push/SMS as future backends). Per-user preferences and
   digests live here.

## Configurability

- **Channels as optional apps** under `freedom_ls.comms` (conditional `INSTALLED_APPS`);
  a context processor exposes which are active so UI degrades cleanly.
- **Swappable `MessagingPolicy`** selected by settings dotted-path (and optionally per-scope,
  see precedence below), resolved via `import_string` — mirrors the existing
  `COURSE_ACCESS_BACKEND` pattern.
- **Pluggable `NotificationBackend`(s)** via `COMMS_NOTIFICATION_BACKENDS`.
- **Cohort-optional** audience resolution centralised in one helper; the base comms app must
  not hard-depend on cohort models.
- **Extension points:** Django signals for outbound events (e.g. `message_sent`,
  `announcement_posted`); template overrides via the loader hierarchy; a lightweight channel
  registry for future channels.

### Configuration precedence (two axes, per-field resolution)

Comms configuration (which channels are enabled, messaging policy, notification defaults —
i.e. the *level of communication service*) resolves along **two orthogonal axes**:

- **Context axis** — *where* the user is. A precedence chain from most precise to least:
  course-registration → course → site → project/install default. The most precise config that
  applies to the user-in-that-context wins; each level overrides only the values it sets and
  otherwise falls through to the next. This lets a deployment offer different levels of service
  in different situations — e.g. a premium cohort that gets more support than the default.
- **User axis** — *who* the user is. A per-user, platform-wide entitlement that applies across
  every context — e.g. someone who bought a "premium subscription" to the platform as a whole
  and should get a higher level of comms service everywhere they go.

A platform-wide per-user entitlement is **not "more" or "less precise"** than a
course-registration config — it's broad in *context* but specific in *person*. The two axes
are orthogonal, so when they disagree on a field "most precise wins" is undefined. A
**per-field tie-break** decides which axis wins for that field (see below).

**Context axis (most precise context wins).** From most precise (wins) to least (default):

1. **Course-registration config** — attached to a specific `UserCourseRegistration` *or*
   `CohortCourseRegistration`. The finest grain: "this individual learner's registration" or
   "this cohort's registration on this course".
2. **Course config** — attached to a `Course`. Applies to everyone on that course unless a
   registration-level override exists.
3. **Site config** — per-tenant (`SiteAwareModel`, mirrors `SiteSignupPolicy`). Applies
   across the site unless a course/registration override exists.
4. **Project / install default** — Django settings (with in-app defaults). The baseline when
   nothing more specific is set.

**User axis.** A per-user config attached to the `User`, site-scoped (one row per user per
site, mirroring `SiteAwareModel`). The motivating case is a platform-wide premium
subscription that grants a richer level of comms service regardless of which course, cohort,
or site context the user is acting in.

**Per-field resolution.** When the resolved user-axis value and the resolved context-axis
value disagree on a field, a **declared per-field policy** decides the winner — the deployment
chooses *at each point*. Three illustrative cases:

- **User wins (floor).** The premium user's value acts as a *minimum guaranteed* level of
  service — the context can raise it but never drop below it.
- **Context wins.** The context value wins even over a premium user — e.g. a course that
  disables peer (student↔student) messaging for safeguarding must win regardless of any
  user-level entitlement.
- **Neither privileged.** Fall back to the context axis ("most precise context wins") as the
  default for ordinary fields.

Resolution is centralised in one helper: a single place walks *both* axes and applies the
per-field tie-break, so adding a new config field or scope only touches that helper.

**To resolve in spec/plan:**
- A learner can be registered to one course *both* individually (`UserCourseRegistration`)
  *and* via a cohort (`CohortCourseRegistration`). When both carry a comms config, which
  wins? Likely "individual registration beats cohort registration" — confirm during spec.
- **How the per-field tie-break is expressed** — e.g. fields declaring floor / ceiling /
  override semantics, or the user-axis config naming which fields it forcibly overrides. The
  mechanism is a spec/plan decision; the fixed requirement is that the user-vs-context winner
  is **decidable per field**.
- **Where the user-axis config lives and what feeds it** — likely a per-user, site-scoped
  model (mirrors `SiteSignupPolicy` / `SiteAwareModel`). Its value is *likely fed by* the
  drafted subscriptions concept (`spec_dd/0. drafts/03. subscriptions/`), but comms must stay
  **decoupled** — it reads a user-level config value and must not hard-depend on a
  subscriptions app existing.
- **Scope of the user axis** — confirm whether per-user config is per-site (a user can be
  premium on one site but not another) or truly project-wide; per-site (`SiteAwareModel`) is
  the likely default given the multi-tenant model.
- Whether config is a shared embedded value object / `JSONField` reused at every level, or a
  separate model per scope, is a spec/plan decision; the precedence semantics are the fixed
  requirement.

## Sensible out-of-the-box defaults

- In-app notification centre: always on, works with no configuration.
- Email notifications: on, digest-leaning defaults (daily digest out of the box, frequency
  configurable per user/category/channel), user-opt-out — gated by the async-queue
  dependency below.
- Messaging policy: `InstructorInitiatedPolicy` (instructors start, students reply; no peer
  DMs).
- No cohort assumptions; everything works for individually-registered learners.

## Dependencies & things to resolve in spec/plan

- **Async task queue.** FLS currently runs Django Tasks on the synchronous *immediate*
  backend. Broadcast fan-out to large audiences and email digest batching need a real async
  backend (already flagged as a prod TODO in settings). This is a prerequisite for the email
  and large-broadcast parts of the notifications layer and must be decided during spec/plan.
- **Email deliverability** for the host deployment (SPF/DKIM/DMARC, verified-address
  handling, bounce/complaint feedback). FLS only sends allauth transactional mail today; the
  comms layer significantly increases volume.
- **Django Channels / ASGI + channel layer.** Real-time delivery requires running FLS under
  ASGI and a channel-layer backend (e.g. Redis via `channels_redis`) for cross-process
  fan-out. FLS is WSGI today, so the spec/plan must decide the ASGI deployment story and how
  the real-time layer stays optional — degrading to HTMX polling — for installs that don't
  run a channel layer.

## Explicitly later (not this iteration)

- SMS / mobile push backends (architecture should accommodate; not built now).
- Reply-by-email (inbound email → thread).
- Behaviour-triggered automated messages (milestone / inactivity nudges).
