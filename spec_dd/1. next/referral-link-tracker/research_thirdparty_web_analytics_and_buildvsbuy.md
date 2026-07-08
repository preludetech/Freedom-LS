# Research: Privacy-First Web Analytics Tools (Matomo, Plausible, Fathom, Umami, GA4) + Build-vs-Buy Synthesis

Scope: this document evaluates page/traffic-analytics tools against FLS's referral-link tracking
requirements, and closes with the build-vs-buy decision framework that ties this lane together with
the product-analytics/CDP lane (PostHog, Segment, RudderStack — not re-analysed here, see that
research file).

## Our constraints, recap

- Referral codes minted externally — we only **observe** `?ref=CODE` + UTM params.
- Track **anonymous** browsing, then **stitch identity** to our own `accounts.User` PK at signup.
- Record **conversion events** (course view, express interest, apply, register, signup) — these are
  server-side application events, not just pageviews.
- **Store-only for now** — no dashboard required, but raw events must be **queryable and joinable**
  with our own Postgres data (users, courses, registrations).
- **Multi-site** (`django.contrib.sites`) segmentation.
- **GDPR/ePrivacy**, EU/UK data residency, self-hosting/data-ownership preferred.
- **Reusable** across multiple downstream Django projects ("implement once, use again and again").

---

## 1. Matomo (self-hosted On-Premise)

**Summary: partial fit.** Best-of-breed in this category for server-side event capture and raw SQL
access, but it is still fundamentally a *visit/action* analytics product bolted alongside your app,
not a table in your own schema.

