# Research: Product Analytics & Customer Data Platforms for Referral/Campaign Tracking

Lane: third-party product-analytics / CDP tools, evaluated for build-vs-buy on FLS's referral-link
tracker. Constraints recap: codes are minted externally (we only *observe*), we need
anonymous→identified stitching, "store-only" but queryable/joinable raw events, multi-site (Django
`sites`) segmentation, EU/UK GDPR posture, and a design we can **implement once and reuse across many
downstream Django projects**.

---

## 1. PostHog (given the most depth, as requested)

### What it is
Open-source product analytics platform with event capture, session replay, feature flags, and (newer)
a ClickHouse-backed data warehouse with SQL access (HogQL). Ships both as **PostHog Cloud** (US or EU
region) and as **self-hosted OSS**.

### 1. Referral/UTM capture + anonymous→identified linkage
- `posthog-js` auto-captures the five standard UTM parameters (`utm_source/medium/campaign/content/term`)
  plus `gclid`/`fbclid`/`msclkid`, storing both "initial" and "most recent" values as **person
  properties**. Custom params (our `?ref=CODE`) are captured by adding them to
  `custom_campaign_params`, or trivially by capturing a `ref` property server-side ourselves.
  [UTM segmentation docs](https://posthog.com/docs/data/utm-segmentation)
- Anonymous events use an auto-generated `distinct_id` (cookie/localStorage). On signup, calling
  `posthog.identify(user_id)` **merges the anonymous person into the identified person** — full history
  (including pre-signup UTM/ref properties) becomes available under the real user ID. `alias()` is the
  companion call for stitching two IDs you control directly (e.g. a backend ID before a frontend ID
  exists). This is exactly the identify+merge model the feature needs.
  [Identify docs](https://posthog.com/docs/product-analytics/identify)
- Caveat: merge behaviour has known edge cases (must call `identify` only once per real transition;
  duplicate/reused distinct_ids cause unwanted merges) — well documented but requires discipline.

**Score: good fit.**

### 2. Self-hostable / data ownership / EU residency
- Core self-hosted product is **MIT licensed** ("provided without a guarantee" — community support
  only, PostHog explicitly will not troubleshoot instance-specific self-host issues).
  [OSS support policy](https://posthog.com/docs/self-host/open-source/support) ·
  [Self-host docs](https://posthog.com/docs/self-host)
- PostHog Cloud offers an **EU region hosted in Frankfurt** for residency requirements, with a DPA.
  [Pricing](https://posthog.com/pricing)
- Self-hosting = full data ownership + EU residency by construction (data never leaves our
  infrastructure), but PostHog itself warns that "PostHog at production scale is a data-intensive
  application with a complex system architecture" — non-trivial ops burden (ClickHouse, Kafka/Redis,
  multiple services).

**Score: good fit for data ownership; self-host OSS is operationally heavy; EU Cloud is the pragmatic middle ground.**

### 3. Django integration effort / reusability
- Official `posthog-python` SDK, `pip install posthog`, with a **Django middleware** that wraps every
  request in a context and auto-tags captured events with session/user metadata.
  [Django library docs](https://posthog.com/docs/libraries/django)
- Straightforward to package as a small reusable Django app: settings-driven API key/host, middleware
  in `MIDDLEWARE`, a thin `capture()` wrapper. Requires the frontend and backend to agree on
  `distinct_id` (documented pitfall: mismatched IDs create orphaned events) — an integration detail
  every downstream project must get right, not a blocker.
- Genuinely reusable: it's just a pip package + a few settings, no schema/migrations of ours required.

**Score: good fit.**

### 4. Multi-tenant / per-site segmentation
- PostHog's native multi-tenancy primitive is **Group Analytics** (define a "group type" like
  `site`/`organization`, tag every event with a group key, then filter/aggregate by group). Up to 5
  group types per project; it's an **add-on with its own pricing** (first ~1–2M group-events free, then
  metered) and "every event must carry the group identifier or the rollup breaks" — i.e., it's opt-in
  and must be wired into every capture call, not automatic.
  [Group analytics docs](https://posthog.com/docs/product-analytics/group-analytics)
- Alternative that avoids the paid add-on: tag every event with a plain `site_id`/`site_domain`
  property (django.contrib.sites) and filter with HogQL/insights — works but loses the native
  group-rollup UX.

**Score: partial** — doable, but per-site segmentation is either a paid feature or a manual-property
convention; nothing gives us free, automatic per-tenant isolation.

### 5. Query raw events / join with our own app data
- PostHog now ships a genuine **SQL layer (HogQL)** over the events/persons/groups tables, with a SQL
  editor, and a **data warehouse** feature that can **join PostHog events directly against external
  Postgres tables** (and Stripe, HubSpot, S3, Snowflake, BigQuery, etc.) in one query.
  [SQL access](https://posthog.com/docs/sql) · [Joining data](https://posthog.com/docs/data-warehouse/join)
- **Batch exports** to S3/Postgres/Snowflake/BigQuery/Redshift/Databricks/Azure Blob are built in for
  getting raw events out.
- This is the strongest "queryable and joinable" story of any tool in this lane, self-hosted or cloud.

**Score: good fit.**

### 6. Cost model at realistic scale
- Usage-based, priced per event (not MTU): ~$0.00005/event for the first 1–2M events/month, dropping
  to ~$0.000009/event past 250M; **1M events/month free** on Cloud.
  [Pricing](https://posthog.com/pricing)
- For an "observe-only" referral tracker (page views + a handful of conversion events per visitor),
  volumes will likely stay inside or just past the free tier for a single LMS deployment — cheap.
  Self-hosting removes per-event cost but adds infra cost (ClickHouse cluster) instead.
- Group analytics, session replay, etc. are separately metered add-ons if adopted later.

**Score: good fit** for our light "store-only" event volume.

### 7. Consent / privacy controls
- **EU Cloud region** (Frankfurt) plus published DPA; GDPR page documents deletion.
  [GDPR compliance](https://posthog.com/docs/privacy/gdpr-compliance)
- **Deletion API**: `DELETE` on the Persons endpoint with `delete_events=true` removes a person and
  their events (personal API key required); processed asynchronously, and PostHog recommends not
  reusing a deleted `distinct_id`.
- Default EEA/UK/Switzerland retention is **24 months** unless you request earlier deletion; supports
  IP anonymization and cookieless/consent-gated capture (JS SDK can be initialized only after consent
  is obtained, or use `opt_out_capturing()`).
- Self-hosting sidesteps most of these questions entirely (data never leaves our DB), at the cost of
  us being responsible for retention/erasure tooling.

**Score: good fit** (Cloud has a real erasure API + documented retention; self-host gives full control
by default).

### 8. Fit for "external codes + store-only + observe-only"
PostHog was built to *observe* behaviour, not to mint/manage anything — this maps cleanly onto "codes
come from elsewhere, we just record what happened." No feature of PostHog assumes it owns the referral
code lifecycle, so there's no fighting the tool's opinions.

### 9. Lock-in / operational burden on every downstream project
- Cloud: low burden (pip package + settings + a queue/async send, which the Python SDK already
  batches/threads); but every downstream project now has an external SaaS dependency, an account, and
  a bill (even if small).
- Self-host: real operational burden (ClickHouse/Kafka-class deployment) that most small downstream
  Django projects will not want to run just for referral tracking — this is a good fit only if
  PostHog is already/will be adopted org-wide for product analytics generally, not solely for this
  referral use case.

---

## 2. Segment (Twilio Segment)

1. **Referral/UTM + identity**: Segment's `analytics.js`/server libs auto-capture UTM as `context.campaign`
   fields; `identify()`/`alias()` are first-class, foundational CDP primitives — arguably the *origin*
   of this identify/alias pattern that PostHog and RudderStack both mirror.
2. **Self-host/EU residency**: **No self-hosted option** — SaaS only. Data residency/region controls
   exist but it's Twilio-operated infrastructure, not ours.
3. **Django reuse**: Official Python server-side SDK exists; reasonably reusable, but you're wiring a
   commercial SaaS into every project.
4. **Multi-tenant**: Workspaces/sources give some separation but nothing native to `django.contrib.sites`.
5. **Query/join raw data**: Segment's model is destination-based routing (send raw events onward to a
   warehouse destination) rather than an in-product SQL/query layer — you still need your own warehouse
   to query/join.
6. **Cost**: MTU-based; Free tier is very small (1,000 visitors/mo, 2 sources), Team tier starts
   ~$120/mo for 10k MTUs — expensive fast for a "store only" use case with modest analytics value.
7. **Consent/GDPR**: Enterprise-grade compliance program, DPAs, but no self-hosting means no EU data
   residency by default without paid regional options and no way to fully own the data.
8. **Company trajectory concern**: Segment was demoted to "Niche Player" in Gartner's 2025 CDP Magic
   Quadrant after Twilio impairments/layoffs and a 2025 restructuring; product is being folded into
   twilio.com. Not an existential risk today, but a signal of reduced investment.

**Score: poor fit** — no self-hosting, MTU pricing is punitive for an "observe only, store for later"
use case, and it doesn't solve the query/join need on its own (you'd still need your own DB/warehouse
behind it, at which point Segment is just an expensive router).

Sources: [What is Twilio Segment](https://cdp.com/articles/what-is-twilio-segment/) ·
[Segment pricing](https://www.twilio.com/en-us/pricing/customer-data)

---

## 3. RudderStack (open-source CDP)

1. **Referral/UTM + identity**: JS + server SDKs (including Python) support `identify`, `track`,
   `alias` with the same Segment-compatible API surface; UTM auto-capture on the JS SDK.
   [Python SDK](https://www.rudderstack.com/docs/sources/event-streams/sdks/rudderstack-python-sdk/)
2. **Self-host/EU residency**: `rudder-server` is genuinely **open source and self-hostable**
   ("RudderStack Open Source" — full event-stream + transformations), giving full data ownership and
   EU residency by deploying in our own infra.
   [RudderStack Open Source](https://www.rudderstack.com/docs/get-started/rudderstack-open-source/)
3. **Django reuse**: Official Python SDK is a thin HTTP client (`rudderstack-python-sdk`), easy to wrap
   in a reusable Django app/middleware, same shape as PostHog's.
4. **Multi-tenant**: No native per-site concept; would rely on a custom `site_id` property in every
   event, same as PostHog's non-group-analytics fallback.
5. **Query/join raw data**: RudderStack has pivoted to a **warehouse-native architecture** — events
   land in *our own* Postgres/Snowflake/BigQuery/Databricks, and identity resolution ("Profiles") plus
   Reverse ETL operate directly against that warehouse via SQL. This is arguably the cleanest "queryable
   and joinable with our own app data" story, because the warehouse literally *is* our own Postgres.
   [Warehouse-native architecture](https://www.rudderstack.com/learn/customer-data-platform-cdp/warehouse-native-architecture-operating-model/)
6. **Cost**: OSS self-hosted event stream is free (infra cost only); managed tiers start at ~$220/mo
   for 1M events, free tier up to 250k events/mo. Reverse ETL is billed per-destination-per-record,
   which we would not need for a store-only use case.
7. **Consent/GDPR**: Self-hosting again solves residency/ownership by construction; RudderStack markets
   HIPAA/GDPR support, SSO, RBAC, SSH tunnels on paid tiers, but the OSS event-stream tier is a thinner
   product than PostHog OSS (no built-in analytics UI at all — it's a pure pipeline).
8. **Fit for external-codes/store-only**: Very good — RudderStack OSS's core job *is* "capture raw
   events and land them in your warehouse," which is precisely "store only for now, query later."

**Score: good fit**, arguably the best-aligned OSS CDP for the "land raw events in our own Postgres and
join with our own data" requirement specifically, at the cost of having no analytics UI out of the box
(you'd query with plain SQL/Django ORM against the landed tables, which is fine for "no dashboard needed
yet").

Sources: [RudderStack pricing](https://www.rudderstack.com/pricing/) ·
[Open Source FAQ](https://www.rudderstack.com/docs/get-started/rudderstack-open-source/faq/)

---

## 4. Jitsu (open-source, "Segment alternative")

1. **Referral/UTM + identity**: JS SDK does browser capture; server-side is via a generic **HTTP events
   API** (any language, incl. Python via `requests`), but there's no polished, official Python SDK with
   identify/alias helpers the way PostHog/RudderStack/Segment/Mixpanel/Amplitude ship — you'd be
   hand-rolling the JSON payload against the HTTP API.
   [HTTP API](https://jitsu.com/docs/sending-data/http)
2. **Self-host/EU residency**: 100% open source (MIT), self-hostable; a bundled free ClickHouse
   destination or bring-your-own warehouse (Postgres/Snowflake/BigQuery/Redshift/MySQL). Full EU
   residency/data-ownership by deploying ourselves.
3. **Django reuse**: Because there's no first-class Python SDK, building a reusable Django app means
   writing and maintaining our own thin HTTP client — more work than PostHog/RudderStack, and that
   maintenance burden repeats for every consumer unless we centralize it in one shared package (which
   we'd have to build ourselves, unlike the others).
4. **Multi-tenant**: No native concept; same manual-property approach as the others.
5. **Query/join raw data**: Strong — events land in Postgres/ClickHouse/warehouse of choice, directly
   queryable/joinable with plain SQL.
6. **Cost**: Free (self-hosted); requires running Jitsu's own service stack (needs a JVM/Go runtime +
   Postgres or ClickHouse) — moderate ops burden, lighter than PostHog OSS.
7. **Consent/GDPR**: Self-hosting again means we own retention/erasure entirely (implement it
   ourselves — Jitsu doesn't provide a managed deletion API since there's no SaaS control plane in the
   OSS deployment model we'd use).
8. **Fit for external-codes/store-only**: Reasonable in spirit (it's explicitly a raw ingestion
   pipeline) but the weakest Python ergonomics of the OSS options here.

**Score: partial** — good architecture fit, but lacks official Python/Django tooling, making the
"implement once, reuse everywhere" goal harder than PostHog or RudderStack.

Sources: [Jitsu GitHub](https://github.com/jitsucom/jitsu) · [Jitsu docs](https://jitsu.com/docs)

---

## 5. Mixpanel

1. **Referral/UTM + identity**: Solid `identify()`/`alias()` primitives; notably documents a flag to
   **disable retroactive merging** of pre-identification (anonymous) history unless consent was given —
   a genuinely useful GDPR-aware nuance the others don't foreground as clearly.
2. **Self-host/EU residency**: **No self-hosting** — SaaS only. Does offer a dedicated **EU Data
   Residency program**, hosting raw events in a Netherlands data center at no extra cost; as of Aug
   2025 new EU projects only ingest into the EU region if the SDK targets the EU endpoint (i.e., it's
   opt-in and must be configured correctly per project).
   [EU Residency docs](https://docs.mixpanel.com/docs/privacy/eu-residency) ·
   [GDPR compliance](https://docs.mixpanel.com/docs/privacy/gdpr-compliance)
3. **Django reuse**: Official Python SDK, straightforward to wrap.
4. **Multi-tenant**: No native per-site tenancy primitive beyond custom event/user properties.
5. **Query/join raw data**: Mixpanel has raw event export APIs but no first-class warehouse-join/SQL
   layer comparable to PostHog's HogQL or RudderStack's warehouse-native model — you'd export and load
   into your own DB to join with app data, an extra step.
6. **Cost**: Free tier ~1M events/mo; Growth from ~$20/mo; enterprise from ~$1,167/mo+ — moderate, but
   scales with MTUs/events in ways that add up for a background "store only" feature.
7. **Consent/GDPR**: Good EU-residency story for a pure SaaS tool, but no self-hosting means no true
   data ownership — we're always trusting a third party with even "store only" raw events.
8. **Fit for external-codes/store-only**: Fine functionally, but doesn't add anything PostHog/RudderStack
   don't already do better on the query/join and ownership axes.

**Score: partial** — solid identity/GDPR nuance, but SaaS-only with a weaker query/join story than the
OSS options.

---

## 6. Amplitude

1. **Referral/UTM + identity**: Mature identify/merge model, comparable to Mixpanel/Segment.
2. **Self-host/EU residency**: **SaaS only, no self-hosting.** EU Data Residency option stores events
   in AWS eu-west-1 (Ireland) on **Business/Enterprise plans only** — i.e., paywalled. Analysis notes
   EU residency "does not resolve" CLOUD Act exposure concerns for EU-strict organizations (a US-parent
   company can still be compelled to produce data under US law regardless of where it's stored).
   [Data residency and privacy](https://amplitude.com/blog/data-residency-and-privacy)
3. **Django reuse**: Official Python SDK exists.
4. **Multi-tenant**: No native per-site primitive.
5. **Query/join raw data**: Export APIs and warehouse connectors exist but, like Mixpanel, it's not an
   in-place SQL/join layer over your own Postgres — again an extra ETL hop.
6. **Cost**: Free under 50k MTUs; Plus ~$49/mo (50–300k MTUs); Growth/Enterprise scales from
   ~$22k/yr into six figures at higher MTU bands — this is priced for genuine growth-analytics teams,
   not a lightweight observe-only referral tracker.
7. **Consent/GDPR**: GDPR-compliant program with SOC2/ISO27001, but EU residency behind a paywall and
   the CLOUD Act caveat above is a real concern for a UK/EU-first compliance posture.
8. **Fit**: Functionally fine, but cost and lack of self-hosting/warehouse-native design make it the
   weakest match to "self-hosting/data ownership matters a lot" among the paid SaaS tools.

**Score: poor-to-partial fit** — expensive at any real scale, EU residency gated behind paid plans, no
self-host option, weaker query/join story than the OSS choices.

---

## 7. June (June.so)

June was a B2B-focused product analytics tool (PostHog-adjacent positioning, not a PostHog product).
**June wound down operations in July 2025** and its founding team joined Amplitude; existing customers
were given until August 2025 to export data or migrate.
[A new chapter for June](https://www.june.so/blog/a-new-chapter) ·
[HN discussion](https://news.ycombinator.com/item?id=44502506)

**Score: not viable — defunct.** Excluded from further comparison; do not build against it.

---

## The hybrid option: our own thin capture layer + pluggable sink

**Proposed architecture**: a small first-party Django app (e.g. `referral_tracking`) that:
- Provides middleware/view-decorator to capture `?ref=CODE` + UTM params on first touch, storing them
  in the session (or a signed cookie) for the anonymous visitor.
- Exposes a single internal `track_event(event_name, distinct_id, properties, site)` call used at each
  of our defined conversion points (course view, express interest, apply, register, signup) — this call
  is the *only* thing downstream code depends on.
- On signup, calls a `link_identity(anonymous_id, user)` step that performs the anonymous→identified
  merge in whichever sink is configured.
- Routes both to a **pluggable sink interface** — `LocalPostgresSink` (writes to our own `ReferralEvent`
  model, joinable via ordinary Django ORM/`select_related` with `User`/`Course`/`Registration`) as the
  default/always-on sink, with **optional additional sinks** (PostHog, RudderStack) enabled via
  settings for host projects that want a full analytics UI on top.

**Why this is the right shape for "implement once, reuse many times":**
- It decouples "what we track" (our conversion funnel, our UTM/ref parsing, our multi-site tagging)
  from "where it goes" (a swappable backend), so every downstream Django project gets the same event
  vocabulary and Django-idiomatic model (queryable via the ORM, no external dependency required to
  satisfy the "store only, queryable, joinable" requirement) — and can *optionally* bolt on a real
  analytics tool without changing any call sites.
- It avoids hard lock-in to any single vendor's SDK/API shape at every call site in every project;
  only the sink adapter needs updating if a vendor's API changes or we swap vendors.
- Consent gating, per-site (`django.contrib.sites`) tagging, and GDPR erasure become **our own code**
  (straightforward against our own Postgres table) rather than something we must trust/configure
  correctly in a third party for every project.

**What the surveyed SDKs make easy/hard for this pattern:**
- **PostHog's** and **RudderStack's** Python SDKs are the easiest to wrap as an *optional secondary
  sink*: both are simple `capture()`/`identify()` HTTP clients with batching built in, no schema
  coupling — good adapter targets.
- **RudderStack OSS being warehouse-native** means, if a downstream project already runs RudderStack,
  its "warehouse" could literally *be* the same Postgres our `LocalPostgresSink` writes to — the two
  options aren't even mutually exclusive.
- **Segment/Mixpanel/Amplitude** SDKs are equally easy to adapt as sinks technically, but their
  cost/self-hosting profile makes them less attractive *default* choices — fine as an opt-in sink for a
  project that already pays for one of them.
- **Jitsu** is the hardest to adapt cleanly since there's no first-class Python SDK to wrap — we would
  be maintaining our own HTTP client for it, which is more the exception than the rule and lowers its
  attractiveness as a plug-in sink option (though the HTTP API itself is simple enough to hand-write).

**Verdict on the hybrid**: Yes — this is the sensible "implement once, use again and again"
architecture. The always-on local Postgres sink alone satisfies every hard constraint (store-only,
queryable, joinable, multi-site via a `site` FK, GDPR erasure via a Django admin action/management
command deleting rows for a user). Any product-analytics tool becomes strictly optional sugar on top,
not a dependency the core feature needs.

---

## Comparison table

| Tool | Identify/alias | Self-host / EU residency | Django SDK reuse | Multi-site | Query/join own data | Cost at our scale | GDPR/consent | External-codes/observe-only fit |
|---|---|---|---|---|---|---|---|---|
| **PostHog** | Good — native merge on `identify` | OSS self-host (MIT, community support only) **or** EU Cloud (Frankfurt) | Good — official `posthog-python` + Django middleware | Partial — Group Analytics is a paid add-on; manual property otherwise | Good — HogQL SQL + warehouse joins + batch export | Good — ~free under 1M events/mo | Good — EU region, deletion API, 24mo default retention | Good |
| **RudderStack** | Good — Segment-compatible API | Good — genuinely OSS self-hostable event stream | Good — official Python SDK | Partial — manual property, no native concept | Very good — warehouse-native, lands in our own Postgres | Good — free self-hosted (infra cost only); free tier 250k events/mo managed | Good on self-host (full ownership); GDPR/HIPAA marketed on paid tiers | Good |
| **Jitsu** | Partial — no polished Python identify/alias helpers | Good — OSS, self-hostable, bundled ClickHouse or BYO warehouse | Partial — HTTP API only, no first-class Python SDK | Partial — manual | Good — lands in Postgres/warehouse directly | Good — free self-hosted | Partial — self-host gives ownership but no managed erasure tooling | Partial |
| **Segment** | Good (origin of the pattern) | Poor — SaaS only, no self-host | Partial — official SDK but SaaS dependency everywhere | Poor | Partial — router to warehouse, not a query layer itself | Poor — MTU pricing, expensive fast | Partial — enterprise compliance, no residency by self-hosting | Partial |
| **Mixpanel** | Good — explicit consent-aware merge flag | Poor — SaaS only; opt-in EU residency (Netherlands) | Good — official SDK | Poor | Partial — export APIs, no in-place SQL/join | Partial — moderate at low volume, scales up | Good EU-residency nuance, no self-host ownership | Partial |
| **Amplitude** | Good | Poor — SaaS only; EU residency paywalled, CLOUD Act caveat noted | Good — official SDK | Poor | Partial — export/warehouse connectors, extra hop | Poor — enterprise-scale pricing quickly | Partial — paywalled EU residency | Partial |
| **June** | — | — | — | — | — | — | — | **Defunct (wound down July 2025, migrating to Amplitude)** |

---

## Verdict

No single off-the-shelf tool is a slam-dunk "just buy it" answer once you weight self-hosting/data
ownership, multi-site segmentation, and "implement once, reuse everywhere" as heavily as the brief
does — every SaaS-only tool (Segment, Mixpanel, Amplitude) trades away real data ownership, and every
OSS tool (PostHog, RudderStack, Jitsu) either has operational weight (PostHog OSS) or a thinner
Python/Django story (Jitsu) or no analytics UI at all (RudderStack OSS).

**Recommendation**: Build the thin first-party capture layer (Section "The hybrid option") as the
reusable core — this alone satisfies every hard constraint using nothing but our own Postgres, and is
genuinely a pip-installable "implement once" Django app usable across all downstream projects with
zero external dependency or vendor cost. Then treat **PostHog** (EU Cloud, to avoid our own
self-hosting burden) as the *recommended optional sink* for any downstream project that later wants a
real analytics UI/dashboard on top of the same event stream — its identify/merge model, UTM capture,
EU residency, deletion API, and genuine SQL/join layer over the same events are the best combination in
this lane, and its Python SDK is trivial to wire in as a second sink without touching call sites.
**RudderStack OSS** is the fallback if a downstream project specifically wants to self-host the sink
rather than depend on any SaaS at all (its warehouse-native model even lets that sink literally be the
same Postgres table our local sink already writes to). Do not adopt Segment, Mixpanel, Amplitude, or
Jitsu as the primary path for this feature — Segment/Mixpanel/Amplitude are poor fits on ownership and
cost, Jitsu is a weak Python/Django fit, and June is defunct.

## References
- PostHog Django library: https://posthog.com/docs/libraries/django
- PostHog self-host: https://posthog.com/docs/self-host
- PostHog OSS support policy: https://posthog.com/docs/self-host/open-source/support
- PostHog identify/alias: https://posthog.com/docs/product-analytics/identify
- PostHog GDPR compliance: https://posthog.com/docs/privacy/gdpr-compliance
- PostHog group analytics: https://posthog.com/docs/product-analytics/group-analytics
- PostHog SQL access / HogQL: https://posthog.com/docs/sql
- PostHog data warehouse joins: https://posthog.com/docs/data-warehouse/join
- PostHog UTM segmentation: https://posthog.com/docs/data/utm-segmentation
- PostHog pricing: https://posthog.com/pricing
- Segment overview/pricing: https://cdp.com/articles/what-is-twilio-segment/ , https://www.twilio.com/en-us/pricing/customer-data
- RudderStack Python SDK: https://www.rudderstack.com/docs/sources/event-streams/sdks/rudderstack-python-sdk/
- RudderStack Open Source: https://www.rudderstack.com/docs/get-started/rudderstack-open-source/
- RudderStack warehouse-native architecture: https://www.rudderstack.com/learn/customer-data-platform-cdp/warehouse-native-architecture-operating-model/
- RudderStack pricing: https://www.rudderstack.com/pricing/
- Jitsu GitHub: https://github.com/jitsucom/jitsu
- Jitsu HTTP API: https://jitsu.com/docs/sending-data/http
- Mixpanel EU residency: https://docs.mixpanel.com/docs/privacy/eu-residency
- Mixpanel GDPR: https://docs.mixpanel.com/docs/privacy/gdpr-compliance
- Amplitude data residency/CLOUD Act discussion: https://amplitude.com/blog/data-residency-and-privacy
- June wind-down announcement: https://www.june.so/blog/a-new-chapter
- June/Amplitude HN discussion: https://news.ycombinator.com/item?id=44502506

status: ok
