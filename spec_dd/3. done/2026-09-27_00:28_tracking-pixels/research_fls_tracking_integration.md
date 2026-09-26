# Research: how GA4/Google Ads are wired today, and what Meta/TikTok pixels would touch

Scope: codebase-only research to support the "tracking-pixels" idea (Meta and TikTok pixels, various
pages, conversion types "just like Google Ads"). No implementation checklist; this lays out what
exists, what the idea builds on, and the open options — it does not choose between them.

## 1. How the event queue, context processor and templates work today

Everything lives in `freedom_ls/google_tag/` (app label `freedom_ls_google_tag`, depends only on
`base` — `docs/app_structure.md:97,221`). Four moving parts:

- **`events.py`** — `GoogleAnalyticsEvent` (a `StrEnum`: `SIGN_UP`, `COURSE_ACCESS_REQUESTED`,
  `COURSE_REGISTERED`, `COURSE_STARTED`, `COURSE_COMPLETED`, `GENERATE_LEAD`) and
  `record_google_analytics_event(request, name, params)`. A view calls this; it validates the name/
  param names against **GA4's own naming rules** (`_NAME_PATTERN`, `_RESERVED_PREFIXES`,
  `_RESERVED_PARAMETER_NAMES`, `_MAX_VALUE_LENGTH = 100`) and appends a `{name, params}` dict to a
  session list keyed `GOOGLE_ANALYTICS_EVENTS_SESSION_KEY = "google_analytics_events"`. It is a
  **one-shot queue**: the same request can be a bare unit-test request with no session (handled), and
  `record_google_analytics_event` no-ops if `freedom_ls.google_tag` isn't installed (`events.py:70`).
- **`context_processors.py::google_tag_config`** — pops the session queue once per render via
  `pop_google_analytics_events`, attaches each event's Google Ads `send_to` (from
  `google_ads.conversion_send_to`), and exposes `google_analytics_events` as a lazy callable (so a
  render that never reaches the events partial leaves the queue for the next page — HTMX partials,
  emails, token-bearing pages). Also exposes `google_analytics_measurement_id`,
  `google_ads_conversion_id`, and the hard-coded `CONSENT_MODE_DENIED_REGIONS` tuple (EEA + UK + CH).