1. **Referral/UTM/campaign capture — good.** Matomo natively parses `pk_campaign`/UTM parameters and
   referrer URLs into its Referrers reports; this is a core, mature feature.
   [Tracking HTTP API](https://developer.matomo.org/api-reference/tracking-api)
2. **Anonymous→identified linkage & custom server-side events — partial/good with caveats.** Matomo
   has a first-class **User ID** field (`uid` param) you can set once a visitor logs in, and it
   supports **Custom Dimensions** (`dimension{id}`) for arbitrary attributes via the HTTP Tracking
   API — i.e., true server-side tracking with no browser involved. Custom Dimensions could carry our
   internal `User.pk`, code, cohort etc. However, Matomo's "User ID" merges *future* visits under
   that ID; it does not automatically retro-stitch the anonymous pre-signup visitor session into the
   User ID trail — you must call `setUserId` (or send `uid`) and Matomo will link by its own visitor
   ID cookie/fingerprint at the point that ID is first set, which is workable but is an integration
   detail you own, not something Matomo solves for you.
   [Server-side tracking vs client-side](https://matomo.org/blog/2025/07/what-is-server-side-tracking/) ·
   [Custom dimensions guide](https://matomo.org/blog/2026/03/custom-dimensions/) ·
   [User ID + custom dimensions FAQ](https://matomo.org/faq/reports/how-to-use-custom-dimensions-with-the-user-id-for-ecommerce-reports/)
3. **Self-hostable / data ownership / EU residency — good.** Matomo On-Premise is free, MySQL/MariaDB
   backed (a community `matomo-to-pg` sync tool exists but Postgres is not first-class), runs
   entirely on infrastructure you control, so EU residency is trivially satisfiable.
   [matomo-to-pg](https://github.com/betagouv/matomo-to-pg)
4. **Query/joinability with our app data — good, but requires ETL.** Matomo stores raw events in
   `log_visit`, `log_link_visit_action`, `log_conversion`, `log_conversion_item` tables and documents
   direct SQL joins across them, plus a `Live.getLastVisitsDetails` API for full visit/clickstream
   export (JSON/XML/CSV). But this lives in a **separate MySQL database**, not our Postgres — joining
   with `accounts.User`/`courses`/`registrations` means either cross-database federation (FDW,
   ETL sync, or the `matomo-to-pg` project) or exporting via API into our own tables. Not a native
   join.
   [Database schema](https://developer.matomo.org/guides/database-schema) ·
   [Log data guide](https://developer.matomo.org/guides/log-data) ·
   [Raw data export FAQ](https://matomo.org/faq/how-to/faq_24574/) ·
   [SQL query FAQ](https://matomo.org/faq/how-to/how-do-i-write-sql-queries-to-select-visitors-list-of-pageviews-searches-events-in-the-matomo-database/)
5. **Multi-tenant / per-site — good.** Matomo has native multi-site support ("Websites" concept) that
   maps directly onto our `django.contrib.sites` model — one Matomo site ID per FLS site.
6. **Cost & operational burden — good self-hosted cost, moderate ops burden.** On-Premise core is
   free forever; paid plugins for extras (heatmaps €199/yr, session recording €149/yr) are optional
   and irrelevant to our store-only use case. But it's a whole extra service (PHP app + MySQL) to
   deploy, patch, and back up **per downstream project**, unless centralised as one shared Matomo
   instance for all projects (adds its own multi-tenant-of-multi-tenant complexity). Cloud tier
   starts at €29/mo for 50k hits/30 sites if self-hosting ops burden is unwanted.
   [Pricing](https://matomo.org/pricing/) · [Is Matomo truly free FAQ](https://matomo.org/faq/log-analytics-tool/is-matomo-truly-free-to-use-what-are-the-costs-or-requirements/)
7. **Consent/privacy posture — good.** Configurable for cookieless tracking, DNT/GPC respect, IP
   anonymisation, and data minimisation guidance is well documented; GDPR-compliant configurations
   are standard practice.
   [pagemachine/matomo-tracking (consentless)](https://github.com/pagemachine/matomo-tracking)
8. **Reusability across Django projects — partial.** Reusable as *infrastructure* (stand up once,
   point every downstream Django project's tracking calls at it), but not reusable as *our own
   Django app/library* — every project needs the same Matomo HTTP-API integration glue code
   re-written or shared as a small internal package, and the actual referral data still lives outside
   any Django project's own database.

---

## 2. Plausible (self-hosted Community Edition / Cloud)

**Summary: poor-to-partial fit.** Excellent lightweight privacy-first pageview/UTM tool, but weak on
exactly the two things we need most: user-identity linkage and joinable raw storage.

1. **Referral/UTM capture — good.** Standard, well-supported out of the box (Sources/Campaigns
   reports); custom event goals can carry campaign context via custom properties.
   [Custom events](https://plausible.io/docs/custom-event-goals) ·
   [Custom props for custom events](https://plausible.io/docs/custom-props/for-custom-events)
2. **Anonymous→identified linkage & server-side custom events — poor.** Plausible's Events API does
   support server-side pageview/event recording (useful for mobile apps or server-side sends), and
   custom properties can be attached. But Plausible has **no concept of a persistent User ID** you
   can set to stitch anonymous-then-known sessions the way Matomo's `uid` does — its visitor
   identification is deliberately ephemeral (rotating daily salted hash of IP+UA, precisely *because*
   it avoids persistent identifiers for privacy). This is a direct conflict with our "identity
   stitching to `User` PK" requirement — Plausible is architecturally opposed to persistent
   cross-session identifiers.
   [Events API reference](https://plausible.io/docs/events-api)
3. **Self-hostable / data ownership / EU residency — good.** Community Edition is open source,
   self-hostable (Docker), EU (Germany) hosted cloud option available too.
   [plausible/analytics GitHub](https://github.com/plausible/analytics)
4. **Query/joinability — poor.** Self-hosted Plausible stores site/user config in **Postgres** but
   the actual **event data lives in ClickHouse**, a separate columnar store, accessible only via
   `docker exec`+clickhouse-client or the ClickHouse native protocol — no documented supported way to
   join it against an application Postgres database, and full raw-data export from Cloud isn't even
   available yet (open feature request). This is the opposite of "queryable/joinable with our own
   app data."
   [DB access discussion](https://github.com/plausible/analytics/discussions/621) ·
   [Raw ClickHouse export feature request (open)](https://feedback.plausible.io/636)
5. **Multi-tenant / per-site — good.** Multiple sites per instance is native and simple.
6. **Cost & operational burden — good for cost, low ops (lightweight single Docker Compose stack).**
   Cloud: $9/mo (10k pageviews, 1 site) up to $14/mo for 3 sites; self-hosted is free plus hosting
   costs.
7. **Consent/privacy posture — good.** Cookieless by design, no personal data stored, no cookie
   banner legally required in most EU readings — genuinely best-in-class on this axis.
8. **Reusability — partial.** Easy to stand up per project or centrally, but because of point 2 and
   4, it cannot carry the identity-stitching/conversion-event workload we actually need; it would
   only ever be a *supplementary* pageview/UTM dashboard, not the referral-tracking system of record.

---

## 3. Umami (self-hosted OSS)

**Summary: partial fit — the most promising of the "pure analytics" tools for our use case, still
short of a real solution.**

1. **Referral/UTM capture — good.** Standard referrer/UTM capture built in.
2. **Anonymous→identified linkage & server-side custom events — partial, notably better than
   Plausible.** Umami has a genuine **`umami.identify(id)` / Distinct ID** mechanism: you call it
   (client-side or via the `/api/send` server endpoint with an `id` field) after login to tie a
   session to an external identifier such as your own user ID or email, and Umami's Sessions API
   returns `distinctId` alongside session data — this is real, if partial, anonymous→known-user
   stitching support, and closer to what we need than Plausible or Fathom. Umami also supports
   **custom events with arbitrary properties** stored per-event
   (`data-umami-event-*` attributes or API), which can carry conversion-event payloads. However,
   there is an open feature request/issue for more automatic "session linking / identity stitching"
   suggesting the current mechanism is a manual, single-ID tag rather than a full historical-trail
   merge, and distinct-ID filtering in the dashboard itself is still an open feature request too —
   i.e., the write path is fine, associated querying/analysis tooling is immature.
   [Distinct IDs](https://docs.umami.is/docs/distinct-ids) ·
   [Identify logged-in users](https://docs.umami.is/docs/guides/identify-logged-in-users) ·
   [Automatic session linking issue (open)](https://github.com/umami-software/umami/issues/3820) ·
   [Distinct ID dashboard filter feature request (open)](https://github.com/umami-software/umami/issues/3861)
3. **Self-hostable / data ownership / EU residency — good.** Fully open source, self-hosted, you
   control the region entirely.
4. **Query/joinability — good relative to peers.** Crucially, Umami is **PostgreSQL-native** (current
   releases use Postgres as the primary supported DB, not a bolted-on side store), with a documented
   `website_event` table and a separate `event_data` table for custom-event properties, plus a full
   REST API. If we ran Umami against the **same Postgres cluster** as FLS (different schema/database),
   genuine cross-database joins (via `postgres_fdw` or simple application-level correlation on shared
   keys like our `User.pk` passed as the Distinct ID) become realistic — a real advantage over
   Matomo (MySQL) and Plausible (ClickHouse) for a Django/Postgres shop.
   [For Developers](https://umami.is/product/developers)
5. **Multi-tenant / per-site — good.** Native multi-website support per instance.
6. **Cost & operational burden — good.** Free, open source, lightweight single Next.js app + Postgres
   — the lowest operational footprint of the self-hosted options, and it's already Postgres, which
   FLS's own ops team already knows how to run/back up.
7. **Consent/privacy posture — good.** Cookieless, no personal data by default; adding a Distinct ID
   deliberately introduces personal/pseudonymous data so that step still needs a lawful basis/consent
   review, same as anywhere we add a persistent identifier.
8. **Reusability — partial-good.** Of the four analytics tools, Umami is the one whose data model
   (Postgres, `identify()`, custom event properties) is closest to something we could realistically
   wire into multiple Django projects and query directly — but it is still a separate app/schema
   with its own migrations and lifecycle that we don't control, not a Django app we own.

---

## 4. GA4 (Google Analytics 4)

**Summary: poor fit for this project.** Free and powerful for marketing-style attribution, but wrong
on data ownership, GDPR risk, and joinability all at once.

1. **Referral/UTM capture — good.** Google Ads/Analytics-grade attribution modelling is the deepest
   of any tool here.
2. **Anonymous→identified linkage & server-side custom events — good technically, but data isn't
   ours.** The **Measurement Protocol** supports genuine server-side event sends (offline
   conversions, subscription events, etc.) and GA4 supports a real `user_id` field distinguishing
   identified users from `user_pseudo_id` pseudonymous ones, exported to BigQuery in a dedicated
   `user_(#)` table alongside a `pseudonymous_users_YYYYMMDD` table. Functionally this is the
   strongest identity-stitching capability of the four tools.
   [GA4 Measurement Protocol](https://www.ga4audits.com/blog/ga4-measurement-protocol) ·
   [BigQuery Export schema](https://support.google.com/analytics/answer/7029846?hl=en)
3. **Self-hostable / data ownership / EU residency — poor.** Not self-hostable at all; data is
   processed by Google (US entity) regardless of BigQuery export region. This is the crux of the
   problem for FLS.
4. **Query/joinability — good via BigQuery, but outside our infrastructure.** GA4→BigQuery export is
   free and gives full SQL-queryable event tables, genuinely the best "joinable" story of the four —
   *if* you're willing to bring your own Postgres data into BigQuery (e.g. via scheduled export) to
   join there, or export BigQuery data back into Postgres. Either way, the join happens outside our
   own database, with a US-headquartered vendor in the loop, and adds a second data platform
   (BigQuery) to operate.
5. **Multi-tenant / per-site — good.** GA4 properties map cleanly to sites.
6. **Cost & operational burden — free tool, moderate integration burden, real compliance burden.**
   No licensing cost, but every downstream project needs its own GDPR risk assessment, and as of the
   Austrian DSB (Dec 2021) and French CNIL (Feb 2022) rulings, transferring EU personal data to
   Google Analytics was found to violate GDPR Chapter V absent supplementary safeguards; Sweden's IMY
   fined companies (Tele2 €1M, CDON €25k) for the same reason. The 2023 EU-US Data Privacy Framework
   adequacy decision has reduced — but not eliminated — this risk pending expected legal challenges
   ("Schrems III").
   [GDPR rulings summary](https://usercentrics.com/knowledge-hub/google-analytics-and-gdpr-compliance-rulings/) ·
   [European rulings](https://www.dataprotectionreport.com/2022/02/european-rulings-on-the-use-of-google-analytics-and-how-it-may-affect-your-business/)
7. **Consent/privacy posture — partial.** GA4 does not store EU IPs and supports Consent Mode v2
   (cookieless pings + modelling when consent is denied), but it remains a persistent third-party
   identifier system requiring a cookie/consent banner and DPA with Google in virtually every EU
   reading — the opposite of "consent-light" self-hosted alternatives.
8. **Reusability — good technically, poor strategically.** Trivial to add to any Django project (a
   tracking snippet + Measurement Protocol calls), but every downstream project inherits the same
   GDPR exposure and vendor dependency FLS is explicitly trying to avoid ("EU data residency and
   consent-gating matter").

---

## Fathom (bonus / not requested but relevant)

**Summary: poor fit — worth naming only to rule out.** Fathom is a commercial, closed-source, hosted
SaaS product (Frankfurt EU data centres, strong GDPR/PECR/CCPA posture) with API access and custom
events on every plan — genuinely good on privacy posture and simplicity. But the **only open-source/
self-hostable version, Fathom Lite, is abandoned/legacy** (no active development, closed-source
product replaced it), it has no documented raw-data export/DB access story comparable to Matomo's SQL
tables or Umami's Postgres schema, and no user-identity-linkage feature was found. Given FLS's data
ownership and reuse-across-Django-projects goals, current-generation Fathom does not clear the bar;
it is not analysed further.
[Fathom Lite GitHub (unmaintained)](https://github.com/usefathom/fathom) ·
[Fathom Analytics](https://usefathom.com/) ·
[Events docs](https://usefathom.com/docs/events/overview)

---

## Comparison table

| Tool | UTM/referral | Identity stitching to our User PK | Server conversion events | Self-host/EU | Queryable/joinable w/ our DB | Multi-site | Cost/ops | Consent posture | Reuse across Django projects |
|---|---|---|---|---|---|---|---|---|---|
| Matomo | Good | Partial (manual `uid`, no auto retro-stitch) | Good (HTTP Tracking API + Custom Dimensions) | Good (self-hosted, MySQL) | Good but separate MySQL DB, needs ETL/FDW | Good (native) | Free OSS, real ops burden (PHP+MySQL) | Good | Partial (infra reusable, not a Django app) |
| Plausible | Good | Poor (no persistent ID by design) | Partial (Events API, no user linkage) | Good (self-hosted CE) | Poor (ClickHouse, no supported join/export) | Good | Cheap/free, low ops | Best-in-class | Poor for our use case |
| Umami | Good | Partial-good (`identify()`/Distinct ID, immature dashboard tooling) | Good (custom events + properties) | Good (self-hosted, Postgres-native) | Good — Postgres, realistic FDW/API join | Good | Free, lowest ops (Postgres-native) | Good | Partial-good (closest fit of the four) |
| GA4 | Best-in-class | Good (`user_id`/BigQuery) but data leaves our infra | Good (Measurement Protocol) | Poor (Google-hosted, GDPR risk history) | Good via BigQuery, but outside our stack | Good | Free, high compliance burden | Partial | Poor strategically (repeats vendor risk per project) |
| Fathom | Good | Not found | Good (paid SaaS) | Partial (EU hosted, but only as closed SaaS; OSS Lite abandoned) | Poor (no documented DB/export parity) | Good | Paid SaaS per project | Best-in-class | Poor (no viable OSS self-host path) |

**Bottom line on this lane:** none of these five tools natively satisfies "observe-only external
codes → anonymous-to-known identity stitch → server-side conversion events → queryable/joinable with
our own Postgres app data → reusable Django app." Umami comes closest (Postgres-native, has a real
`identify()` primitive, cheap, open source) but is still a separate service/schema we don't control,
and even its identity-stitching is a bolt-on, not a first-class relational join to `accounts.User`.
Matomo is the most mature and complete for raw SQL access and server-side event richness, at the cost
of being MySQL-based and heavier to operate. GA4 and Fathom fail our core data-ownership/GDPR
requirement outright. Plausible fails the identity-stitching requirement by design philosophy.

---

## BUILD-VS-BUY SYNTHESIS

*(This section is the shared deliverable — the companion research lane covers product-analytics/CDP
tools (PostHog, Segment, RudderStack); refer to that document for their scoring. Here we only
reference that category at the level needed for the decision framework.)*

### Decision framework

Map our actual requirement onto a 2x2 of "traffic/pageview analytics" vs. "product analytics/CDP" vs.
"bespoke build," recognising our need is a **narrow but specific relational-data problem**, not a
dashboarding problem:

| Requirement | Page-analytics tool (Matomo/Plausible/Umami/GA4/Fathom) | Product-analytics/CDP (PostHog/Segment/RudderStack) | Bespoke build (first-party Django app) |
|---|---|---|---|
| Observe externally-minted codes + UTM | Strong — this is their core job | Adequate — usually needs custom event wiring | Trivial — a middleware/view reading query params |
| Anonymous→known identity stitching to **our `User` PK** | Weak/partial — bolt-on identifiers (`uid`, Distinct ID), not a real FK | Strong — `identify()`/alias APIs designed for exactly this, but still an external ID space to reconcile against ours | Strong — literally a nullable FK, set at signup, no reconciliation needed |
| Server-side conversion events | Partial-to-good | Good — this is their design centre | Trivial — a Django signal/service call |
| Store-only, queryable/joinable with our Postgres app data | Weak-to-partial (separate DB engine/schema in all 4 self-hosted tools) | Weak (data lives in vendor's warehouse/cloud, export/ETL required) | **Native** — it's already a table in our Postgres, `JOIN` works today |
| Multi-site (`django.contrib.sites`) | Supported as "properties/websites," a parallel concept to ours | Supported similarly, parallel concept | **Native** — reuses our existing `site_aware_models` app/manager |
| EU data ownership/residency, consent-gating | Good if self-hosted (Matomo/Umami/Plausible CE); poor for GA4/Fathom SaaS | Poor-to-partial — most are cloud SaaS (PostHog offers EU cloud/self-host) | **Best** — data never leaves our own infrastructure by default |
| Reuse across many downstream Django projects | Partial — reusable as shared *infrastructure*, but every project re-integrates against an external system/API in its own way | Partial — same issue, plus per-project vendor account/config | **Best** — ship it as an installable Django app (like `site_aware_models`), same model as the rest of FLS's own architecture |
| Effort to stand up | Low (self-hosted Docker stack) to zero (SaaS) | Low-medium (SDK integration) | Medium (own the event pipeline, retention, migrations) |
| Effort to maintain long-term | Ongoing (patch/upgrade a whole extra service, per project or centrally) | Low (vendor-managed) but recurring cost & lock-in | Ours to maintain, but it's simple, well-understood domain logic already inside our own deploy/test/migration pipeline |

### The strongest argument FOR buying (a page-analytics tool or a CDP)

Don't reinvent the genuinely hard, orthogonal parts of this problem: **identity-stitching heuristics
across devices/sessions, event-pipeline durability/ordering/retries at scale, bot filtering, and rich
downstream integrations** (BigQuery, warehouses, marketing tools) are mature, battle-tested in these
products in a way a from-scratch Django app will not be on day one. If FLS's real need ever grows into
"track everything a user does across sessions/devices, with sophisticated funnels and cohort
analysis," that is squarely a CDP's job, not a homegrown table.

### The strongest argument FOR building

For **our specific, narrowly-scoped requirement** — observe an externally-issued code once, store an
attribution event, stitch it to a `User` at signup, and be able to run `SELECT ... FROM
referral_events JOIN accounts_user JOIN student_management_registration` tomorrow with zero ETL — a
first-party Django app wins decisively:

- **Data lives in our own Postgres**, trivially joinable with `accounts.User`, courses, and
  registrations from day one — every one of the five analytics tools researched here requires either
  a separate database engine (MySQL for Matomo, ClickHouse for Plausible), an external API/export
  step, or a third-party cloud warehouse to achieve what a Django `ForeignKey` gives us natively.
- **Zero per-project vendor/infrastructure dependency.** No downstream project needs a Matomo/Umami
  instance, a Google Analytics property and DPA, or a CDP subscription just to record "someone
  arrived via `?ref=X` and later registered."
- **Full control of consent gating** — the app can check FLS's own consent/cookie state before
  writing anything, rather than configuring a third-party product's consent mode and trusting its
  interpretation of GDPR.
- **Trivially reusable exactly the way the rest of FLS already is reusable** — as an installable
  Django app following the same pattern as `site_aware_models` (multi-site awareness built in from
  the start) — "implement once, use again and again across multiple downstream Django projects" is
  literally how FLS itself is distributed.
- **Scope is genuinely small.** We are not building bot detection, session-replay, or a query builder
  — we are building: a view/middleware to capture `ref`+UTM params into a session/cookie, a model to
  store the anonymous event, a signal/service call at signup to backfill the `User` FK, and a service
  call at each conversion point (view/interest/apply/register) to write a conversion row. This is
  a small, well-understood Django app, not a research project.

### Concrete recommendation

**Build a small, reusable, first-party Django app (e.g. `referral_tracking`), not buy a page-analytics
or CDP tool for the store step — with an explicit HYBRID escape hatch for the future.**

1. **Now:** implement a first-party `referral_tracking` app that:
   - Captures `?ref=CODE` + UTM params into an anonymous tracking cookie/session key on first hit
     (middleware or a lightweight view decorator).
   - Stores raw anonymous events in our own Postgres, site-aware via the existing
     `site_aware_models` base/manager, so multi-tenant segmentation is inherited for free.
   - Stitches the anonymous trail to `accounts.User` via a nullable FK, populated at signup.
   - Exposes a small internal API (Python function/service, not necessarily HTTP) for other apps
     (`student_interface`, `student_management`) to record conversion events (course view, express
     interest, apply, register) — called from existing views, no new HTTP surface required.
   - Ships as an installable app so the *next* downstream Django project gets it via `uv add`, exactly
     like the rest of FLS's own distribution model.
2. **Design it with a HYBRID forwarding seam from day one**, even though only local storage is needed
   right now: a thin adapter interface (e.g. a `TRACKING_SINKS` setting or simple pluggable backend)
   that can *optionally* also forward events to Matomo (HTTP Tracking API) or a CDP (PostHog/Segment)
   later, without changing the capture/storage core. This preserves the "don't reinvent identity
   stitching" buy-side argument as an option, without paying its data-ownership cost today, and avoids
   a rewrite if a future project genuinely needs rich funnel/cohort dashboards.
3. **Do not adopt GA4 or Fathom** for this — GA4's GDPR/data-residency risk history and Fathom's lack
   of a viable current self-hosted path directly conflict with the stated EU data-ownership
   requirement.
4. **Do not adopt Plausible** as the system of record — its privacy-by-design rejection of persistent
   identifiers is a direct architectural conflict with "link anonymous trail to a `User` account."
5. **If/when a real dashboard or sophisticated attribution modelling is wanted**, self-hosted
   **Matomo** (richest server-side/API feature set) or **Umami** (Postgres-native, lowest ops burden,
   best joinability of the SaaS-alternatives) are the two reasonable "buy" fallbacks to plug into the
   hybrid forwarding seam — in that order of feature richness vs. Umami's order of
   operational/architectural simplicity.

---

## References

- Matomo tracking/custom dimensions: https://matomo.org/blog/2026/03/custom-dimensions/ , https://developer.matomo.org/api-reference/tracking-api , https://matomo.org/faq/reports/how-to-use-custom-dimensions-with-the-user-id-for-ecommerce-reports/ , https://matomo.org/blog/2025/07/what-is-server-side-tracking/
- Matomo raw data/DB schema: https://developer.matomo.org/guides/database-schema , https://developer.matomo.org/guides/log-data , https://matomo.org/faq/how-to/faq_24574/ , https://matomo.org/faq/how-to/how-do-i-write-sql-queries-to-select-visitors-list-of-pageviews-searches-events-in-the-matomo-database/ , https://github.com/betagouv/matomo-to-pg
- Matomo pricing: https://matomo.org/pricing/ , https://matomo.org/faq/log-analytics-tool/is-matomo-truly-free-to-use-what-are-the-costs-or-requirements/
- Matomo consentless tracking: https://github.com/pagemachine/matomo-tracking
- Plausible events/custom props: https://plausible.io/docs/events-api , https://plausible.io/docs/custom-event-goals , https://plausible.io/docs/custom-props/for-custom-events
- Plausible architecture/DB access: https://github.com/plausible/analytics , https://github.com/plausible/analytics/discussions/621 , https://feedback.plausible.io/636
- Umami identity/API: https://docs.umami.is/docs/distinct-ids , https://docs.umami.is/docs/guides/identify-logged-in-users , https://github.com/umami-software/umami/issues/3820 , https://github.com/umami-software/umami/issues/3861 , https://umami.is/product/developers
- GA4 server-side/BigQuery: https://www.ga4audits.com/blog/ga4-measurement-protocol , https://support.google.com/analytics/answer/7029846?hl=en , https://developers.google.com/analytics/bigquery/basic-queries
- GA4 GDPR rulings: https://usercentrics.com/knowledge-hub/google-analytics-and-gdpr-compliance-rulings/ , https://www.dataprotectionreport.com/2022/02/european-rulings-on-the-use-of-google-analytics-and-how-it-may-affect-your-business/
- Fathom: https://github.com/usefathom/fathom , https://usefathom.com/ , https://usefathom.com/docs/events/overview

---

status: ok
