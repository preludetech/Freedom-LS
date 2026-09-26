# Research: TikTok Pixel for FLS

Scope: the TikTok half of "advertise on Meta and TikTok, track conversions like Google Ads." Meta
Pixel/Conversions API and POPIA consent implications are covered by sibling research files; this one
stays on TikTok. Grounded in how `freedom_ls/google_tag` already works (session-queued one-shot
events, popped by `partials/google_analytics_events.html` on every full render and HTMX swap,
`GOOGLE_ADS_CONVERSION_LABELS` mapping event names to conversion labels) and in
`docs/how tos/google-analytics-and-ads.md`.

## 1. Base code and the three calls that matter

TikTok's Pixel base code (installed once, in `<head>`, same place the Google/PostHog tags live)
defines a `ttq` command queue, exactly like `gtag`/`dataLayer` do, then calls:

```html
<script>
!function (w, d, t) {
  w.TiktokAnalyticsObject=t; var ttq=w[t]=w[t]||[];
  ttq.methods=["page","track","identify","instances","debug","on","off","once","ready",
    "alias","group","enableCookie","disableCookie","holdConsent","revokeConsent","grantConsent"];
  /* ...queues methods until the real script loads... */
  ttq.load=function(e,n){ /* injects https://analytics.tiktok.com/i18n/pixel/events.js */ };
  ttq.load('PIXEL_ID');
  ttq.page();
}(window, document, 'ttq');
</script>
```

- **`ttq.load(pixelId)`** — registers the pixel ID and injects the loader script from
  `analytics.tiktok.com`. One call per pixel ID; a site can load more than one pixel (e.g. one per
  ad account) by calling `ttq.load` again with a second ID, each subsequent event call then needs
  to target the right instance.
- **`ttq.page()`** — fires a `PageView`, the base "did someone land here" signal, closest analogue
  to GA4's enhanced-measurement page view. Called once at load, and TikTok's SDK **already
  auto-fires a new `PageView` whenever the URL changes via the History API** (`pushState`/
  `replaceState`), which is exactly FLS's HTMX boosted-navigation pattern — no manual call needed on
  navigation, but see §3 for why that's a double-firing risk with FLS's own event partial.
