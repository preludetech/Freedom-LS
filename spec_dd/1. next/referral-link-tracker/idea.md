# Referral Link Tracker

## Problem / goal

We want to know how people who arrive via a **referral link** behave on the site.
Referral links carry a code that identifies a marketing campaign or an affiliate.

The referral codes themselves are **created and managed on a separate external
system** — FLS does **not** create, validate, or manage links/codes. FLS only needs to:

1. Detect when a visitor arrives carrying a referral code (and/or UTM parameters).
2. Observe what that visitor then does on the site — viewing courses, expressing
   interest, applying, registering, and creating an account.
3. Store that information so it can be analysed later.

Most of the underlying activity is already recorded elsewhere (course registrations,
interest, applications, signups); the new part is **attributing that activity to the
referral code the visitor arrived with**, including activity that happens *before* they
create an account.

## Extractability: this is a standalone, reusable Django app

**Primary architectural constraint.** This functionality must live in a **self-contained
Django app that can be lifted out of FLS and installed into other Django projects** with
minimal changes. Design every part of it for reuse, not just for FLS.

Concretely, the app:

- **Depends only on stable, standard Django surface** — `settings.AUTH_USER_MODEL` and
  (optionally) `django.contrib.sites`. It must **not** import from FLS-specific apps
  (`content_engine`, `course_interest`, `course_applications`, `student_management`,
  `accounts`) or subclass FLS base classes (`SiteAwareModel`). Dependency direction is
  strictly **host → app**, never app → host.
- **Is FLS-agnostic in naming and vocabulary** — no course/cohort/LMS-specific concepts
  baked into models or the public API. Events are generic strings the host chooses.
- **Exposes a small public integration API** the host wires into its own code (see below),
  plus a settings-driven config surface (cookie name, cookie lifetime, tracked-param names,
  consent callback, retention). Everything FLS-specific is configuration/wiring in the host,
  not code in the app.

FLS is the app's first consumer; treat FLS's needs as the driver but keep FLS out of the
app's dependency graph.

## Build vs. buy: why a first-party app (not PostHog / a CDP / an analytics tool)

We evaluated off-the-shelf tools against our constraints (see
`research_thirdparty_product_analytics.md` and
`research_thirdparty_web_analytics_and_buildvsbuy.md`). **Conclusion: build the reusable
first-party app.** No third-party tool cleanly satisfies the full requirement *chain*:
observe externally-minted codes → stitch an anonymous trail to *our own* `User` PK → record
server-side conversion events → store it **queryable and joinable with our own Postgres**
(users, courses, registrations) → ship it as a **reusable Django app**.

- **PostHog** (specifically asked about) is the strongest tool — native `identify()` merge,
  UTM capture, EU cloud, a real SQL/warehouse-join layer, cheap at our volume — but its data
  lives in its own store (self-host = ClickHouse/Kafka-class ops burden; cloud = an external
  SaaS dependency + per-site segmentation is a paid add-on). Excellent as an *optional* sink,
  not as the system of record.
- **CDPs** (Segment/Mixpanel/Amplitude) are SaaS-only with no real data ownership and
  event/MTU pricing that's punitive for a background observe-only feature. **RudderStack OSS**
  is warehouse-native (can land in our Postgres) but is an extra pipeline service with no UI.
