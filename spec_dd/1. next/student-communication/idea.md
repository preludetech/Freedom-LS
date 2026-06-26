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
   private/direct messages and critical alerts; everything else defaults to a daily digest.
   Per-category, per-channel preferences (immediate / digest / off). Quiet hours,
   timezone-aware. This is the single biggest driver of notification fatigue and mass
   unsubscribes.
3. **Email is table-stakes.** Every in-platform message also generates an email
   notification (respecting preferences). This requires getting email right: verified
   addresses, surfaced delivery failures (never silent), SPF/DKIM/DMARC, one-click
   unsubscribe, conservative volume. (See dependency note on async queue below.)
4. **Audience scoping is first-class and cohort-optional.** A single audience abstraction
   targets `site | course | cohort | individual`. Installs without cohorts degrade
   gracefully to course/site/individual scope with the cohort layer invisible.
5. **Privacy & safeguarding by default.** Role-based visibility (FERPA/GDPR aware);
   explicit "who will see this" labelling on every compose action; peer (student↔student)
   messaging off by default; moderation built in (report → queue, hide/soft-delete, audit
   trail); stricter defaults available for deployments serving minors.
6. **Accessible and mobile-first.** WCAG 2.2 AA, keyboard-navigable, ARIA live regions for
   unread counts, redundant (icon+text+colour) unread state; designed for a 375px viewport.
   HTMX, no Django Channels yet.
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
5. **Notifications layer** — unified in-app centre (bell + unread badge, HTMX-polled) plus
   email delivery, behind a pluggable backend (in-app / email / webhook-via-existing
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

### Configuration precedence (most precise wins)

Comms configuration (which channels are enabled, messaging policy, notification defaults —
i.e. the *level of communication service*) resolves down a precedence chain. The most
precise config that applies to a given user-in-a-context wins; each level overrides only the
values it sets and otherwise falls through to the next. This lets a deployment offer
different levels of service in different situations — e.g. a premium cohort that gets more
support than the default.

From most precise (wins) to least (default):

1. **Course-registration config** — attached to a specific `UserCourseRegistration` *or*
   `CohortCourseRegistration`. The finest grain: "this individual learner's registration" or
   "this cohort's registration on this course".
2. **Course config** — attached to a `Course`. Applies to everyone on that course unless a
   registration-level override exists.
3. **Site config** — per-tenant (`SiteAwareModel`, mirrors `SiteSignupPolicy`). Applies
   across the site unless a course/registration override exists.
4. **Project / install default** — Django settings (with in-app defaults). The baseline when
   nothing more specific is set.

Resolution is centralised in one helper (a single place implements the walk up the chain and
the per-field fall-through), so adding a new config field or scope only touches that helper.

**To resolve in spec/plan:**
- A learner can be registered to one course *both* individually (`UserCourseRegistration`)
  *and* via a cohort (`CohortCourseRegistration`). When both carry a comms config, which
  wins? Likely "individual registration beats cohort registration" — confirm during spec.
- Whether config is a shared embedded value object / `JSONField` reused at every level, or a
  separate model per scope, is a spec/plan decision; the precedence semantics are the fixed
  requirement.

## Sensible out-of-the-box defaults

- In-app notification centre: always on, works with no configuration.
- Email notifications: on, digest-leaning defaults, user-opt-out — gated by the async-queue
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

## Explicitly later (not this iteration)

- Real-time delivery via Django Channels / WebSockets (start with HTMX polling).
- SMS / mobile push backends (architecture should accommodate; not built now).
- Reply-by-email (inbound email → thread).
- Behaviour-triggered automated messages (milestone / inactivity nudges).
