# Research: multi-platform ad tag patterns (Meta, TikTok, alongside the existing Google Ads tag)

Scope: how other systems architect "several ad platforms' conversion tracking at once," so the
tracking-pixels idea can weigh options rather than default to one. No recommendation, no
implementation checklist. FLS-specific facts (current `google_tag` app) are drawn from
`freedom_ls/google_tag/` and `docs/how tos/google-analytics-and-ads.md`.

## What FLS already does (baseline to compare options against)

- `freedom_ls/google_tag/events.py`: a view calls `record_google_analytics_event(request, name,
  params)`, which validates the name/params and pushes a payload onto a session-backed queue
  (`GOOGLE_ANALYTICS_EVENTS_SESSION_KEY`). Nothing is sent yet.
- The next full-page render includes `partials/google_analytics_events.html`, which pops the queue
  and emits `gtag('event', name, params)` calls — one queue, one JS call form, one destination
  (gtag.js, loaded directly, no Google Tag Manager container).
- `freedom_ls/google_tag/google_ads.py` + `config.py`: `GOOGLE_ADS_CONVERSION_LABELS` is an env var
  parsed once at boot into `{event_name: label}`. `conversion_send_to()` looks up a label for an
  event name and, if found, adds a second `gtag('event', 'conversion', {send_to: 'AW-ID/LABEL'})`
  call alongside the GA4 event. An event with no mapped label sends only the GA4 event.
- Mapping is redeployment-only: changing which events count as Ads conversions means editing the
  env var and restarting, not a marketer action.

This is already "one recorded event, N outbound calls" for N=2 (GA4 event + optional Ads
conversion), both riding the same gtag.js loader. The open question the idea should decide is how
far that pattern extends to Meta's `fbq` and TikTok's `ttq`, which are different JS libraries with
different event vocabularies, not more `gtag` configs.

## Option A — direct per-platform tags in code (extend the current pattern)

Add `fbq('track', ...)` and `ttq.track(...)` calls the same way `gtag` calls are added: a template
partial per platform, each popping (or sharing) the queue, mapping the internal event name to that
platform's vocabulary before firing.

- **Who configures what.** A developer adds a new mapping entry per event/platform in code or in an
  env var, following the existing `GOOGLE_ADS_CONVERSION_LABELS` shape. A marketer cannot add a new
  page or a new conversion mapping without a code change and deploy, unless the mapping table is
  moved out of settings and into the database (see the "who can change mapping" discussion below).
- **CSP.** No `unsafe-eval` needed — `fbq`/`ttq` loader snippets are plain script tags, same shape as
  `gtag.js`. FLS's existing CSP posture (already allowlisting Google's tag domain) just grows to
  allowlist `connect.facebook.net` and `analytics.tiktok.com`.
- **Performance.** Each additional platform is one more script load and one more render-blocking (or
  deferred) tag; no container overhead. This is the cheapest option per platform added, but cost is
  linear in the number of platforms — "just add Meta and TikTok" today doesn't preclude Pinterest,
  Snap, or X pixels being asked for next, and each one is another partial, another queue consumer,
  another CSP entry.
- **Reliability against ad blockers.** Client-side `fbq`/`ttq`/`gtag` are all commonly blocked by the
  same browser extensions and iOS ITP restrictions; none of the three is more resilient than the
  others when fired only from the browser. This is unrelated to whether the tag is inserted directly
  or via GTM — the blocker targets the request domain, not the delivery mechanism.