- **`ttq.track(eventName, params)`** — the workhorse: fires one of TikTok's *standard events* (see
  §2) or a custom event name, with a params object (`content_id`, `content_type`, `value`,
  `currency`, `description`, etc., none of which map cleanly onto FLS's course/`course_id` params —
  TikTok's schema is retail-shaped).
- **`ttq.identify(params)`** — Advanced Matching (see §5): pass `email`/`phone_number`/
  `external_id` *before* the `track`/`page` calls that follow, so every subsequent event on the page
  carries that identity. Not a one-shot call like `track`; it sets state for the pixel instance.

Sources:
[TikTok Pixel & Events API Setup Guide, Dolphin Analytics](https://www.dolphinanalytics.co.uk/blog/tiktok-pixel-events-setup),
[TikTok Conversion Tracking, Kevinleary.net](https://www.kevinleary.net/blog/tiktok-conversion-attribution-tracking/),
[About single-page application PageView measurement, TikTok Ads Manager](https://ads.tiktok.com/resources/help/article/about-single-page-application-pageview-measurement-for-tiktok-pixel?lang=en).

## 2. Standard events, and how FLS's six map onto them

TikTok's standard events (predefined names TikTok uses for reporting, optimisation and audience
building) fall into two groups relevant here — e-commerce ones FLS won't use, and lead-generation
ones that fit an LMS:

| Group | Event codes |
| --- | --- |
| E-commerce | `AddPaymentInfo`, `AddToCart`, `AddToWishlist`, `Download`, `InitiateCheckout`, `Purchase`, `Subscribe`, `ViewContent` |
| Lead generation | `ApplicationApproval`, `CompleteRegistration`, `Contact`, `CustomizeProduct`, `FindLocation`, `Schedule`, `StartTrial`, `SubmitApplication`, `SubmitForm` |
| Both | `Search` |

(Source: [Standard Events and Parameters, TikTok Ads Manager](https://ads.tiktok.com/help/article/standard-events-parameters?lang=en).)

Mapping FLS's six GA4 events (from `docs/how tos/google-analytics-and-ads.md`) onto this set, the
fit is uneven — TikTok's vocabulary was built for shops and lead-gen landing pages, not course
funnels:

| FLS event | Closest TikTok standard event | Fit |
| --- | --- | --- |
| `sign_up` | `CompleteRegistration` ("signs up for something such as account registration") | Good — near-exact match |
| `course_access_requested` (`request_kind=application`) | `SubmitApplication` ("application submitted... for offerings like programs") | Good — this is a better native fit than GA4's own setup, which has to synthesise a `course_application_submitted` custom event via a matching condition because GA4 has no separate "application" event at all |
| `course_access_requested` (`request_kind=interest`) | `SubmitForm` or `Contact` | Loose — "interest" registration isn't quite a form submission or a contact request; either works as a stand-in, neither is exact |
| `course_registered` | No good standard event. `CompleteRegistration` is already spent on `sign_up`; reusing it here blurs "made an account" and "registered for a course" into one optimisation signal, which is a materially worse funnel than the Ads-tag/GA4-import split FLS already runs for Google | Poor — likely needs a **custom event** (e.g. `CourseRegistration`), see below |
| `course_started` | `ViewContent` ("views a specific page... TikTok recommends measuring pages important to your business") | Reasonable — a course's first page is exactly this |
| `course_completed` | No standard event exists for "finished a course" | Poor — custom event, and TikTok has nothing like GA4's arbitrary custom-event names; see below |
| `generate_lead` | `SubmitForm` (or `Contact`, depending on the form) | Good |

**Custom events.** TikTok lets an advertiser register arbitrary custom event names in Events
Manager and use them the same way as standard events, including as optimisation/conversion goals in
Ads Manager. The catch: TikTok's own guidance and third-party write-ups consistently recommend
*standard* events for algorithm learning and eligibility for certain bidding/optimisation goals over
custom ones, because standard events carry the semantic meaning TikTok's ranking models were trained
against; a custom `CourseRegistration` or `CourseCompleted` event works, but starts with less signal
to learn from than `CompleteRegistration` or `SubmitForm` would. This is the mirror image of the GA4
situation, where FLS already accepts an under-standard mapping (`course_access_requested` overloading
one event for two different `request_kind`s) — TikTok will need at least one and probably two of its
own compromises, in the other direction (custom events where GA4 gets to use its own funnel-shaped
built-ins).

Sources:
[Standard Events and Parameters](https://ads.tiktok.com/help/article/standard-events-parameters?lang=en),
[About Custom Events in TikTok Ads Manager](https://ads.tiktok.com/help/article/custom-events?lang=en).

## 3. SPA / HTMX considerations

TikTok's pixel **auto-detects History API navigation and fires its own `PageView` on every URL
change**, by design, "aligning with industry standard practices... no additional setup is required."
That is a direct parallel to FLS's HTMX-boosted navigation (which changes the URL via `pushState`
without a full load) — good news in that TikTok's `PageView` counting should just work without FLS
code, but it means FLS must **not** also call `ttq.page()` manually on every HTMX swap, or every
boosted navigation double-counts a page view. GA4 has the equivalent setting already turned on
("Page changes based on browser history events") for the same reason; TikTok's is on by default with
no toggle mentioned in the docs found.

The one-shot *conversion* events (`sign_up`, `course_registered`, etc.) are a different story from
page views, and map onto exactly the mechanism `google_tag/events.py` and
`partials/google_analytics_events.html` already solve: a view records the moment something happened
in the session queue; the next render — full page or HTMX partial, whichever gets there first —
emits the `ttq.track(...)` call once and removes its own `<script>` tag so a browser Back navigation
to htmx's cached history snapshot doesn't refire it. That plumbing is event-name-agnostic already
(`record_google_analytics_event` takes any string), so a TikTok-specific event stream would either
reuse the same queue (emit both a `gtag('event', ...)` and a `ttq.track(...)` from the same popped
payload) or run a parallel queue — a design decision, not a research finding, and one for the idea
document rather than this file.

Sources:
[About single-page application PageView measurement, TikTok Ads Manager](https://ads.tiktok.com/resources/help/article/about-single-page-application-pageview-measurement-for-tiktok-pixel?lang=en).

## 4. Events API (server-side)

TikTok's Events API is the server-to-server counterpart to the pixel, analogous in purpose to Meta's
Conversions API and to nothing Google Ads currently needs from FLS (the Ads tag setup is
browser-only). As of 2026, TikTok's own guidance and the agency/tooling ecosystem around it treat
**hybrid tracking — pixel *and* Events API together, deduplicated — as the recommended baseline**,
not server-only and not browser-only:

- **Deduplication.** Both calls carry the same `event_id`; TikTok merges duplicates that share an
  `event_id` and arrive within roughly a five-minute window, so a pixel `track` and a server-side
  `track` for the same real-world event count once. This mirrors why FLS's Google Ads tag events
  fire from the render, not the view — the server-side half of a TikTok integration would need the
  view (which already knows the event happened) to generate and pass through the same `event_id`
  that the browser call uses, which is a new plumbing requirement FLS's current queue doesn't carry
  (today's queue stores event name + params, not an id shared between two separate transports).
- **What the Events API payload wants**, to reach TikTok's recommended Event Match Quality (EMQ)
  score of 8.0+: hashed email, hashed phone, `ttclid` (TikTok's click ID, read from the landing
  URL's query string and persisted, typically in a first-party cookie, then replayed server-side),
  the `_ttp` cookie value (an anonymous browser ID the pixel SDK sets itself), client IP address,
  User-Agent, and optionally `external_id`. Access is via a long-lived **access token** generated per
  pixel in TikTok Events Manager, sent as a header on server calls — a secret to store the same way
  FLS stores other credentials (environment variable, never hardcoded, per `CLAUDE.md`).
- **Cost/complexity vs. browser-only.** Pixel-only capture is reported around 65% of true
  conversions once ad blockers, iOS ATT, Safari ITP and consent banners are accounted for; adding a
  deduplicated server-side leg is reported to lift that toward ~95%. The complexity cost is real
  though: a server-side call needs the `ttclid`/`_ttp` values, which only exist in the browser, so
  the browser must at minimum still run a thin capture-and-cookie step even in a "server-side"
  design — there's no such thing as pixel-free tracking that still identifies which ad click led to
  the conversion. For FLS specifically, `course_registered`, `course_started` and `course_completed`
  already happen server-side in a Django view (unlike Meta/Google leads which often start client-side
  in a form), so the raw event capture is actually easier for FLS than the general case; the added
  cost is entirely the `ttclid`/`_ttp` plumbing and the access-token secret, not detecting the event.

Sources:
[About Events API, TikTok for Business](https://ads.tiktok.com/help/article/events-api),
[TikTok event deduplication in SST, TAGGRS](https://taggrs.io/docs/server-side-tracking/tiktok/event-deduplication),
[TikTok Events API: Server-Side Tracking Guide 2026, Benly](https://benly.ai/learn/tiktok-ads/tiktok-ads-events-api-setup),
[TikTok Pixel & Tracking: Setup, Events API and EMQ Guide (2026), MBAdv](https://www.mbadv.agency/tiktok-ads/pixel-and-tracking),
[TikTok Ads Tracking Accuracy, Cometly](https://www.cometly.com/post/tiktok-ads-tracking-accuracy).

## 5. Advanced Matching and the PII question

Advanced Matching is TikTok's name for sending hashed personal identifiers (email, phone,
`external_id`) alongside events via `ttq.identify()` (client-side) or the Events API payload
(server-side), so TikTok can match a conversion to a known TikTok user even when the click ID or
cookie is lost. TikTok offers two modes:

- **Automatic Advanced Matching** — the pixel scans form fields on the page itself and hashes
  whatever it finds (email/phone inputs) without the developer writing identify calls.
- **Manual Advanced Matching** — `ttq.identify({ email, phone_number, external_id })`, called before
  the event calls that follow; email and phone can be passed raw (TikTok hashes with SHA-256
  client-side, industry-standard practice, before the value leaves the browser) or pre-hashed by the
  developer.

**This is the single biggest tension with how FLS is currently documented.**
`docs/how tos/google-analytics-and-ads.md` states plainly: "No email, name or phone number is sent
anywhere." That constraint is a deliberate FLS-wide privacy stance, not an oversight — GA4/Google Ads
work fully without it because the Ads tag and GA4 key event import both operate on click IDs and
session identity alone. TikTok's own EMQ guidance, by contrast, treats hashed email/phone as the
top-weighted inputs to match quality; a TikTok integration that stays consistent with FLS's existing
"no PII, anywhere" line would have EMQ built only from `ttclid`, `_ttp`, IP and User-Agent, which
TikTok's documentation treats as a lower-quality but still functional signal set — automatic advanced
matching would need to be switched **off**, since it actively hashes and sends whatever it finds in
page forms without a developer decision point. Whether FLS decides to hold that line for TikTok too,
or make a deployment-level exception (FLS *does* collect email at signup, so the data exists — the
current choice is not to transmit it to any ad platform) is a decision for the idea document, not a
finding here; TikTok's own guidance flags manual (not automatic) matching as the appropriate choice
for anyone in "regulated or sensitive" categories, which South African POPIA context (see §7) plausibly
puts a learner-data platform into regardless.

Sources:
[Advanced Matching for Web, TikTok Ads Manager](https://ads.tiktok.com/help/article/faqs-for-advanced-matching-for-web),
[How to set up Automatic Advanced Matching, TikTok Ads Manager](https://ads.tiktok.com/help/article/how-to-set-up-automatic-advanced-matching?lang=en),
[TikTok Advanced Matching: A Comprehensive Overview 2026, AdNabu](https://blog.adnabu.com/tiktok/tiktok-advanced-matching/),
[The TikTok Pixel Under Fire: Advanced Matching Vulnerabilities and the 2026 Social Privacy Backlash, cookie-script.com](https://cookie-script.com/news/tiktok-pixel-under-fire-navigating-advanced-matching-vulnerabilities).

## 6. TikTok ads in South Africa

TikTok Ads Manager serves South Africa as an available ad location, with the usual placement types
(In-Feed, TopView, Spark Ads, Collection Ads) and a low posted minimum daily budget; South African
sources put reach at roughly 15 million monthly users. Education is a recognised interest/behaviour
targeting category ("promote online or in-person educational institutions"), and education-flavoured
and behind-the-scenes content is reported to perform reasonably in the South African market. No
South-Africa-specific restriction on education advertisers was found; the general restrictions found
were country-list restrictions on unrelated categories (e.g. certain product-demonstration ad formats
listed South Africa among several countries where that specific format isn't allowed) and the
platform-wide youth-safety policy that applies everywhere TikTok serves ads (landing pages must be
appropriate for the platform's teen audience, and advertisers must follow child-safety law in every
market they target) — relevant to FLS in that any course-advertising creative or landing page needs
the same "safe for a teen audience" bar TikTok applies globally, not a South-Africa-only rule.

Sources:
[TikTok Advertising in South Africa: A Complete Guide for 2026, Juicy Designs](https://www.juicydesigns.co.za/blog/tiktok-advertising-south-africa/),
[About Location Targeting, TikTok Ads Manager](https://ads.tiktok.com/help/article/location-targeting?lang=en),
[Teen Safety and Wellbeing, TikTok Advertising Policies](https://ads.tiktok.com/help/article/tiktok-ads-policy-youth-safety),
[Ad Format and Functionality, TikTok Advertising Policies](https://ads.tiktok.com/resources/help/article/tiktok-ads-policy-ad-format-and-functionality).

## 7. Consent

TikTok's pixel exposes three consent methods on the same `ttq` queue as the tracking calls, meant to
be wired to a cookie-consent banner:

- **`ttq.holdConsent()`** — called immediately after `ttq.load()`, before any `page`/`track` calls,
  to hold all cookies and event sending until a decision is known.
- **`ttq.grantConsent()`** — releases the hold once a visitor accepts; queued events then flow.
- **`ttq.revokeConsent()`** — stops future tracking and clears TikTok's cookies if a visitor declines
  or withdraws consent later; the loader script itself stays loaded, only the pixel's own activity
  stops.

This is functionally the same three-state pattern GA4's Consent Mode already gives FLS
(`gtag('consent', 'update', ...)`), and the existing GA4 doc's framing — "South African visitors are
unaffected [by EEA/UK/CH consent denial]; FLS ships no banner" — is a call for whoever writes the
consent-handling research/idea to make explicitly for TikTok too: POPIA (South Africa's Protection of
Personal Information Act) is a consent-and-lawful-basis law like GDPR, not identical to it, and
whether a TikTok pixel firing PageView/track events for a South African visitor needs an opt-in
banner under POPIA (as opposed to legitimate-interest-style processing) is a legal question this file
does not settle — flagged here only so the idea document doesn't silently assume the GA4 doc's "South
Africa is unaffected" framing carries over to TikTok. A dedicated consent worker covers this in
depth.

Sources:
[TikTok Pixel & Events API Consent Gating, CookieBeam](https://cookiebeam.com/guides/tiktok-pixel-events-api-consent-2026),
[TikTok Pixel and Cookie Consent: A Complete Integration Guide for Publishers in 2026, FlexyConsent](https://flexyconsent.com/blog/tiktok-pixel-consent-integration-guide/).

## 8. CSP hosts

FLS's CSP (`SECURE_CSP_REPORT_ONLY` in `config/settings_base.py`) currently allowlists per-directive
hosts for gtag.js, Google Ads and PostHog, with a comment explaining *why* each host is in which
directive (script-src for anything that injects `<script>` tags or beacons pixels, connect-src for
`fetch`/XHR/`sendBeacon`, img-src for classic `<img>` pixels, frame-src for anything TikTok would
frame). TikTok's pixel loader and its event-sending calls both live on **`analytics.tiktok.com`**
(loader: `https://analytics.tiktok.com/i18n/pixel/events.js`; the same host receives tracked events).
That means, by the same reasoning FLS already applies to Google's hosts:

- **`script-src`**: `https://analytics.tiktok.com` (the pixel injects its own `<script>` tag from
  here, same pattern as `googletagmanager.com`).
- **`connect-src`**: `https://analytics.tiktok.com` (event calls are beacon/XHR-style requests to
  this same host).
- **`img-src`**: not confirmed as strictly required for the current TikTok pixel (it appears to use
  `fetch`/beacon rather than a classic `<img>` pixel fallback) — worth confirming against a live
  Pixel Helper trace before finalising the policy rather than assuming an image-pixel fallback.
- **`frame-src`**: no evidence found that the base pixel frames anything; TikTok ad formats displayed
  *on* FLS pages (e.g. an embedded TikTok video via Spark Ads or a widget) would be a separate,
  unrelated CSP need this idea doesn't currently call for.

A real-world data point: a public bug report against an unrelated Rails app (Gumroad) shows exactly
this failure mode — "TikTok Pixel field blocked by Content Security Policy — missing
`analytics.tiktok.com` in `script-src`" — i.e. forgetting the host is a common, silent failure (the
pixel just never loads, no console error surfaces to an end user, only to someone checking DevTools).
FLS's CSP is currently in **report-only** mode (`SECURE_CSP_REPORT_ONLY`), so a missing host wouldn't
even block anything in the current configuration, only get reported — worth noting since that
softens the immediate risk but means a future enforced CSP needs this checked before enforcement
flips on.

Sources:
[TikTok Pixel field blocked by Content Security Policy, GitHub issue #5001](https://github.com/antiwork/gumroad/issues/5001),
[Using Social Media Pixels & External Tools with CSP, Marco Aures](https://marcoaures.ch/en/social-media-pixel-external-tools-and-csp/).

## 9. Testing

Three separate tools, each catching a different failure layer, mirroring roughly how FLS's doc
describes checking GA4/Ads with Tag Assistant:

- **TikTok Pixel Helper** — a Chrome extension, browser-side only: confirms the pixel loaded and
  which events fired from *this* page load. Equivalent role to Tag Assistant in the GA4 doc.
- **Test Events (in TikTok Events Manager)** — confirms TikTok's servers actually received an event,
  not just that the browser sent it; this is the layer that would also show server-side Events API
  calls, which Pixel Helper cannot see at all (Pixel Helper only sees what fires in the browser).
- **Diagnostics tab** — aggregate pattern-level view across live traffic (match rate trends, error
  rates over time), the layer for ongoing monitoring rather than one-off debugging.

No TikTok-specific "staging account" concept was found analogous to Google Ads' separate Ads
ID/labels-per-environment pattern; the natural equivalent for FLS staging would be the same approach
the GA4 doc already uses for Google Ads — leave the TikTok pixel ID unset (or use a separate
staging-only pixel with no live ad campaigns pointed at it) on staging, so staging traffic and test
sign-ups never inflate a production pixel's event counts or match rate.

Sources:
[TikTok Pixel Helper: Install, Verify & Fix Every Error (2026), AdManage.ai](https://admanage.ai/blog/tiktok-pixel-helper),
[Test Pixel Events Video Walkthrough, TikTok Ads Manager](https://ads.tiktok.com/help/article/test-tiktok-pixel-events-video-walkthrough?lang=en).

## 10. Common pitfalls and complaints

- **Ad blockers and browser privacy features.** Ad blockers run on a substantial share of desktop
  browsers; combined with iOS App Tracking Transparency, Safari's Intelligent Tracking Prevention and
  consent banners, industry write-ups put pixel-only conversion capture around 65% of true
  conversions, i.e. roughly a third of real conversions are invisible to a browser-only pixel. This
  is the direct motivation for the Events API hybrid setup in §4, and is a strictly bigger problem
  for TikTok's youth-skewed, privacy-conscious audience than it tends to be for Google Ads' broader
  reach.
- **Double counting.** Two distinct sources of this risk apply to FLS specifically: (a) TikTok's
  automatic SPA `PageView` firing on every history-API URL change, stacked with a manually-added
  `ttq.page()` call, would double every page view (see §3); (b) running pixel and Events API together
  without matching `event_id` values on both sides double-counts every conversion event, which is
  exactly why deduplication (§4) is treated as mandatory, not optional, once both legs are live.
- **Attribution windows understating real impact.** TikTok's Ads Manager defaults to a 7-day
  click-through / 1-day view-through attribution window (selectable up to 28-day click / 7-day view).
  Advertisers who switched from the 7-day default to 28-day reportedly found 63-79% more conversions
  that the shorter window wasn't crediting to TikTok at all — relevant to FLS in that a course-buying
  decision (unlike an impulse retail purchase) plausibly takes longer than a week from first TikTok
  ad exposure to registering, so the default window may systematically undercount TikTok's real
  contribution to the funnel the same way GA4's own doc already flags for staff/cohort registrations
  bypassing `course_registered` entirely.
- **Automatic Advanced Matching surprising a developer.** Because it scans form fields on the page
  without an explicit `identify()` call, a developer relying only on manual matching could still find
  PII being hashed and sent if automatic matching is left on in Events Manager — worth an explicit
  "off" decision given FLS's no-PII stance (§5), not an assumption that leaving it at its default is
  safe.

Sources:
[TikTok Ads Tracking Accuracy, Cometly](https://www.cometly.com/post/tiktok-ads-tracking-accuracy),
[Ad Blockers Affecting Conversion Tracking, Cometly](https://www.cometly.com/post/ad-blockers-affecting-conversion-tracking),
[TikTok Attribution Window: What It is & How to Set Up, Nestscale](https://nestscale.com/blog/tiktok-attribution-window.html),
[About the attribution window on TikTok Ads Manager](https://ads.tiktok.com/help/article/about-the-attribution-window-on-tiktok-ads-manager).

## Open questions for the idea document (not answered here)

- Whether FLS's no-PII stance extends to TikTok (holding automatic Advanced Matching off, relying on
  `ttclid`/`_ttp`/IP/UA-only Events API payloads) or whether a deployment-level opt-in exception is
  acceptable — this is a policy call, not a technical one.
- Whether a TikTok integration reuses `google_tag`'s existing session-queue mechanism (renaming or
  generalising `freedom_ls.google_tag` into something ad-platform-agnostic) or ships as a sibling app
  — an architecture decision belonging to the idea/design stage, informed by, but not decided by,
  this research.
- Whether the Events API leg is in scope for a first version, given it needs a new secret
  (access token), a shared `event_id` threaded from view to two separate render-time emitters, and
  `ttclid`/`_ttp` capture-and-replay plumbing that doesn't exist for any current FLS integration.

status: ok
