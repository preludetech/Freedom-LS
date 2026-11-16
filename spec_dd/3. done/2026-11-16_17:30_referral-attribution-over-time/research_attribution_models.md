# Research: multi-touch referral attribution — models, payout practice, fraud, storage, privacy, prior art

Scope: material for a spec that extends a single-touch `SignupAttribution` model into a timeline of
touches per person, for later partner/influencer payout decisions. This document supplies vocabulary,
hard numbers, named sources and constraints. It does not propose an FLS design.

---

## 1. Attribution models and vocabulary

Standard model names (used consistently across GA/analytics and affiliate-tooling literature):

- **First-touch (first-click)** — 100% of credit to the first touchpoint. Framed as best for
  awareness/top-of-funnel measurement, long sales cycles, "educator" affiliates who create demand.
- **Last-touch (last-click)** — 100% of credit to the last touchpoint before conversion. Framed as
  best for measuring what "closed the deal"; rewards affiliates who convert people already in
  consideration.
- **Last non-direct click (Google Analytics' historic default, "LNDA")** — like last-click, but
  **direct traffic is excluded from consideration**: if the last recorded channel before conversion
  is "direct" (no referrer/campaign data — e.g. typed URL, bookmark), GA walks back and credits the
  most recent *non-direct* channel instead. Rationale given by Google/analytics vendors: a direct hit
  is assumed to be someone acting on prior brand awareness created by an earlier marketing touch, not
  a new causal channel in its own right, so crediting "direct" would systematically under-credit real
  marketing channels. Source: Google Analytics Help, "About the default MCF attribution models"
  (support.google.com/analytics/answer/1665189) and Optimize Smart's explainer
  (https://www.optimizesmart.com/last-non-direct-click-attribution-model-in-google-analytics/).
- **Position-based / U-shaped** — splits credit, typically weighting first and last touch equally
  (e.g. 40/40 with 20% spread across the middle).
- **Time-decay** — every touch gets some credit, but credit increases the closer the touch is to
  conversion (exponential decay by recency). Source: factors.ai time-decay explainer.
- **Linear** — equal credit to every touch (not asked for explicitly but referenced by the same
  sources as the multi-touch baseline against which time-decay and position-based are contrasted).

De-facto standard for partner/affiliate payout: **last-click (last-touch) wins**, specifically
"most recent affiliate link/code touched before the qualifying conversion, within the attribution
window, gets the commission." Multiple SaaS-affiliate-tooling sources converge on this: "last-click
attribution is the most common model for a reason: it rewards results ... it motivates affiliates to
actively promote offers already in the consideration phase" — Rewardful
(https://www.rewardful.com/articles/first-touch-vs-last-touch-attribution). Rewardful is explicit,
however, that this is **not universally the "right" answer** — their own guidance is that the choice
should track business stage/affiliate-mix (first-touch better rewards top-of-funnel/education
affiliates; last-touch better rewards closers) and that programmes should pick deliberately and stay
consistent, because switching models changes who gets paid for the same underlying events. No
tie-break rule beyond "last one wins" is given in that source for the case of two affiliates touching
the same customer — the model itself *is* the tie-break.

### Attribution / cookie / lookback window

"Attribution window" (a.k.a. cookie window, cookie duration, lookback window) = the maximum time
between a tracked touch and a conversion for which that touch is still eligible to receive credit.
Numbers reported across affiliate-marketing sources (Digistore24, Trackdesk, Post Affiliate Pro,
Refersion, just-affiliates, fluentaffiliate):

- Typical range across the industry: **30–90 days**.
- Cited as *the* industry-standard default: **30 days**.
- Amazon Associates: notably short, **24 hours** (same-day/next-day only, historically extended
  slightly for items added to cart).
- Common discrete tiers seen across programmes: 1 day, 7 days, 30 days, 60 days, 90 days, and
  uncapped/"lifetime" cookies.
- Rule of thumb tying window length to purchase consideration: impulse/low-value goods (<$50) → 7–14
  days; mid-range ($50–$200) → 30 days; high-ticket/complex/considered purchases → 60–90 days.
- The open-source `django-attribution` package defaults its configurable attribution window to
  **30 days**, matching the same industry number (source: project README, see §7).

Caveat: sources disagree on "the" standard — some frame 30 days as *the* norm, others present a wide
band (7–90+) as equally common depending on product/vertical. Treat 30 days as the median default to
anchor a design decision on, not a hard requirement.

---

## 2. Affiliate/referral payout practice: who wins when two partners touch the same customer

- **Last-click-wins** is the dominant convention in SaaS referral tooling (Rewardful, and by
  implication FirstPromoter/PartnerStack-style tools, which are typically compared feature-for-feature
  against Rewardful on exactly this axis — attribution model choice is a headline comparison point
  between these vendors per firstpromoter.com's own comparison pages). Under last-click, "the partner
  who gets credit is the one whose link/code was most recently used before the conversion, regardless
  of whether other partners influenced awareness earlier."
- **First-click-wins** exists as an alternate, explicit, program-level policy choice (not a fallback) —
  chosen deliberately for programmes that want to reward top-of-funnel demand generation over closing.
- Overrides seen in practice: manual commission overrides by the program admin (to resolve disputed
  or fraud-suspected attributions), and "sticky" affiliate cookies that some platforms let a merchant
  configure as override rules (e.g. "if a coupon code is entered directly, it always wins over a
  stale click"). The general affiliate-payout literature (Tapfiliate, ReferralCandy,
  idevaffiliate) does not describe a standardized tie-break algorithm beyond "the configured
  attribution model decides"; disputes are handled by manual admin review, not by more granular
  automatic rules.
- **Locked / frozen attribution at conversion time.** Affiliate/commission-tracking literature
  describes a **commission lifecycle with discrete states**: e.g. *Pending → Approved/Confirmed →
  Rejected/Reversed → Locked (billing cycle closed) → Paid* (Tapfiliate's payout guide). The
  attribution decision — which touch/partner gets credit — is made and **recorded at the moment of
  conversion**, checked against the attribution window, refund/hold period, and fraud screening, and
  then **not recomputed** afterward even if new touches are recorded later or the underlying tracking
  data changes. This matters because: (a) raw touch/click logs are commonly pruned, deduplicated, or
  purged for fraud/volume reasons after some retention period, so a "recompute from raw events" step
  might not have the same inputs available later; (b) payout obligations need a stable, auditable
  number at the point commission is approved — a partner should not see a commission clawed back
  or created solely because attribution-engine logic or event retention changed after the fact.
  Sources: Tapfiliate "How to Manage Affiliate Payouts" (2026 guide), idevaffiliate "Fix Coupon
  Attribution Problems in Affiliate Payouts", ReferralCandy "Attribution Models For Affiliate
  Programs".

---

## 3. Self-referral, fraud and hygiene rules

Recurring items across fraud-prevention sources (Rewardful's fraud-detection page, ReferralCandy,
Social Snowball, track360, LoudCrowd, mFilterIt):

- **Self-referral**: an affiliate/partner signs up (or gets a friend/relative to sign up) using their
  own code/link to earn a reward or a customer discount they weren't entitled to. Detection signals
  cited: unusually high conversion rate on one code, repeated orders from the same device/IP,
  commissions concentrated on accounts that already look like existing customers, near-instant
  redemption after code issuance. Mitigation: explicit prohibition in program terms; automatic
  invalidation/ban on detection; some platforms auto-flag and hold commission before payout rather
  than clawing back after (track360: "fraud detection should block commissions before payout, not
  after money leaves your account").
- **Code leaked/used by someone other than the partner**: coupon/referral codes posted to public
  coupon-aggregator sites, inflating a partner's apparent referral volume without them having done
  the referring. Mitigation: per-partner **unique, single-use or usage-capped codes** rather than
  memorable/generic ones; automatic disabling once a usage cap is hit; monitoring for the code
  appearing on third-party coupon sites (LoudCrowd, ReferralCandy both dedicate guides to this).
  An alternative structural fix some vendors use: a **linkless/codeless** referral (the discount is
  conferred automatically by clicking the affiliate's link, not by typing a shared code), removing
  the leak vector entirely.
- **Bots / link-unfurlers inflating touches**: not covered by name in the affiliate-fraud sources
  found, but the general fraud-detection stack described (device fingerprinting, IP/VPN/proxy
  blocking, real-time fraud scoring, email/phone validation) is the same tooling used against bot and
  crawler-driven click inflation; mFilterIt and track360 both frame "fraud detection" broadly enough
  to include automated/non-human traffic alongside human self-referral, without giving unfurler-bots
  a distinct named mitigation.
- **General technical controls** repeatedly cited: cookie-based click tracking to establish
  provenance of a conversion; device/IP-level fraud scoring; explicit program-terms prohibitions with
  enforcement (ban + invalidate); usage caps and single-use codes; holding commissions pending
  review rather than paying instantly.

---

## 4. Storing a touch timeline

Two common data shapes, both attested across the analytics/CDP and Django-package literature (see
§7):

1. **Append-only event/touch table** — one row per touch (session/click), each carrying its own
   source data (utm_*, click ids, referrer, landing URL, timestamp) and a foreign key to an identity.
   This is what `django-attribution`'s `Touchpoint` model does, and is the shape needed to support
   *any* multi-touch model (position-based, time-decay, last-non-direct) since those all require
   walking the ordered list of touches, not just two endpoints.
2. **Denormalised first/last pair on the customer/identity record** — cheaper to query, sufficient
   only for first-touch or last-touch models; this is effectively what the existing single-row
   `SignupAttribution` model already is (a frozen first-touch snapshot). It cannot answer "which code
   was in play for course X" once more than one touch might exist, and cannot support last-non-direct,
   position-based or time-decay without extra data.

### Anonymous-to-account stitching

Standard mechanism: a durable anonymous **visitor/session id** is set (typically a server-set
first-party cookie, sometimes paired with a fingerprint) before signup; every touch is recorded
against that anonymous id; at signup, the anonymous id's touch history is **merged/re-keyed onto the
new account** — this is exactly what `django-attribution` calls "Identity ... merged when an
anonymous visitor logs in (their history gets consolidated with their user account)" (see §7).

Failure modes, repeatedly named across identity-resolution literature (RudderStack, Perform Digital,
Attribuly, Celebrus):

- **Cookie cleared or expired before the person ever converts** — the touch is orphaned; there is no
  key to attach it to at signup time, so it silently disappears from the timeline.
- **Different device / cross-device** — a touch happens on a phone, the signup happens on a laptop;
  without a logged-in cross-device identity graph (email match, login on both devices, etc.) these
  cannot be stitched at all from cookies alone.
- **Ad blockers / privacy tooling** that block third-party trackers can also interfere with
  first-party analytics scripts or client-set identifiers, though a server-set first-party cookie
  (as FLS already uses) is comparatively robust to this class of blocking.
- **Shared devices → "identity explosion"**: a cookie/id that many different people share (shared
  computer, generic email) incorrectly merges unrelated people's touches into one profile, corrupting
  the timeline for all of them.
- General point: "if tagging/tracking is sloppy, identity resolution just amplifies the noise" — the
  quality of the stitched timeline is bounded by the quality of the underlying per-touch data
  capture, not fixable after the fact by clever merge logic.

### Safari ITP and Chrome cookie-lifetime caps (directly relevant — existing cookie is server-set)

- **Safari ITP's well-known 7-day cap applies only to cookies set via JavaScript
  (`document.cookie`)**, not to cookies set via the HTTP `Set-Cookie` response header from a
  first-party server. "Any cookie written by JavaScript via `document.cookie` is capped at a maximum
  7-day lifetime" (and can be cut to 24 hours if Safari classifies the setting domain as a tracker).
  **Server-set first-party cookies follow ordinary HTTP cookie rules and can persist for their full
  configured lifetime, historically up to 400 days** — i.e. the existing FLS server-set 90-day cookie
  is *not* subject to the 7-day ITP cap. Sources: Louder ("Apple ITP targets HTTP cookies with 7 day
  cap"), usehardal.com Safari ITP guide, seresa.io.
- **Important caveat as of Safari 16.4 (April 2023)**: even server-set first-party cookies can be
  capped to 7 days if Safari decides the *serving infrastructure* looks suspicious — specifically
  when the cookie-setting server is fronted by a CNAME to a third-party tracking vendor, or otherwise
  looks disconnected from the site's own first-party infrastructure ("CNAME cloaking" detection).
  A cookie set directly by the FLS Django app on its own domain (not via a third-party CNAME'd
  tracking vendor) should not trigger this, but it is a live constraint to note if any tracking is
  ever proxied through a third-party vendor domain.
- **Chrome and Firefox both now cap cookie `Expires`/`Max-Age` at 400 days** (Chrome since M104,
  August 2022; Firefox capped `Expires` first and then `Max-Age` in Firefox 140, June 2025). A cookie
  requesting a longer expiry is not rejected — its expiry is silently clamped to 400 days from time of
  setting. Re-setting/refreshing the cookie on a later visit resets the 400-day clock from that visit,
  not from the original. Sources: Chrome for Developers blog
  (https://developer.chrome.com/blog/cookie-max-age-expires), Chromium issue tracker
  (issues.chromium.org/issues/40800807).
- Net effect for a spec: a 90-day server-set cookie is comfortably inside all of these caps (400-day
  ceiling, ITP HTTP-cookie exemption) on every major browser today. It is **only** at risk if the
  cookie-setting endpoint is ever served via a CNAME to third-party infrastructure that Safari can
  flag as tracking-related.

---

## 5. Cookie payload size limits (hard numbers)

- **Per-cookie size ceiling: 4096 bytes**, counting the cookie's name, value, and attributes together,
  consistently across Chrome, Firefox (~4097 bytes), Safari, and Edge.
- **Per-domain cookie count ceilings** (browser-specific, and the smallest one governs
  cross-browser-safe design): Chrome ~180 cookies/domain, Firefox ~150, **Safari 50, Edge 50**.
- **Cross-browser-safe practical guidance** repeatedly given: **do not exceed ~30–60 cookies per
  domain, and keep each individual cookie under ~4093–4095 bytes** to be safe across all browsers
  and account for encoding overhead.
- Direct implication for "carry a list of touches client-side in one cookie": a single 4096-byte
  cookie storing a JSON array of touch records (each touch needing at minimum a code/id, timestamp,
  and perhaps a source label) can hold only a **few dozen** compact touch records at best before
  hitting the ceiling — nowhere near enough for an open-ended timeline, and safety margin must be left
  for the cookie's own name/attribute overhead (path, domain, `Secure`, `HttpOnly`, `SameSite`,
  signing overhead if signed). Splitting the timeline across multiple cookies is technically possible
  (up to ~50 cookies/domain on the tightest browser, Safari/Edge) but multiplies request header
  overhead (cookies round-trip on every request to the domain) and signing/parsing complexity.
  Source: Browser Cookie Limits reference tables (browsercookielimits.iain.guru), Ingest Labs cookie
  size explainer, Convert.com support article.

---

## 6. Privacy and law

- **GDPR core principles bearing directly on a touch timeline**: Art. 5(1)(c) data minimisation
  ("only collect what is necessary") and Art. 5(1)(e) storage limitation ("keep no longer than
  necessary"). A **longer, richer history of touches is a bigger footprint under both principles**
  than a single first-touch snapshot: minimisation asks whether *each additional retained touch* is
  actually necessary for the stated purpose (here: enabling a future payout decision), and storage
  limitation asks how long that expanding record needs to be kept — a timeline that keeps growing for
  as long as someone is a customer is a materially different (larger, longer-lived) risk profile than
  a single frozen first-touch row, and should be justified and time-boxed explicitly rather than kept
  indefinitely "just in case." Source: Legiscope's GDPR minimisation/storage-limitation explainer.
- **ICO/EDPB retention guidance for tracking cookies specifically**: commonly cited maximum
  **13 months for analytics/advertising cookie lifespan**, with **consent itself commonly re-asked at
  most every ~6 months**. This is *cookie-lifetime* guidance rather than a hard legal ceiling, but it
  is the benchmark regulators and cookie-consent vendors point to; a 90-day cookie is well under it,
  but a payout/attribution *record* that persists indefinitely in the database (as opposed to the
  browser cookie) is a separate retention question that isn't automatically satisfied just because the
  cookie itself expires in 90 days.
- **UK ICO / PECR position, 2026 update**: the ICO finalised new guidance on tracking technologies
  (cookies and tracking pixels) on **29 April 2026**, described as the most significant update to UK
  cookie rules since GDPR, following consultations in December 2024 and July 2025 tied to the Data
  (Use and Access) Act. Key points found:
  - **Affiliate/attribution tracking pixels and cookies require consent.** "An affiliate marketer
    needs consent to use a pixel to track clicks on affiliate links and conversions to attribute
    sales to those clicks" — affiliate attribution tracking is explicitly named as a use case that
    is **not** exempt as "strictly necessary."
  - The **"strictly necessary" exemption** (which would let a site set a cookie without consent) only
    applies when the cookie is genuinely necessary *from the user's perspective* for a service they
    asked for — **not** merely because it is commercially useful to the business. An
    attribution/payout-tracking cookie serving the *merchant's/partner's* commercial interest (paying
    a partner correctly) rather than the *visitor's* requested service is squarely on the
    consent-required side of that line, on this reading.
  - Maximum PECR fine has been raised to **£17.5 million or 4% of global annual turnover, whichever
    is higher** — brought into line with UK GDPR-level fines, up from a prior £500,000 cap.
  - Sources: CookieYes "UK ICO Cookie Guidance Just Changed", usercentrics "ICO PECR Cookies
    Guidance: Updates for 2026", insideprivacy.com summary of the ICO's guidance changes,
    Pearl Cohen "UK ICO Finalizes New Cookies and Pixel Tracking Guidelines."
- **Right to erasure and a per-person touch history**: none of the sources found give
  affiliate/attribution-specific erasure guidance beyond general GDPR data-subject-rights principles
  (a touch timeline tied to an identifiable person is personal data like any other, and is therefore
  in scope for access/erasure requests same as the existing single-touch record — a longer history
  is simply *more* personal data to locate and delete/redact on request, not a different legal
  category of data). Treat this as an inference from general GDPR principles rather than a directly
  sourced statement — flagged here as a gap, not a confirmed regulatory position specific to touch
  timelines.

Where sources disagree / gaps: the 13-month cookie-lifetime figure is analytics/advertising cookie
guidance, not attribution/payout-cookie-specific; I found no ICO guidance that speaks *directly* to
"how long may a per-person referral-touch history be retained in a database" as distinct from
general storage-limitation principles — this is a gap a designer will need to make a reasoned,
documented call on rather than cite a specific number for.

---

## 7. Django-specific prior art

The field is thin — no single dominant, actively-maintained "Django affiliate/attribution" package
exists. Two candidates surfaced, useful mainly for vocabulary to borrow rather than as
production-ready dependencies:

- **`django-utm-tracker`** (yunojuno) — Django 4.2+/Python 3.10+. Middleware-based: extracts
  `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, plus click ids (`gclid`,
  `aclk`, `msclkid`, `twclid`, `fbclid`) and custom tags (JSONField `custom_tags`) from the incoming
  querystring, stashes them in `request.session` for anonymous visitors, and persists them against
  `request.user` in a **`LeadSource`** model once the user is authenticated. This is a **first-touch
  captured at session-start, promoted to a durable record at login/signup** shape — structurally the
  same pattern the existing FLS `SignupAttribution` already follows (session/cookie → single durable
  row at signup), not a multi-touch timeline. Source: github.com/yunojuno/django-utm-tracker.
- **`django-attribution`** (YounesOMK) — explicitly framed as multi-touch marketing-attribution
  tracking for Django. Models named in its own docs:
  - **`Identity`** — represents a visitor tracked by cookie, "merged when an anonymous visitor logs
    in (their history gets consolidated with their user account)" — i.e. this package names the exact
    anonymous-to-account stitching operation FLS will need.
  - **`Touchpoint`** — one row per visit/source: UTM params, click ids, landing URL, referrer. This
    is the append-only-event-table shape from §4.
  - **`Conversion`** — the valuable event (with type, monetary value, currency, confirmed flag),
    linked to the `Identity` that converted, and attributed back to `Touchpoint`s.
  - Supports **first-touch and last-touch** attribution models today, each with a configurable
    **attribution window (default 30 days)**, and the docs describe per-source window overrides
    ("different windows per source").
  - Source: github.com/YounesOMK/django-attribution.

Vocabulary worth borrowing rather than reinventing, based on the above: **Identity** (the
stitched anonymous+authenticated actor), **Touchpoint** (one recorded touch/event), **Conversion**
(the event being attributed, generalizable beyond "signup" to e.g. "course registration"),
**attribution window** (the lookback cutoff), and the **merge-on-login** operation name for
stitching. Neither package is verified here as maintained-and-battle-tested at scale; treat both as
naming/shape references, not as recommended dependencies to install.

---

## Summary of hard numbers for quick reference

| Item | Value | Source |
|---|---|---|
| Affiliate attribution window, industry-cited standard | 30 days | Post Affiliate Pro, Trackdesk |
| Affiliate attribution window, common range | 30–90 days (1 day–lifetime seen) | multiple affiliate-tooling blogs |
| Amazon Associates cookie window | 24 hours | Post Affiliate Pro |
| `django-attribution` default attribution window | 30 days | github.com/YounesOMK/django-attribution |
| Cookie size ceiling (name+value+attrs) | 4096 bytes (Chrome/Safari/Edge), ~4097 (Firefox) | browsercookielimits.iain.guru, Ingest Labs |
| Per-domain cookie count ceiling | Safari/Edge 50, Firefox ~150, Chrome ~180 | same |
| Cross-browser-safe practical ceiling | ~30–60 cookies/domain, <4095 bytes each | same |
| Safari ITP JS-cookie cap | 7 days (24h if flagged tracker) | Louder, usehardal.com |
| Safari ITP server-set HTTP cookie | full TTL exempt from 7-day cap; can drop to 7 days if server looks like third-party/CNAME-cloaked tracking infra (Safari ≥16.4, Apr 2023) | seresa.io, dataflysignal.com |
| Chrome/Firefox cookie `Expires`/`Max-Age` ceiling | 400 days (silently clamped, resets on refresh) | developer.chrome.com/blog/cookie-max-age-expires |
| ICO/EDPB analytics/advertising cookie lifetime guidance | ~13 months; consent re-ask ~6 months | (general ICO/EDPB guidance, via CookieYes/flowconsent summaries) |
| UK PECR max fine (post-2026 ICO update) | £17.5m or 4% global turnover, whichever higher | CookieYes, Pearl Cohen |
| ICO 2026 tracking-technologies guidance finalised | 29 April 2026 | CookieYes, usercentrics |

---

status: ok