- **Fit for a reusable OSS package installed into other projects.** This keeps FLS's story simple:
  "install the app, set env vars, get gtag+fbq+ttq." It matches the project's existing convention
  (`AppSettings`/`Setting` pattern in `config.py`, parsed at boot, `ImproperlyConfigured` on a bad
  value) and needs no new dependency or external account (beyond each ad platform's own pixel ID).

## Option B — Google Tag Manager (web container)

Replace direct tags with one GTM container; FLS pushes structured events to a `dataLayer` instead of
calling `gtag`/`fbq`/`ttq` directly, and GTM's web UI fans each `dataLayer` event out to whichever
tags a marketer configures (Meta pixel, TikTok pixel, GA4, Ads conversions, etc.).

- **Who configures what.** This is GTM's core trade-off: once the container exists and FLS emits a
  stable `dataLayer` vocabulary (e.g. `{event: 'course_registered', course_id: ..., access_type:
  ...}`), a marketer can add/remove/re-map destination tags and triggers in the GTM UI without a
  deploy. The cost is moved from "developer edits an env var" to "marketer configures a black box
  that isn't in version control" — GTM containers are typically not source-controlled, so a change
  marketing makes in GTM isn't visible in the FLS repo, isn't code-reviewed, and can silently start
  firing a tag on every page.
- **CSP impact.** GTM's own container loader is a plain script. The friction is specific templates:
  Meta's and TikTok's *official* GTM community templates are well-behaved custom templates, but any
  **Custom HTML tag** (frequently how less-common event mappings or workarounds get added by a
  marketer) needs `'unsafe-inline'`/`'unsafe-eval'`-adjacent CSP allowances because GTM's sandboxed
  JS runtime for community templates uses APIs that some CSP configurations must loosen to permit
  (Incremys' 2026 CSP guide for GTM covers the concrete headers/nonce approach). This is the direct
  tension with FLS's current tight CSP allowlist (currently just `www.google.co.za`).
- **Performance.** One container script load replaces N direct loads, but the container then loads
  each configured vendor tag anyway, plus GTM's own tag-firing overhead; net page weight is
  comparable to Option A for a small number of tags, and better than Option A only once there are
  many tags. For "Meta and TikTok on various pages," the difference to Option A is marginal.
  Reliability against ad blockers is *worse* on average — GTM's own domain (`googletagmanager.com`)
  is a common ad-blocker/uBlock filter list target, so a blocked GTM container blocks everything
  behind it, whereas losing one direct pixel in Option A still leaves the others firing.
- **Fit for a reusable OSS package.** Awkward: GTM requires an external Google account, container ID
  and ongoing GTM-side configuration that lives outside the FLS repo and outside each downstream
  project's Django settings — the opposite of FLS's current "everything is an env var checked into
  the deploy config" model. A downstream project adopting FLS would need its own GTM container and
  its own marketer maintaining it, which is a bigger operational ask than setting three IDs and a
  labels string.

## Option C — server-side GTM / Stape (or another server container)

A second GTM container runs server-side (self-hosted or via a paid proxy service like Stape), and
either receives events forwarded from the browser container or receives events sent directly from
Django. It then calls each platform's *server* API (Meta Conversions API, TikTok Events API, Google
Ads Enhanced Conversions) rather than the platform's browser script.

- **Who configures what.** Same GTM-UI-driven mapping as Option B, plus a second container marketers
  or a specialist agency configures; adds an operational layer (hosting the server container, or
  paying Stape/Taggrs/similar) that a reusable OSS LMS package would be pushing onto every downstream
  deployer, not shipping itself.
- **CSP/performance.** Removes browser-side script weight for whichever tags move server-side, and
  is materially better against ad blockers and Safari ITP, because the request never leaves the
  first-party domain the way a client pixel call does. Stape's and Taggrs' 2026 docs on Meta CAPI
  and TikTok Events API describe this as recovering conversions client-side tracking loses.
- **Deduplication becomes mandatory, not optional.** Every source describing server-side setups
  (Stape's Meta dedup guide, Taggrs' Meta dedup docs, TikTokEvents API) is explicit that a
  browser-and-server pair for the *same* real-world event must carry an identical `event_id`
  (Meta) / event ID (TikTok), generated once and threaded through both paths, or the platform counts
  it twice. TikTok's Events API docs add a specific wrinkle: TikTok requires roughly a 5-minute
  minimum gap between a pixel event and its server-side twin inside a 48-hour dedup window, a detail
  that trips up naive send-both-immediately implementations.
- **Fit for a reusable OSS package.** Heaviest option: needs its own compute/hosting (or a paid
  vendor), its own credentials (Conversions API access tokens are more sensitive than a pixel ID —
  they can create *server-attributed* events for the account), and is the option Google Ads' own tag
  in FLS already sidesteps today by keeping campaign-critical timing conversions (registration, lead)
  entirely client-side and letting only lagging events (application, completion) travel through a
  GA4 import instead.

## Option D — CDP (Segment, RudderStack) as the fan-out layer

Instrument the product once against a CDP SDK (`analytics.track('Course Registered', {...})`); the
CDP's dashboard maps each tracked event to as many configured "destinations" (Meta, TikTok, GA4, Ads,
plus non-ad tools like a data warehouse) as are turned on, without further app-side code.

- **Who configures what.** Closest match to the request "marketing wants to change conversion
  mapping without deploys": RudderStack/Segment explicitly separate the developer's one-time
  event/schema instrumentation from a marketer's destination configuration and per-destination event
  mapping, done in the CDP's own UI. RudderStack additionally offers a "tracking plan" that can
  validate/enforce the event schema, addressing the "events firing inconsistently" complaint at the
  instrumentation layer rather than downstream.
