# Research: Meta (Facebook/Instagram) Pixel for FLS

Scope: the Meta Pixel and Conversions API only. TikTok's pixel is a separate research
topic. This is research to inform an idea, not an implementation plan.

## 1. How the pixel works, and how it would sit next to `google_tag`

The Meta base code is one inline `<script>` block (from `connect.facebook.net/en_US/fbevents.js`)
that defines `fbq`, then calls:

```js
fbq('init', '<PIXEL_ID>');
fbq('track', 'PageView');
```

placed once per page, near the top of `<head>`, plus a `<noscript>` fallback `<img>` pointing at
`https://www.facebook.com/tr?id=<PIXEL_ID>&ev=PageView&noscript=1` for browsers with JS disabled.
`fbq('track', <StandardEventName>, {params})` fires one of Meta's 17 predefined **standard events**
(see §2). `fbq('trackCustom', '<AnyName>', {params})` fires an arbitrarily named **custom event**
that behaves identically on the wire but isn't recognised by Meta's standard-event tooling
(benchmarking, some campaign-objective presets) unless later wrapped in a **custom conversion**.
A **custom conversion** is a Meta-Events-Manager-side rule ("count this as a conversion when event X
fires and parameter Y matches") built from any standard or custom event plus optional URL/parameter
filters — conceptually the same shape as GA4's "created event" (`course_application_submitted`) that
`docs/how tos/google-analytics-and-ads.md` already uses to split `course_access_requested` by
`request_kind`. Meta's own docs: https://developers.facebook.com/docs/meta-pixel/reference/,
https://developers.facebook.com/docs/meta-pixel/implementation/conversion-tracking/.

As of 2026, Meta's Events Manager UI renames a Pixel to a **dataset** (the dataset ID is the same
numeric ID as the pixel), and Pixel + Conversions API events for one dataset are unified in one view
(https://adsuploader.com/blog/meta-events-manager). Terminology in Meta's docs may say "dataset"
where older material says "pixel"; they're the same ID.

**Architectural fit.** FLS's existing pattern — a view records a one-shot event into the session
queue (`freedom_ls/google_tag/events.py`), and `partials/google_analytics_events.html` pops the
queue and emits `gtag('event', ...)` calls on the next render, including after an HTMX swap — maps
onto `fbq('track', ...)`/`fbq('trackCustom', ...)` calls just as well, since both are plain
browser-side JS calls with a name and a flat parameter object. Whether Meta reuses that queue or gets
its own is a design decision for later, not something this research resolves.

## 2. Standard events and a candidate mapping to FLS's six GA4 events

Meta's 17 standard events (https://developers.facebook.com/docs/meta-pixel/reference/):
`AddPaymentInfo`, `AddToCart`, `AddToWishlist`, `CompleteRegistration`, `Contact`,
`CustomizeProduct`, `Donate`, `FindLocation`, `InitiateCheckout`, `Lead`, `Purchase`, `Schedule`,
`Search`, `StartTrial`, `SubmitApplication`, `Subscribe`, `ViewContent`, plus the automatic
`PageView`. None of these was designed for an LMS funnel, so the mapping below is a judgement call,
not a lookup:

| FLS event | Nearest Meta standard event(s) | Notes |
| --- | --- | --- |
| `sign_up` | `CompleteRegistration` | Direct semantic fit ("registration form submission"). |
| `course_access_requested`, `request_kind=interest` | `Lead` | "Sign-up completion" / expression of interest; matches Meta's own definition of Lead as agreeing to be contacted. |
| `course_access_requested`, `request_kind=application` | `SubmitApplication` | Named for exactly this. |
| `course_registered` | No good standard fit. Candidates: `StartTrial` (if free courses are framed as a trial), `Subscribe` (if registration is gated behind a paid plan), or a custom event via `trackCustom` | Unlike GA4/Ads, Meta has no generic "enrolled" event. Reusing `CompleteRegistration` here would collide semantically with `sign_up` and muddy Meta's per-event optimisation and benchmarking. A custom event (e.g. `trackCustom('CourseRegistered', …)`) avoids a forced-fit standard event; it can still be wrapped in a custom conversion for campaign optimisation, just without Meta's standard-event benchmarks. |
| `course_started` | No good standard fit. `ViewContent` is the closest ("visit to an important page") but is heavily used for e-commerce product views, which may confuse benchmarking. A custom event is the more honest option | This is a funnel step, not a conversion goal (matches Google Ads treatment, where it's not a key event either). |
| `course_completed` | No standard fit at all — a custom event (e.g. `trackCustom('CourseCompleted', …)`) | Same lag-to-ad-click reasoning that made this a *secondary* Google Ads conversion applies here. |
| `generate_lead` | `Lead` | Direct fit — this is the textbook use of the `Lead` event. |

Standard events get Meta's benchmarking, appear in event-selection dropdowns without extra setup,
and are what Meta's automated "Suggested Events" tooling and some campaign objectives expect.
Custom events cost nothing extra to fire but need a **custom conversion** defined in Events Manager
before they can be chosen as a campaign's optimisation goal, and they don't benefit from Meta's
per-industry benchmark comparisons. Practically, this means `course_registered`, `course_started`
and `course_completed` are equally well served by custom events, wrapped in custom conversions the
same way GA4's `course_application_submitted` is today — this is a close structural parallel to what
FLS already does for Google.

Sending `value` and `currency` (`ZAR` is a valid ISO 4217 code Meta accepts) on `Lead` and
`CompleteRegistration` gives Meta's optimisation something to bid towards, mirroring the Google Ads
doc's explicit "Don't use a value" choice for FLS's conversions — the same choice (skip value) is
available here and keeps the two platforms consistent, but the trade-off (an estimated value can
improve bidding quality) belongs in a design conversation, not this research note.

## 3. SPA / HTMX considerations

The pixel's base code, once loaded, **automatically listens to `history.pushState`/`replaceState`**
and fires a `PageView` on every history change by default — this is Meta's built-in SPA support, not
something FLS would add
(https://developers.facebook.com/ads/blog/post/2017/05/29/tagging-a-single-page-application-facebook-pixel/,
https://github.com/segment-integrations/analytics.js-integration-facebook-pixel/issues/5). This
matters directly for FLS: `docs/how tos/google-analytics-and-ads.md` already notes "Most FLS
navigation changes the URL without a full page load" for GA4's enhanced measurement. Whichever way
FLS's HTMX boosted swaps update the URL (`hx-push-url`/`hx-boost`), Meta's listener will very likely
already catch it and fire an extra `PageView` — the practical risk is **double-counting PageView**:
once from the automatic listener on the URL change, and again if FLS's own template partial also
calls `fbq('track','PageView')` on that same swapped render (the same failure mode GA4's own
"Page changes based on browser history events" setting exists to avoid, per that doc's data-stream
table). The commonly recommended fix is to pick exactly one source of truth for `PageView`
(the pixel's own listener, or an explicit call, never both) rather than disabling the listener with
`disablePushState`, which most guides advise against
(https://www.analyticsmania.com/post/facebook-pixel-in-single-page-applications/). This should be
verified concretely against FLS's actual HTMX swap behaviour before any implementation choice is
made — it isn't resolvable from the pixel's docs alone.

## 4. Conversions API (server-side) — is it worth it in 2026?

**What it is.** A server-to-server POST to `graph.facebook.com/<version>/<PIXEL_ID>/events` carrying
the same event vocabulary as the pixel (event name, `event_time`, `event_id`, `user_data`,
`custom_data`), authenticated with a long-lived **access token** generated per dataset in Events
Manager → Settings → Conversions API. Because it's a server call, not a browser `fetch`, **it needs
no CSP entries at all** — a materially different cost profile from the pixel's browser JS.

**Recommended in 2026, not just optional.** Multiple 2026 setup guides frame CAPI as close to
mandatory now rather than an advanced add-on, citing iOS App Tracking Transparency and ad-blocker
loss (see §7) as the reason:
https://www.cometly.com/post/facebook-conversion-api-setup,
https://stape.io/blog/how-to-set-up-facebook-conversion-api,
https://weld.app/blog/boost-facebook-conversion-tracking-to-95-with-server-side-tracking-a-step-by-step-guide
(the last claims server-side tracking recovers conversions up to "95%" of otherwise-lost events;
treat vendor-blog percentages as directional, not verified figures).

**Deduplication.** When both the pixel and CAPI send the same real-world event, Meta deduplicates
purely on the pair `(event_name, event_id)` sent within a 48-hour window of each other —
**not** on `fbp`/`fbc`/email, which are match-quality signals, not dedup keys
(https://watsspace.com/blog/meta-conversions-api-deduplication-event_id/). The practical requirement
is a single `event_id` generated once per real event and threaded through to *both* the browser call
and the server call for that same event — for FLS's session-queued events, the natural place to
generate it would be wherever the event is first recorded in the view (mirroring `event_id` to
whatever eventually reaches CAPI), though the concrete wiring is a design question, not something
this research resolves.

**Event Match Quality (EMQ) and what CAPI wants.** EMQ is Meta's 0–10 score per dataset,
shown in Events Manager, that measures how well Meta can tie an event to a real person; a higher
score improves attribution and campaign optimisation. Inputs that raise it: SHA-256-hashed
lower-cased+trimmed email (`em`) and/or phone (`ph`); `fbp` (the first-party
`_fbp` cookie the pixel sets) and `fbc` (derived from the `fbclid` URL parameter on ad-click
landings) sent **unhashed**; `client_ip_address` and `client_user_agent` (also unhashed); optionally
name, city, state, zip, date of birth, gender, `external_id` (a stable internal user ID, hashed).
Sources: https://ceaksan.com/en/facebook-pixel-advanced-matching,
https://opinly.ai/blog/improve-meta-pixel-event-match-quality. **FLS currently sends no email, name
or phone number anywhere** (per the Google Ads doc's own statement), so a CAPI implementation that
wants a meaningfully higher EMQ than the pixel alone gets would need to start hashing and sending PII
it doesn't send today — a real scope and privacy-posture change, not a drop-in addition.
`external_id` (FLS's numeric account ID, hashed) is the one field FLS could send without introducing
new PII, mirroring how `user_id` is already sent unhashed to GA4 today.

**Cost/complexity vs browser-only.** Browser-only (pixel alone) is simpler: no access-token
management, no server code, no new PII flows, but is fully exposed to ad blockers and iOS
restrictions (§7) and to the browser environment generally. CAPI needs a securely stored access
token (env var, never in a template or client bundle — consistent with FLS's existing "never hardcode
credentials" convention), a server-side HTTP call at the same points where FLS already calls
`record_google_analytics_event`, and — for EMQ gains beyond just deduplication resilience — new PII
collection and hashing. A CAPI integration that sends *only* non-PII fields (event name, `event_id`,
`fbc`/`fbp` passed through, `external_id`) still gets the deduplication and ad-blocker-resilience
benefits without the PII scope increase; it just won't reach the higher EMQ tiers that hashed
email/phone unlock.

## 5. Advanced matching and PII implications

**Automatic Advanced Matching (AAM)**, a toggle in Events Manager, scans the page's own forms for
recognisable fields (email, phone, name inputs) and has the pixel hash and send them itself — no
code change, but it means the pixel is scraping form fields FLS didn't explicitly choose to send.
**Manual Advanced Matching** is explicit: passing `em`, `fn`, `ln`, etc. into `fbq('init', ...)` or
per-event calls, pre-hashed with SHA-256 (lower-case, trimmed) by the calling code — the pixel's JS
library will also hash for you if given plaintext, per
https://developers.facebook.com/docs/meta-pixel/advanced/advanced-matching/. Either mode is a step
beyond what FLS does anywhere today: "No email, name or phone number is sent anywhere" is stated as
a settled fact in the Google Ads doc, and turning on AAM (even passively, via the Events Manager
toggle, no code change) or manual matching would break that statement and needs a deliberate,
documented decision — not a default this research recommends either way.

## 6. Meta restrictions relevant to an education platform

**Sensitive categories / Special Ad Category.** Meta's ad-policy tooling flags topics that "can
influence personal wellbeing, identity, or life circumstances" for tighter targeting and claims
rules; education content that touches on education *policy* or similarly charged framing is called
out as a candidate for review/authorisation
(https://www.wetracked.io/post/meta-ads-new-sensitive-categories-restrictions,
https://www.foxwelldigital.com/blog/meta-special-ad-category-vs-sensitive-ad-category-whats-the-difference).
Plain course-marketing ("learn X", "enrol now") is unlikely to trip this, but campaigns that frame
courses around protected characteristics, life circumstances ("struggling with unemployment?") or
outcomes tied to sensitive categories could. Some sensitive-category advertisers additionally lose
Pixel/CAPI optimisation for certain event types under Meta's tiered data-restriction system
(https://sagapixel.com/meta-ads/facebook-ads-3-tiers/) — this is a policy risk to flag, not something
resolvable without knowing the actual ad creative/targeting FLS's downstream deployer plans.

**Aggregated Event Measurement (AEM) and domain verification.** AEM exists to preserve
Meta's visibility into conversions from visitors who deny iOS App Tracking Transparency. Historically
(pre-June 2025) it capped a domain at 8 prioritised conversion events for opted-out iOS traffic; as
of a mid-2025 change, **Meta removed that 8-event cap and the manual prioritisation UI** — AEM now
aggregates all eligible events automatically
(https://segwise.ai/blog/facebook-aggregated-event-measurement,
https://thread-transfer.com/blog/2025-06-09-aggregated-event-measurement/). AEM itself doesn't
require domain verification, but **domain verification does still matter**: it establishes which
Business Manager has authority to configure/edit events for a domain, and is required for Meta's
Business Tools generally (in-context ads, link previews with the right identity, iOS 14 app-side
event configuration) — done once, in Business Manager → Brand Safety → Domains, via a DNS TXT record
or an uploaded/meta-tag HTML file (https://www.conversios.io/blog/meta-aggregated-event-measurement/,
https://www.facebook.com/business/help/331612538028890). Since AEM's manual 8-event triage is gone,
FLS doesn't face the old "which five events get iOS visibility" trade-off GA4/Ads's key-events table
implicitly avoided — one less piece of platform-specific configuration than it would have needed a
year ago.

## 7. Consent: `fbq('consent', ...)` and a POPIA note

Meta ships `fbq('consent', 'revoke')` / `fbq('consent', 'grant')`: revoke keeps the pixel dormant —
no cookies set, no advertising-purpose data sent, though Meta's docs describe some aggregated,
non-advertising processing may still occur — and grant resumes normal operation
(https://seers.ai/blogs/facebook-pixel-consent-missing-piece-in-ad-strategy/). There's also a
separate **Limited Data Use (LDU)** flag, aimed at US state privacy laws (CCPA-style), that
restricts how *Meta itself* processes already-received data (`data_processing_options: ['LDU']` on
CAPI calls) — LDU is a Meta-side processing restriction, not a substitute for not sending the data,
and it's a US-specific construct, not something with an established POPIA equivalent
(https://flexyconsent.com/blog/meta-pixel-facebook-conversions-api-consent-guide/). For POPIA
specifically (South Africa): POPIA's default posture — like the GDPR default the Google Ads doc
already documents for the EEA/UK/Switzerland ("denied for visitors in the EEA... South African
visitors are unaffected") — treats tracking pixels and their cookies as processing of personal
information requiring a lawful basis (typically consent, since legitimate-interest-style bases are
narrower under POPIA than under GDPR); this note is deliberately brief since another worker is
covering consent in depth, and POPIA's specific interaction with `fbq('consent', ...)` is a topic to
resolve there, not here.

## 8. CSP hosts

Based on Meta's own domains and community-documented CSP rule sets
(https://github.com/jonashaag/content-security-policy-rules/blob/master/facebook.md,
https://help.adroll.com/hc/en-us/articles/6964547103629-Pixel-Troubleshooting-CSP-Errors,
https://marcoaures.ch/en/social-media-pixel-external-tools-and-csp/), the pixel itself needs:

| Directive | Host(s) | Why |
| --- | --- | --- |
| `script-src` | `https://connect.facebook.net` | Serves `fbevents.js`, the pixel library itself. |
| `img-src` | `https://www.facebook.com` | The `<noscript>` fallback `<img src="https://www.facebook.com/tr?...">`, used when JS is disabled; the JS-mode pixel also fires its tracking request as a beacon/image-style call to the same `/tr` endpoint in some browsers. |
| `connect-src` | `https://www.facebook.com`, `https://connect.facebook.net` | The JS-mode `fbq(...)` calls send their event data via `fetch`/XHR-style requests to `facebook.com/tr` (and the library may fetch config from `connect.facebook.net`). |

No `frame-src` entry is needed for the pixel alone — it sets no iframe. (A separate Facebook Login
button or Messenger customer-chat plugin, if ever added, would need its own `frame-src`/`script-src`
entries; that's out of scope for "tracking pixel".) Conversions API needs **no browser CSP entries
at all**, since it's a server-to-server call FLS's own backend makes with `requests`/`httpx`, not
something a visitor's browser executes — this is the one respect in which CAPI is strictly *simpler*
than the pixel, CSP-wise, even though it's more work everywhere else. This shape (one script host,
one combined img/connect host, no frame) is narrower than the Google Ads CSP block in
`config/settings_base.py`, which needs several `googleadservices.com`/`doubleclick.net`/
`googlesyndication.com` hosts plus a per-country `www.google.<TLD>` — Meta's footprint is smaller and
does not have the "per-country TLD" complication `config/settings_base.py`'s comment calls out for
Google.

## 9. Testing

**Test Events tool** (Events Manager → Data Sources → the dataset → Test Events tab): shows events
arriving from a specific browser session in real time, tagged either automatically (via the browser
extension) or by pasting a **Test Event Code** into `fbq('track', ..., {}, {eventID: ..., test_event_code: 'TEST12345'})`-style
calls or the equivalent CAPI field — this lets test traffic be flagged and excluded from real
campaign data without needing a second pixel ID, unlike GA4/Ads's approach of a wholly separate
staging property/stream. **Meta Pixel Helper** is the companion Chrome extension for eyeballing
which events fired on a given page load and their parameters
(https://www.conversios.io/blog/meta-pixel-helper-guide/). For FLS's staging environment, two options
exist: reuse the production pixel ID with the Test Event Code (Meta's built-in mechanism, no
separate dataset to provision) or provision a wholly separate staging pixel/dataset the way the
Google Ads doc does for `GOOGLE_ANALYTICS_MEASUREMENT_ID` (its own stream, "set up exactly as
below") — the Google Ads doc's stated reason for a separate staging property, avoiding test
sign-ups counting as real conversions, applies here too, but Meta's Test Event Code mechanism was
built to solve exactly that problem without a second dataset. Which approach fits FLS's deployment
model is a decision for the concrete design, not something resolved by this research.

## 10. Common pitfalls and complaints

- **Ad blockers.** uBlock Origin and similar block `connect.facebook.net`/`facebook.com/tr` outright;
  affected visitors show no events at all in Pixel Helper, which is often mistaken for a broken
  implementation rather than a blocked one
  (https://www.cometly.com/post/facebook-pixel-tracking-issues). CAPI is the standard mitigation,
  since the server call bypasses the browser entirely.
- **iOS / App Tracking Transparency.** iOS 14+ visitors who deny tracking (in-app contexts) or use
  Safari's tracking protections cause significant pixel data loss; various vendor sources cite figures
  around "50–60% of pixel data blocked," which should be treated as illustrative rather than a hard
  number for FLS's own audience (https://niblin.com/blog/meta-ads-tracking-attribution-issues). This
  is the same underlying pressure that produced AEM (§6) and is Meta's own stated motivation for
  pushing CAPI adoption in 2026 guides (§4).
  A South African audience is overwhelmingly Android; the practical size of the iOS-specific loss for
  this deployment is unverified and would need its own check against FLS's actual traffic mix rather
  than assumed from these mostly US-centric sources.
- **Double counting.** The most FLS-relevant version is the SPA/HTMX `PageView` duplication in §3;
  the general form (same conversion counted via pixel *and* CAPI *and* an imported/aggregated route)
  is the reason `event_id`-based deduplication (§4) exists at all, mirroring the "each moment goes
  through exactly one route" discipline the Google Ads doc already applies between "Ads tag" and
  "imported GA4 key event" routes.
- **Errors that aren't errors.** Pixel Helper reporting "no pixel found" or "errors" is frequently
  just an ad blocker or an over-strict CSP silently dropping the script/request, not a code defect —
  worth checking CSP report-only violation logs (FLS's `SECURE_CSP_REPORT_ONLY` setting) before
  assuming the integration itself is wrong.

## Sources

- Meta Pixel reference (standard events): https://developers.facebook.com/docs/meta-pixel/reference/
- Meta Pixel conversion tracking: https://developers.facebook.com/docs/meta-pixel/implementation/conversion-tracking/
- Meta Pixel advanced matching: https://developers.facebook.com/docs/meta-pixel/advanced/advanced-matching/
- Advanced matching in practice / EMQ: https://ceaksan.com/en/facebook-pixel-advanced-matching, https://opinly.ai/blog/improve-meta-pixel-event-match-quality
- Meta Events Manager / "dataset" terminology in 2026: https://adsuploader.com/blog/meta-events-manager
- Meta CAPI setup and dedup: https://www.cometly.com/post/facebook-conversion-api-setup, https://stape.io/blog/how-to-set-up-facebook-conversion-api, https://weld.app/blog/boost-facebook-conversion-tracking-to-95-with-server-side-tracking-a-step-by-step-guide, https://watsspace.com/blog/meta-conversions-api-deduplication-event_id/
- SPA / PageView duplication: https://developers.facebook.com/ads/blog/post/2017/05/29/tagging-a-single-page-application-facebook-pixel/, https://www.analyticsmania.com/post/facebook-pixel-in-single-page-applications/, https://github.com/segment-integrations/analytics.js-integration-facebook-pixel/issues/5
- Aggregated Event Measurement and the 2025 8-event-cap removal: https://segwise.ai/blog/facebook-aggregated-event-measurement, https://thread-transfer.com/blog/2025-06-09-aggregated-event-measurement/, https://www.conversios.io/blog/meta-aggregated-event-measurement/, https://www.facebook.com/business/help/331612538028890
- Sensitive categories / Special Ad Category and education: https://www.wetracked.io/post/meta-ads-new-sensitive-categories-restrictions, https://www.foxwelldigital.com/blog/meta-special-ad-category-vs-sensitive-ad-category-whats-the-difference, https://sagapixel.com/meta-ads/facebook-ads-3-tiers/
- Consent / LDU: https://seers.ai/blogs/facebook-pixel-consent-missing-piece-in-ad-strategy/, https://flexyconsent.com/blog/meta-pixel-facebook-conversions-api-consent-guide/
- CSP hosts: https://github.com/jonashaag/content-security-policy-rules/blob/master/facebook.md, https://help.adroll.com/hc/en-us/articles/6964547103629-Pixel-Troubleshooting-CSP-Errors, https://marcoaures.ch/en/social-media-pixel-external-tools-and-csp/
- Testing: https://www.conversios.io/blog/meta-pixel-helper-guide/
- Pitfalls (ad blockers, iOS): https://www.cometly.com/post/facebook-pixel-tracking-issues, https://niblin.com/blog/meta-ads-tracking-attribution-issues

status: ok