- **Templates** — `partials/google_analytics.html` (loader + `gtag('consent', 'default', …)` +
  `gtag('config', ga_id, …)` + `gtag('config', ads_id)`, included once in `<head>` via
  `_base.html:90-92`'s `{% block google_analytics %}`) and `partials/google_analytics_events.html`
  (emits `gtag('event', name, params)` + optional `gtag('event', 'conversion', {send_to})`, a
  self-removing `<script>` per event). The events partial is included **twice** — inside
  `#interface-main` (`_base_interface.html`) and before `</body>` (`_base.html`) — so whichever swap
  point renders first pops the queue and the other renders nothing; this is what makes events survive
  `hx-boost` partial swaps (course player Previous/Next/Finish).
- **`google_ads.py`** — `parse_conversion_labels` (parses
  `GOOGLE_ADS_CONVERSION_LABELS="event=label,…"` at settings-build time, no Django model imports) and
  `conversion_send_to(conversion_id, labels, event_name)` → `"AW-ID/LABEL"` or `None`. This is the
  **Ads-label mapping**: an event with no label sends no conversion; Ads rides entirely on the GA4
  loader (`checks.py` W001/W002 warn if the two settings are set inconsistently).

Where events are recorded across the tree: `freedom_ls/course_access/google_analytics.py` (the
course funnel — `record_interest_expressed`, `record_application_submitted`,
`record_course_self_registered`, `record_course_started`, `record_course_completed`, all wrapping
`record_google_analytics_event` with `course_event_params(course)` = `course_slug`, `course_id`,
`access_type`), and `freedom_ls/accounts/allauth_account_adapter.py:147` (`record_sign_up` on
account creation). Nothing else calls the recorder in-tree; `docs/how tos/google-analytics-and-ads.md`
documents `generate_lead` as the hook for a downstream project's own lead form.

**Is this platform-neutral enough to reuse?** The event *names* and *parameters* are already
platform-neutral in intent — the module docstring (`events.py:1-17`) says event names describe
"funnel moments every course access backend shares," and the how-to explicitly frames `sign_up`,
`course_registered`, `generate_lead` etc. as things Ads imports as conversions. Nothing about
`sign_up` or `course_registered` is Google-specific in meaning. But the **validation rules are GA4's,
not generic**: `_NAME_PATTERN` (40 chars, must start with a letter), `_RESERVED_PREFIXES` (`ga_`,
`google_`, `firebase_`), `_RESERVED_PARAMETER_NAMES` (`user_id`, `session_id`, `currency`, `uid`,
`cid`, `customer_id`) and `_MAX_VALUE_LENGTH = 100` are all pulled from GA4's own naming/collection
limits (cited in the prior spec's `research_event_taxonomy.md` §7), not from Meta's or TikTok's rules
(Meta's Pixel/CAPI events have their own vocabulary — `Lead`, `CompleteRegistration`,
`Purchase` — and TikTok Events API has a third). A shared recorder would need to either (a) keep GA4's
rules as the strictest common denominator and just also fan the same `{name, params}` out to Meta/
TikTok mappings, or (b) decouple validation from any one platform's limits. And the *identifiers* are
unambiguously Google-specific: `GoogleAnalyticsEvent`, `record_google_analytics_event`,
`GOOGLE_ANALYTICS_EVENTS_SESSION_KEY`, the app name `google_tag`, the session key string
`google_analytics_events` (asserted against literally in ~10 test files across
`course_applications`, `course_interest`, `learner_interface`, `accounts`, `google_tag` itself — see
grep results below). Renaming any of those to something neutral is a breaking change to every one of
those tests and to the public API the how-to doc already tells downstream projects to call
(`record_google_analytics_event(request, GoogleAnalyticsEvent.GENERATE_LEAD, …)` is in
`docs/how tos/google-analytics-and-ads.md:229-236` as the documented extension point).

## 2. Where Meta/TikTok support could live — options, not a pick

**A. Extend `google_tag` in place.** Add `META_PIXEL_ID`/`TIKTOK_PIXEL_ID` settings and a second (and
third) `conversion_send_to`-style mapping inside the existing app, reusing the same session queue and
the same two include points. Cheapest to build — the queue, the dedupe-by-whole-dict logic, the
`_base_interface.html`/`_base.html` double-include dance, and the `analytics_enabled` gate are all
solved problems here. Cost: the app's name and its public function name become misleading —
`google_tag.record_google_analytics_event` firing a Meta pixel event reads wrong at every call site,
and a project that wants GA4 off but Meta on (or vice versa) can no longer do so by leaving one app
out of `INSTALLED_APPS`, which is the mechanism `docs/how tos/google-analytics-and-ads.md:221-223`
documents today ("A project that wants neither GA4 nor Google Ads leaves `freedom_ls.google_tag` out
of `INSTALLED_APPS`"). Bundling Meta/TikTok in removes that per-vendor opt-out.

**B. New sibling app(s) per platform** (`meta_pixel`, `tiktok_pixel`, or one `ad_pixels` app covering
both). Each depends on `base` the way `google_tag` does, and each can be left out of
`INSTALLED_APPS` independently — preserving the existing per-vendor opt-out contract. The event
*names* (`GoogleAnalyticsEvent.SIGN_UP` etc.) would need to move somewhere both `google_tag` and the
new app(s) can import without a circular or optional dependency — either up into `base` (or a small
shared "marketing events" module) or kept in `google_tag` with the new apps depending on `google_tag`
for the enum only. `course_access/google_analytics.py` and `allauth_account_adapter.py` would then
call into whichever module owns the shared vocabulary, once per platform, or into one fan-out function
that calls each installed platform's recorder — the second implies a small registry (which platform
apps are installed) rather than a hard import.

**C. A generic "tracking"/"marketing tags" layer above per-platform apps.** One shared queue + shared
platform-neutral event vocabulary + validation, with GA4, Ads, Meta and TikTok each a thin adapter
that reads the queue and knows its own `send_to`-equivalent mapping and its own naming limits. This is
option B taken further: it fixes the GA4-specific-validation problem in §1 by making validation
pluggable per adapter, and it's the shape that scales best if a fourth platform arrives later. Cost:
biggest change, including probably renaming/relocating `google_tag`'s current internals, which is the
option least consistent with "don't build what's not asked" — the idea only asks for Meta and TikTok
today, and event-name portability is already good enough (§1) that a full abstraction layer may be
solving a problem that hasn't arrived yet.

All three options can preserve the deployment's `INSTALLED_APPS` opt-out for GA4 vs. Ads vs. Meta vs.
TikTok independently **only if** each platform's recording/rendering lives in its own app (B or C);
option A collapses Google's and Meta's/TikTok's on/off switches into one.

## 3. "Various pages" — what exists, and whether ad pixels belong everywhere

The GA4/Ads loader (`partials/google_analytics.html`) is included exactly once, in `_base.html`'s
`{% block google_analytics %}` (`_base.html:90-92`), which every full page in FLS extends directly or
via `_base_interface.html` (`{% extends "_base.html" %}`, `_base_interface.html:1`). That covers:

- The public catalogue and course detail pages, and any developer-authored landing page
  (`docs/how tos/landing-pages.md`) — these can additionally set `content_group="landing_page"` by
  overriding the block (documented pattern, `google-analytics-and-ads.md:244-257`).
- Learner-facing course content (`learner_interface`, which extends `_base_interface.html` per the
  app dependency graph and is where `course_started`/`course_completed` fire).
- Educator interface pages (`educator_interface/templates/educator_interface/interface.html` extends
  `_base_interface.html` too), i.e. **staff browsing their own cohorts and learner progress also loads
  the GA4/Ads tag today.**
- Everything **except** the two allauth token-bearing routes (`account_confirm_email`,
  `account_reset_password_from_key`), gated by `analytics_enabled` (`deployment/context_processors.py`
  `TOKEN_BEARING_URL_NAMES`).

So today there is **no existing distinction** in FLS between "public marketing surface" and
"authenticated learner/staff surface" for analytics — one gate (`analytics_enabled`) covers
(almost) everything, and GA4 + Ads load site-wide. The idea's "various pages" for Meta/TikTok could
mean the same blanket approach, or could mean something narrower — landing pages and the signup/
application funnel only, deliberately excluding the course player and educator interface. That is a
real privacy fork the research surfaces rather than resolves: Meta and TikTok pixels are more
explicitly tied to cross-site retargeting/ad-audience building than GA4's own tag (which FLS already
runs with Google Signals *off* and ads personalisation *off*, per the prior spec's operator-setup
section), so firing a Meta/TikTok pixel on every authenticated page a learner or educator visits is a
materially different exposure than firing it only on the public pages an anonymous ad-click lands on.
`docs/how tos/landing-pages.md` already draws the FLS-owns/project-owns line for landing pages
themselves (FLS owns `_base.html`'s head blocks and the deferred-login CTA flow; the project owns the
page). Whichever option in §2 is chosen, the *page scope* question (all pages vs. a `content_group`-
style subset vs. an explicit landing-page-only include) is separate from the *app-location* question
and needs its own decision.

## 4. Configuration model today, and multi-site deployments

`google_tag/config.py`'s `GoogleTagSettings(AppSettings)` declares `GOOGLE_ANALYTICS_MEASUREMENT_ID`,
`GOOGLE_ADS_CONVERSION_ID`, `GOOGLE_ADS_CONVERSION_LABELS` — all read from Django settings (i.e.
environment variables per `docs/how tos/google-analytics-and-ads.md` §4), via the shared
`AppSettings`/`Setting` machinery in `freedom_ls/base/app_settings.py`. This is **one measurement ID,
one Ads ID, one label map per deployment process** — not per `Site`. `google-analytics-and-ads.md:47`
says so explicitly: "The measurement ID and Ads ID are set once per FLS deployment. Every site that
deployment serves shares one GA4 property and one Ads account. Sites are told apart by the Hostname
dimension." `docs/product/multi-tenancy-and-isolation.md` confirms FLS is multi-site-capable
(`Per-Site Configuration` section) and that **other** cross-cutting config, e.g. webhook endpoints and
secrets (`docs/product/webhooks.md:48`, "Named secret values... can be stored per site"), already
*is* modelled per-`Site` as DB rows rather than env vars, precisely because different sites/tenants
need different credentials. Meta and TikTok pixel IDs are the same shape of problem: if a downstream
deployment runs several sites/brands that advertise separately, a single deployment-wide env var
pixel ID (matching today's GA4/Ads pattern) means every site's traffic reports into one Meta/TikTok
ad account, indistinguishable except by whatever URL/UTM dimension the ad platform itself exposes —
whereas a per-`Site` model (matching the webhooks pattern) lets each site carry its own pixel ID(s).
This is an open trade-off to flag, not resolve: env-var-per-deployment is less work and matches GA4/
Ads exactly; per-site DB config matches webhooks' existing precedent and would matter the moment one
deployment runs multiple advertised brands.

## 5. CSP implications

`config/settings_base.py:500-546` — `SECURE_CSP_REPORT_ONLY` (report-only mode; not yet enforcing) —
already lists per-vendor host groups with inline comments explaining *why* each host is there
(lines 482-499): GA4's loader/collection hosts, PostHog's ingestion+assets hosts, and a distinct block
for **Google Ads'** conversion/remarketing hosts (`googleadservices.com`, `googleads.g.doubleclick.net`,
`pagead2.googlesyndication.com`, `ad.doubleclick.net`, `www.google.com`, plus `www.google.co.za` —
called out specifically because "CSP cannot wildcard the right-hand side of a host" so each visitor-
country TLD Google might call has to be listed by hand, and a deployment targeting a different country
would need to add its own TLD). Meta and TikTok would each need their own such block across
`script-src`, `img-src`, `connect-src` (and `frame-src` if either loads an iframe) — Meta's pixel
calls `connect.facebook.net` (script) and `www.facebook.com`/`*.facebook.com` (collection pixel);
TikTok's calls `analytics.tiktok.com` (both script and collection) — exact hosts need confirming
against each platform's current pixel docs at implementation time, not assumed from this research.

`freedom_ls/base/tests/test_csp.py` is the test pattern to copy: one `django_db`-marked test per
vendor group, hitting `client.get("/")`, parsing the `Content-Security-Policy-Report-Only` header into
a `directive: sources` dict by splitting on `;` then the first space, then asserting specific hosts
are `in` the relevant directive's value string. Three existing tests: a baseline (`default-src 'self'`
present), one naming GA4+PostHog hosts across `script-src`/`img-src`/`connect-src`, and one naming
Google Ads' hosts across `script-src`/`img-src`/`connect-src`/`frame-src`. A Meta/TikTok addition would
add a fourth (and fifth) test in the same shape, naming that platform's hosts.