- **Cost and fit for OSS.** This is a paid third-party service (or a self-hosted RudderStack, which
  is itself a nontrivial piece of infrastructure to run) with its own account, API keys and, for
  Segment specifically, usage-based pricing that scales with event volume. For a downstream project
  that just wants "Meta and TikTok pixels," standing up a CDP is a large jump from FLS's current
  zero-extra-infrastructure model (env vars + gtag.js). It is the option best suited to an
  organisation already running (or willing to run) a CDP for reasons beyond ad conversions —
  warehousing, product analytics, other marketing tools — not one adopting it solely for two ad
  pixels.
- **Deduplication/CSP/performance** follow from whichever server- or browser-side connectors the CDP
  uses under the hood for each destination — the CDP doesn't remove the underlying Meta/TikTok
  dedup requirement, it just centralises where the mapping is declared.

## Option E — each platform's own partner/native integration

Meta and TikTok both publish "connect your platform" style partner integrations for e-commerce/CMS
platforms (Shopify, WooCommerce, WordPress) that install their own pixel/CAPI pairing with little
developer effort, as opposed to a generic pixel library a developer wires up by hand.

- **Relevance to FLS.** These exist for platforms with a large installed base and a partner program
  (Shopify's is described below); FLS, as a Django app installed into arbitrary downstream projects,
  has no equivalent surface for Meta/TikTok to build a native partner integration against, so this
  option is not realistically available to FLS itself — it's included here because it is the model
  competing LMS/e-commerce platforms use (see Kajabi/Thinkific below), and it's useful context for
  why those platforms' tracking setup looks turnkey while a Django package's does not.

## Open-source Python/Django reference points

- **django-analytical** (`jazzband/django-analytical`) ships a `facebook_pixel` service alongside
  Google Analytics, Google Ads, and many others, each as an independent Django app/template-tag
  module with its own settings (e.g. `FACEBOOK_PIXEL_ID`, `FACEBOOK_PIXEL_INTERNAL_IPS`) and its own
  template tag inserted into the base template. There is no unified "one event, many providers"
  queue in django-analytical — each service's template tag renders its own snippet independently, and
  the project doesn't appear to model a TikTok pixel at all as of the versions surfaced in search
  (its docs and source cover Facebook Pixel, not TikTok). This is architecturally closest to Option A
  but without FLS's shared event queue: each provider's tag fires independently rather than being
  driven from one recorded-event list.
  (https://django-analytical.readthedocs.io/en/latest/services/facebook_pixel.html,
  https://github.com/jazzband/django-analytical/blob/main/docs/services/facebook_pixel.rst,
  https://github.com/jazzband/django-analytical/blob/main/analytical/templatetags/facebook_pixel.py)
- Smaller single-purpose packages exist per provider (`django-facebook-pixel-code`,
  `django-facebook-capi`, `django-pixels`) rather than one package modelling several providers
  behind a shared event abstraction — reinforcing that "one recorded event fanned out to
  gtag+fbq+ttq" is not a solved pattern already available to pull in; FLS's own `events.py` queue is
  the more novel part of the current design, and extending it to more `fanout` targets is a
  first-party decision either way.
  (https://pypi.org/project/django-facebook-pixel-code/, https://libraries.io/pypi/django-facebook-capi,
  https://djangopackages.org/packages/p/django-pixels/)

## How mature multi-pixel products model this

- **Shopify** runs pixels through a "Web Pixels API" sandbox (Customer events in the admin), with
  two pixel types: app pixels (installed by marketing apps) and custom pixels (added by a developer
  in the admin). Shopify's own docs and third-party commentary flag the exact failure mode this idea
  should watch for: "Multiple custom pixels installed by different apps, all firing the same event...
  represents the classic duplicate pixel problem," with the fix being either consolidating into one
  pixel that fans out to all destinations, or ensuring each pixel targets exactly one vendor — i.e.
  the same one-event-many-destinations-vs-many-pixels-one-destination-each choice this research
  frames as Option A internals.
  (https://help.shopify.com/en/manual/promoting-marketing/pixels/app-pixels,
  https://shopify.dev/docs/api/web-pixels-api,
  https://help.shopify.com/en/manual/promoting-marketing/pixels/overview)
- **Kajabi** (course platform) sends Meta Lead and Purchase events *both* client-side (browser pixel)
  and server-side (Conversions API) for the same action, relying on Meta's own dedup rather than
  choosing one path — i.e. it defaults to Option A + Option C combined for Meta specifically, not a
  single-path answer. TikTok on Kajabi is commonly reached through a third-party connector (Able
  CDP) rather than a first-party Kajabi TikTok integration, i.e. Kajabi's own native support is
  Meta-first, and TikTok support for a course platform is more often bolted on via a
  connector/CDP-style product than shipped natively.
  (https://help.kajabi.com/hc/en-us/articles/1260803892269-Meta-Pixel-Enhancements,
  https://www.ablecdp.com/connect/kajabi-and-tiktok, https://www.ablecdp.com/track/kajabi/tiktok)
- **Thinkific** (course platform) ships a Meta Pixel app that automatically fires a standard
  `Purchase` event (with price and product name) for any order, and documents a manual pattern for
  free-course "registration" conversions: the operator creates a Meta **custom conversion** keyed to
  the URL of the first lesson page and tags it with the `CompleteRegistration` category, rather than
  Thinkific firing a `CompleteRegistration` event itself. This is the concrete precedent for the
  business's "map course registration to CompleteRegistration" expectation — on Thinkific that
  mapping is done entirely in Meta's Events Manager UI by whoever runs the ads account, using a URL
  rule, not by the platform emitting a named event.
  (https://support.thinkific.com/hc/en-us/articles/360030366714-Installing-Meta-Pixel,
  https://support.thinkific.com/hc/en-us/articles/360030367174-Track-Free-Course-Conversions-for-Facebook-Ads,
  https://apps.thinkific.com/apps/facebook-pixel)
- **PixelYourSite** (WordPress plugin, the closest thing to a general-purpose multi-platform pixel
  manager for a non-e-commerce-specific CMS) models Meta, TikTok, Pinterest, Bing and GA/Ads pixels
  each with their own settings panel, fires events via both the browser pixel and (where supported)
  a server-side Conversions API with automatic dedup, and maps its own generic event vocabulary
  (`PageView`, `Lead`, `CompleteRegistration`, `Purchase`, etc., matching Meta's/TikTok's shared
  "standard events" naming) onto each platform's native call, with WooCommerce/Easy-Digital-Downloads
  actions pre-mapped and toggle switches (not per-event free-text mapping) controlling which event
  groups reach which pixel. This is architecturally the most literal precedent for "one internal
  event vocabulary fanned out to fbq/ttq/gtag calls," configured through an admin UI rather than env
  vars or code, aimed at non-developer site operators.
  (https://www.pixelyoursite.com/, https://www.pixelyoursite.com/docs/tiktok-settings-configuration,
  https://www.pixelyoursite.com/docs/creating-custom-events)

## Deduplication specifics worth carrying into design discussions later

- **Meta**: browser pixel (`fbq`) and server Conversions API events for the same real action must
  share an identical `event_id`; Meta's own dedup keys off that ID plus a matching time window.
  Stape's and Optizent's GTM-based walkthroughs both center the setup on one "Event ID" variable fed
  to both the pixel tag and the CAPI tag.
  (https://stape.io/blog/how-to-set-up-facebook-event-deduplication-in-google-tag-manager,
  https://www.optizent.com/blog/how-to-set-up-meta-event-deduplication-meta-pixel-conversion-api-using-google-tag-manager/)
- **TikTok**: same event-ID pairing requirement between pixel and Events API, with an added TikTok-
  specific rule — roughly a 5-minute minimum gap enforced between the two copies of an event inside
  the 48-hour dedup window — that a naive "fire both immediately" implementation would violate.
  (https://stape.io/blog/tiktok-conversion-tracking, https://theadspend.com/blog/tiktok-conversion-tracking,
  https://timhuttonco.medium.com/implementing-tiktok-events-api-e5e3547f8e1c)
- **Google/GA4 interaction the idea should keep in mind, since FLS already has this exact case**:
  the current `docs/how tos/google-analytics-and-ads.md` design explicitly routes each conversion
  moment through *either* an Ads-tag conversion *or* a GA4 key-event import, never both, precisely to
  avoid the double-counting failure mode described generically above ("if your purchase page has both
  an Ads tag and a GA4 tag... the same purchase registers as two conversions"). Any Meta/TikTok
  design that also lets those platforms ingest via a GA4 export or via GTM inherits the same
  either/or discipline, or the same double-counting risk, that FLS's Google Ads doc already solved
  once for Google's own two routes.
  (https://www.ruleranalytics.com/blog/reporting/conversion-duplication/,
  https://www.cometly.com/post/duplicate-conversion-counting-issue)

## Common complaints across sources, independent of which option is picked

- **Double counting**: from stacking client + server events without a shared ID (Meta/TikTok CAPI
  docs above), from the same pixel being installed twice — once in template code, once again via a
  tag manager (BlogPros/Ruler Analytics), and from GA4-vs-Ads-tag import overlap (already solved once
  for Google in FLS's own doc, per above).
  (https://blogpros.com/multiple-tracking-pixels-page/, https://www.ruleranalytics.com/blog/reporting/conversion-duplication/)
- **Events firing on every page / pixel sprawl**: Shopify's own guidance names "multiple custom
  pixels ... all firing the same event" as the classic failure, recommending consolidation to one
  pixel-equivalent per vendor or one shared dispatcher; PixelYourSite's answer is per-event-group
  toggles specifically so an operator can stop a pixel receiving events it shouldn't.
  (https://help.shopify.com/en/manual/promoting-marketing/pixels/app-pixels,
  https://www.pixelyoursite.com/docs/tiktok-settings-configuration)
- **Marketing wanting to change conversion mapping without a deploy**: this is the headline reason
  GTM (Option B) and CDPs (Option D) exist at all — both explicitly move event-to-destination mapping
  into a non-developer UI — set against the cost that the mapping then lives outside the app's
  version control and review process. Thinkific's precedent (mapping done as a URL-rule custom
  conversion inside Meta's own Events Manager, not inside the platform) shows a third path: leave
  mapping entirely on the ad platform's side and have the LMS emit nothing platform-specific at all,
  which needs no in-app mapping mechanism but only works when the qualifying action is identifiable
  by URL/page alone.
  (https://support.thinkific.com/hc/en-us/articles/360030367174-Track-Free-Course-Conversions-for-Facebook-Ads,
  https://www.rudderstack.com/competitors/rudderstack-vs-segment/)
- **CSP/security friction specific to GTM**: custom HTML tags and some community templates need
  looser CSP than a hand-written direct tag would, a recurring complaint distinct from the tags
  themselves.
  (https://www.incremys.com/en/resources/blog/google-tag-manager-csp)

## Sources

- https://django-analytical.readthedocs.io/en/latest/services/facebook_pixel.html
- https://github.com/jazzband/django-analytical/blob/main/docs/services/facebook_pixel.rst
- https://github.com/jazzband/django-analytical/blob/main/analytical/templatetags/facebook_pixel.py
- https://pypi.org/project/django-facebook-pixel-code/
- https://libraries.io/pypi/django-facebook-capi
- https://djangopackages.org/packages/p/django-pixels/
- https://help.shopify.com/en/manual/promoting-marketing/pixels/app-pixels
- https://shopify.dev/docs/api/web-pixels-api
- https://help.shopify.com/en/manual/promoting-marketing/pixels/overview
- https://help.shopify.com/en/manual/promoting-marketing/pixels
- https://help.kajabi.com/hc/en-us/articles/1260803892269-Meta-Pixel-Enhancements
- https://www.ablecdp.com/connect/kajabi-and-tiktok
- https://www.ablecdp.com/connect/kajabi-and-facebook
- https://www.ablecdp.com/track/kajabi/tiktok
- https://support.thinkific.com/hc/en-us/articles/360030366714-Installing-Meta-Pixel
- https://support.thinkific.com/hc/en-us/articles/360030367174-Track-Free-Course-Conversions-for-Facebook-Ads
- https://apps.thinkific.com/apps/facebook-pixel
- https://www.pixelyoursite.com/
- https://www.pixelyoursite.com/docs/tiktok-settings-configuration
- https://www.pixelyoursite.com/docs/creating-custom-events
- https://stape.io/blog/how-to-set-up-facebook-event-deduplication-in-google-tag-manager
- https://www.optizent.com/blog/how-to-set-up-meta-event-deduplication-meta-pixel-conversion-api-using-google-tag-manager/
- https://mdniamul.com/blog/meta-pixel-conversions-api-capi-sgtm-stape/
- https://stape.io/blog/tiktok-conversion-tracking
- https://theadspend.com/blog/tiktok-conversion-tracking
- https://timhuttonco.medium.com/implementing-tiktok-events-api-e5e3547f8e1c
- https://taggrs.io/docs/server-side-tracking/facebook/meta-capi
- https://taggrs.io/docs/server-side-tracking/facebook/event-deduplication
- https://taggrs.io/docs/server-side-tracking/tiktok/events-api
- https://www.incremys.com/en/resources/blog/google-tag-manager-csp
- https://github.com/tiktok/gtm-template-eapi
- https://github.com/tiktok/gtm-template-pixel
- https://www.rudderstack.com/competitors/rudderstack-vs-segment/
- https://www.ruleranalytics.com/blog/reporting/conversion-duplication/
- https://www.cometly.com/post/duplicate-conversion-counting-issue
- https://blogpros.com/multiple-tracking-pixels-page/
- https://www.digitalapplied.com/blog/meta-tiktok-conversions-api-capi-server-side-tracking-2026

status: ok