- **Privacy analytics** (Matomo/Plausible/Umami/Fathom/GA4) are pageview-oriented: Plausible
  rejects persistent identifiers *by design* (can't do the user linkage), Matomo is MySQL and
  heavy to run, Umami is the closest (Postgres-native, has `identify()`) but is still a
  separate schema we don't own, and GA4/Fathom fail the EU data-ownership bar.

Crucially, the **"implement once, reuse again and again" goal is served *better* by the
extractable Django app than by a vendor**: for a general-purpose LMS that others install, the
app is a `uv add` with zero per-project vendor account, DPA, or bill, and its data is a plain
`JOIN` away. A vendor would make *every* downstream project inherit a SaaS dependency and GDPR
exposure — the opposite of what we want.

**Decision: local Postgres storage only for this iteration.** A pluggable "sink" seam (so a
future project could *optionally* forward the same events to PostHog/Matomo/RudderStack for
dashboards, without changing any call sites) is a **documented future extension**, not built
now — see non-goals. If forwarding is ever wanted, PostHog (EU cloud) is the recommended sink,
with RudderStack OSS / Matomo / Umami as self-hosted fallbacks.

## Scope (decisions made during refinement)

- **Store only, for now.** Persist referral hits and the resulting behaviour in a
  queryable model. **No** dashboard, report, or outbound webhook in this iteration — those
  are explicit later extensions.
- **Track anonymous browsing and link it to the account at signup.** A referred visitor
  is tracked while logged out (via a first-party visitor cookie), and their pre-signup
  activity is reconciled to the `User` when they register.
- **Support both `?ref=CODE` and standard UTM parameters**
  (`utm_source/medium/campaign/term/content`). The `ref` code is the external system's
  identifier; UTM fields are captured for extra campaign context. Treat all of these as
  untrusted input (length-capped, stored as-is, never validated against the external
  system). The exact param names should be configurable via settings, defaulting to
  `ref` + the five UTM keys.
- **Trail granularity: conversions + course/relevant object views only.** We record the
  referral hit, object views (in FLS: course views), and conversion events (in FLS: express
  interest, apply, register, signup). We do **not** log every generic page view (avoids high
  volume and reduces privacy exposure). Event *types* are host-defined strings, not an
  LMS-specific enum hard-coded in the app.
- **Attribution model is not baked into the schema.** We store *every* touch as an
  immutable, timestamped row so first-touch / last-touch / windowed attribution can be
  chosen later at query time (see `research_attribution_models.md`). No scoring or
  conflict-resolution logic is built now.
- **Optional multi-tenancy via `django.contrib.sites`.** The app's models carry an
  **optional/nullable `site` FK** using the standard Sites framework, so it works in
  projects with or without multi-tenancy. The app does **not** subclass FLS's
  `SiteAwareModel`; FLS layers its own site-aware querying/filtering on top of the app's
  models rather than the app depending on FLS's base class.

## Shape of the solution (high level)

- **Capture middleware** (in the app) — when an inbound request carries a configured
  tracking param (`?ref=` / `utm_*`), it mints/reads a long-lived first-party visitor cookie
  (independent of the Django session cookie), records the hit, and redirects to strip the
  tracking params from the URL. The host adds it to `MIDDLEWARE`. It relies only on the
  request/session, not on any FLS middleware, though it should be ordered after session and
  (if used) the Sites-resolving middleware.
- **Append-only storage** (in the app) — a two-table event log: an inbound-hit / "visit"
  row plus behaviour/"event" rows referencing it. Both carry an `anonymous_id`, a nullable
  `user` FK (`settings.AUTH_USER_MODEL`) back-filled at signup, and a nullable `site` FK.
  Append-only, following the well-known immutable-audit-row pattern. See
  `research_data_model.md` for a concrete model sketch (to be de-FLS-ified: plain models,
  not `SiteAwareModel`).
- **Public tracking API** (the integration seam) — the app exposes a small public function,
  e.g. `track_event(request, event_type, obj=None, metadata=None)`, that the host calls from
  its own code to record a conversion/view against the current visitor. **The host depends
  on the app; the app never imports the host.** In FLS, these calls live at the existing
  conversion sites — `CourseInterest`, `CourseApplication`, `UserCourseRegistration.save()`,
  and account creation in `AccountAdapter.save_user` — but that wiring is FLS code, not app
  code.
- **Anonymous → user reconciliation** (in the app, called by the host) — the app exposes a
  function, e.g. `link_visitor_to_user(request, user)`, that looks up the visitor cookie's
  id and sets the `user` FK on the matching hit/event rows. FLS calls it from
  `AccountAdapter.save_user` (alongside its existing `user.registered` webhook). The app
  itself does **not** depend on django-allauth. The anonymous id is preserved on the rows
  (not rewritten) so provenance ("was anonymous until date Y") stays queryable.

## Privacy & consent (first-class requirement for the spec)

Research (`research_privacy_consent.md`) is clear that persisting an anonymous trail and
linking it to an identifiable person is **consent-gated tracking** under EU/UK ePrivacy +
GDPR — it is *not* a strictly-necessary cookie, and IP addresses are personal data.

Decision: **build the capture/storage mechanism now, but treat consent-gating and
retention as first-class requirements the spec must address** (not an afterthought).
Because the app must stay reusable, consent is handled as a **host-provided hook**, not a
hard dependency on FLS's consent models:

- The app exposes a configurable **consent callback** (a setting pointing at a callable, or
  a documented override) that it checks before writing any persistent cookie/trail. If
  consent is absent/declined, at most do a single-request, non-persisted read. The default
  callback can be conservative (e.g. "no consent → don't persist").
- **FLS supplies its own consent implementation** via that hook, reusing its existing
  per-site `SiteSignupPolicy` (on/off + copy) and append-only `LegalConsent` (IP +
  timestamp) patterns. That integration is FLS code; the app knows nothing about
  `LegalConsent`.
- **Data minimisation** — no generic page-view logging (already decided); truncate/omit IP
  where possible and treat any stored IP as pseudonymous personal data.
- **Retention** — a defined, short retention window for un-converted anonymous trail data,
  with scheduled cleanup (a management command shipped in the app; the window is a setting),
  not "keep forever".
- **Erasure** — deleting a `User` cascades/anonymises linked trail data (standard FK
  `on_delete` behaviour, configured in the app's own models).

This is a general-purpose app installed by many operators/projects; it must let each host
*configure* compliance (consent copy, retention, on/off) rather than hard-coding one
jurisdiction's rules or one host's consent models.

## Known limitations (accepted, not bugs)

First-party-cookie-only tracking means: clearing cookies loses attribution, and
cross-device journeys (click on phone, sign up on laptop) won't link. No fingerprinting or
third-party tracking to compensate. Bots/link-unfurlers hitting referral URLs add noise; a
cheap user-agent filter reduces it but isn't a security control.

## Explicit non-goals (this iteration)

- Creating, validating, or managing referral codes/links (external system owns this).
- Any dashboard, report, or UI for viewing the data.
- Outbound webhooks per tracked conversion (the model doesn't preclude adding this later).
- Attribution scoring / first-vs-last-touch resolution logic.
- Generic page-view analytics.
- Social/SSO signup reconciliation (only wire the standard signup path now; leave a TODO
  for the social adapter if social login is ever enabled).
- Publishing the app to PyPI or splitting it into a separate repo *now* — the goal for this
  iteration is only that it is **structured to be extracted cleanly later** (self-contained,
  no host coupling), not that the extraction itself happens yet.
- Forwarding events to any third-party tool (PostHog, Matomo, RudderStack, etc.). Storage is
  local Postgres only for now; the pluggable-sink seam is a documented future extension, not
  built this iteration (see "Build vs. buy").

## Research

- `research_attribution_models.md` — why to store all touches and decide attribution later.
- `research_link_capture_and_linkage.md` — capture middleware, visitor cookie vs session,
  and the signup-time back-fill hook.
- `research_privacy_consent.md` — ePrivacy/GDPR consent, IP handling, retention, erasure.
- `research_data_model.md` — two-table append-only model sketch and prior art. **Note:** its
  sketch subclasses FLS's `SiteAwareModel` and hooks FLS models directly — for the extractable
  app, translate that to plain models (optional `contrib.sites` FK) plus the public
  `track_event` API described above.
- `research_thirdparty_product_analytics.md` — PostHog / Segment / RudderStack / Mixpanel /
  Amplitude scored against our constraints; hybrid thin-capture-layer + optional-sink verdict.
- `research_thirdparty_web_analytics_and_buildvsbuy.md` — Matomo / Plausible / Umami / GA4 /
  Fathom, plus the build-vs-buy decision framework and recommendation.