## 6. Consent handling as it exists

One function decides whether *any* analytics/marketing snippet renders:
`freedom_ls/deployment/context_processors.py::analytics_enabled` — `True` for every URL name except
the two allauth token-bearing ones (`TOKEN_BEARING_URL_NAMES`). Both `partials/google_analytics.html`
and `partials/posthog.html` gate on `{% if analytics_enabled and <platform>_id %}`. The docstring is
explicit that this is the intended extension seam: "A downstream deployment that needs consent gating
adds its own context processor here in place of this one, returning `analytics_enabled` from whatever
consent state it tracks." Google's **Consent Mode v2** is wired only for GA4/Ads today —
`CONSENT_MODE_DENIED_REGIONS` (EEA + UK + CH, hard-coded tuple in `google_tag/context_processors.py`)
feeds `gtag('consent', 'default', {ad_storage: 'denied', ...})` before the first `gtag('config', ...)`
call in `partials/google_analytics.html:26`. This is Google-specific machinery (`gtag('consent', ...)`
is Google's own API) — Meta and TikTok each have **their own** separate consent/limited-data-use
mechanisms (Meta's Limited Data Use flag for CCPA, TikTok's own consent signal parameter) that this
mechanism does not cover and would need separate wiring per platform, not a shared "consent mode."

The prior spec's `research_consent_south_africa.md` (done, `spec_dd/3. done/2026-09-23_11:31_google-
analytics-setup/`) is the operative decision record: for a South-Africa-only deployment, POPIA's
legitimate-interest ground means **no consent banner is required**, and the recommendation there was
explicitly to keep the extension seam (the single `analytics_enabled` boolean) cheap rather than build
a banner — "this GA4 decision should not create a second, differently-shaped instance of the same open
problem" as PostHog's and the referral-tracking cookie's existing no-consent-gate posture. That
research also flags (§3) that a downstream deployment serving EU/UK/Swiss learners would need a real
consent gate covering GA4 **and** PostHog **and** the referral-tracking cookie together "since they are
functionally the same category of problem" — Meta and TikTok pixels would join that same list. Nothing
in-tree currently implements a consent gate; `analytics_enabled` today is unconditional except for the
two token-bearing URLs.

Separately and materially: `freedom_ls/referral_tracking/` (the signup-attribution app) **already
captures `fbclid`** (Meta's click identifier, from the query string, `capture.py:29` `TRACKED_PARAMS`)
and **already reads the `_fbp`/`_fbc` cookies** (Meta's own first-party pixel cookies) directly off
the request at signup time (`capture.py:237-238`, written into `SignupAttribution.fbp_cookie`/
`fbc_cookie`, `models.py:77-78`) — for internal attribution reporting, not for sending anything to
Meta. `docs/product/signup-attribution.md:21,23,36` documents this and already flags it as a privacy
gap: "Reading the Google Analytics and Meta cookies is itself regulated... A banner that covers
analytics does not obviously extend to copying those identifiers into a permanent record held against
a name." So FLS already has Meta-shaped identifiers in the schema and already has an open, documented
consent gap around them — a real Meta Pixel (which would *set* `_fbp` and read/write `_fbc` itself, and
send events to Meta's servers) is a new, additional privacy surface on top of that existing gap, not
an isolated addition.

## 7. Domain vocabulary that applies

- **"Conversion"** is already an FLS term, scoped specifically to the Google Ads mapping:
  `GOOGLE_ADS_CONVERSION_ID`, `GOOGLE_ADS_CONVERSION_LABELS`, `conversion_send_to`,
  `parse_conversion_labels` (`google_tag/google_ads.py`), and the how-to's "Conversions in Google Ads"
  section lists five conversion *moments* (`course_registered`, `course_access_requested`+
  `application`, `generate_lead`, `sign_up`, `course_completed`) each mapped to one Ads "conversion
  action." The idea's "different types of conversions" maps directly onto this existing vocabulary —
  Meta's and TikTok's equivalent concepts (a "Standard Event"/"Custom Conversion" for Meta, an "Event"
  for TikTok) are each platform's own word for the same moment and should be introduced as *that
  platform's* word, attributed, per `domain_vocabulary.md`'s rule for borrowed terms — not silently
  folded into "conversion" as if FLS had one universal name for it.
- **"Event"** — FLS's own word already, but currently spelled `GoogleAnalyticsEvent`/
  `google_analytics_events` (§1). A platform-neutral document should say "event" in prose (matching
  the how-to's own usage, e.g. "Every event from that page…") while being explicit that the *code*
  identifier is Google-scoped until/unless §2 changes that.
- **"Landing page"** is FLS's own term for a public, developer-authored, single-CTA marketing page
  (`docs/how tos/landing-pages.md:3`) — distinct from "catalogue page" or "course page." Any research
  or spec describing pixel placement should use this term precisely rather than "marketing page" or
  "ad page," which aren't used elsewhere in the codebase.
- **First touch / attribution** — `SignupAttribution`, `FirstTouchCount`, `advert_code`,
  `referral_code` (`referral_tracking/models.py`) are the existing nouns for "which campaign/ad
  brought this signup." A Meta/TikTok pixel spec sits adjacent to, but is not the same system as,
  this — the pixel reports events *to* Meta/TikTok for their bidding algorithms and audience-building;
  `SignupAttribution` records the same kind of click IDs *into FLS's own database* for FLS's own
  reporting. Don't conflate "add a Meta pixel" with "extend signup attribution" — they overlap in the
  identifiers they touch (`fbclid`, `_fbp`, `_fbc`) but solve different problems.
- No existing FLS term for "pixel" itself; `google_tag` is the closest existing app-name pattern
  (named for the Google tag it renders, not a generic "analytics" name) — worth noting if §2 picks a
  sibling-app option, since `google_tag`'s own name is already platform-specific rather than a
  precedent for a shared name.

## Sources (in-repo, all read in full for this research)

- `freedom_ls/google_tag/config.py`, `events.py`, `google_ads.py`, `context_processors.py`,
  `checks.py`, `apps.py`
- `freedom_ls/google_tag/templates/partials/google_analytics.html`,
  `partials/google_analytics_events.html`
- `docs/how tos/google-analytics-and-ads.md`, `docs/how tos/landing-pages.md`
- `docs/product/signup-attribution.md`, `docs/product/referral-codes.md`,
  `docs/product/multi-tenancy-and-isolation.md`, `docs/product/webhooks.md`, `docs/app_structure.md`
- `config/settings_base.py` (lines ~480-546, CSP; INSTALLED_APPS/context processors ~107, 200)
- `freedom_ls/base/tests/test_csp.py`
- `freedom_ls/deployment/context_processors.py` (`analytics_enabled`, `posthog_config`)
- `freedom_ls/base/templates/partials/posthog.html`, `freedom_ls/base/templates/_base.html`
- `freedom_ls/course_access/google_analytics.py`, `freedom_ls/accounts/allauth_account_adapter.py`
- `freedom_ls/referral_tracking/models.py`, `freedom_ls/referral_tracking/capture.py`
- `freedom_ls/base/app_settings.py`
- `spec_dd/3. done/2026-09-23_11:31_google-analytics-setup/idea.md`,
  `research_event_taxonomy.md`, `research_consent_south_africa.md`, `research_user_id_and_pii.md`
- `claude_plugins/sdd/resources/domain_vocabulary.md`, `.claude/sdd/config.md`,
  `.claude/skills/domain-glossary/SKILL.md` (no separate `domain-glossary` skill exists under
  `claude_plugins/*/skills/`; the project's copy lives at `.claude/skills/domain-glossary/SKILL.md`
  per `.claude/sdd/config.md`'s Vocabulary Sources)

status: ok
