# Research: Attribution Models & Windows

Scope note: referral codes are minted and owned by an external system. This app only
observes visits/behavior tied to a code and (per product decision) **stores data only for
now** — no scoring, dashboard, or webhook yet. The purpose of this research is to make
sure the storage schema doesn't accidentally bake in a model we'll regret later.

## 1. First-touch vs last-touch vs multi-touch

| Model | Credit goes to | Used for |
|---|---|---|
| First-touch | The very first referral touch in the window | Rewarding discovery/awareness partners (content creators, SEO); "who introduced this lead" |
| Last-touch (last-click) | The most recent referral touch before conversion | The de-facto default across affiliate networks; rewards the closer |
| Multi-touch / linear (or data-driven) | Split fractionally across every touch in the path | Marketing analytics (GA4), not typically used for paying/crediting a single affiliate |

Key facts:
- **Last-click with a cookie window is the standard for affiliate/commission crediting.**
  Most affiliate networks/platforms (PartnerStack, Post Affiliate Pro, Everflow, Trackdesk)
  default to last-touch, because it maps directly to "one partner, one commission" —
  first-touch and multi-touch require splitting money or credit, which is operationally
  harder and networks don't want disputes. ([Rewardful](https://www.rewardful.com/articles/first-touch-vs-last-touch-attribution), [RedTrack](https://www.redtrack.io/blog/first-touch-vs-last-touch-attribution/), [Everflow](https://helpdesk.everflow.io/customer/choosing-between-first-touch-last-touch-attribution))
- First-touch is offered as an alternative/toggle in most affiliate platforms for programs
  that want to reward top-of-funnel discovery rather than the last click before checkout.
- **GA4's default is "data-driven attribution" (DDA)**, a machine-learned multi-touch model
  that fractionally credits every touchpoint based on its estimated causal contribution
  (time-to-conversion, device, order of exposure, etc.). It requires meaningful volume
  (~400 conversions + 4,000 ad interactions/month) or GA4 silently falls back to last-click.
  This illustrates that multi-touch/DDA is a **marketing-analytics** concept, not something
  affiliate networks use to decide who gets paid. ([Growth Method](https://growthmethod.com/data-driven-attribution/), [Optimize Smart](https://optimizesmart.com/blog/ga4-attribution-models-explained-how-to-choose-the-right-one/))
- GA4 also has a distinct "last non-direct click" behavior at the **user-acquisition**
  level: if the most recent session's source is "(direct)", GA4 looks back up to 90 days
  to find the last non-direct source instead of crediting "direct". This is a pragmatic
  fallback rule, not a full model — it matters for us mainly as a reminder that "direct/no
  code" visits shouldn't wipe out a previously known referral if we ever compute credit.
  ([Affect Group](https://affectgroup.com/blog/ga4-source-and-medium-session-first-user-attribution/), [Napkyn](https://www.napkyn.com/blog/advanced-utm-attribution-in-ga4-aligning-with-universal-analytics-using-bigquery))

**Takeaway for affiliate/campaign credit specifically:** last-touch-within-window is the
industry norm because it produces one unambiguous answer per conversion. But because our
codes are managed by an *external* system, we don't need to pick this model at all right
now — see recommendation in §5.

## 2. Attribution windows

An attribution window (a.k.a. cookie duration / tracking window) is the period after a
touch during which a later conversion is still credited to that touch. After the window
expires, that touch is no longer eligible.

- **Typical values: 7–90 days**, chosen per program/vertical. Nutrition/consumable
  products often use short windows (~15 days); considered/high-value purchases (e.g.
  bicycles) use longer windows (~90 days). ([Avelon](https://avelonetwork.com/support/brand/affiliate-attribution-windows-first-party-cookies), [Trackdesk](https://trackdesk.com/blog/affiliate-marketing-cookie-duration))
- **Click vs view window**: a *click-through* window counts from when the user actually
  clicked the link; a *view-through* (a.k.a. post-view/impression) window counts from when
  the user merely saw an ad/impression without clicking, and is typically much shorter
  (default often ~24–48 hours) because the causal link to an unclicked impression is
  weaker. ([Post Affiliate Pro](https://www.postaffiliatepro.com/faq/what-is-click-attribution-affiliate-marketing/), [Webgains](https://knowledgehub.webgains.com/home/what-is-attribution))
  For an LMS referral link (`?ref=CODE` clicked in an email/social post/partner site),
  every touch we can observe is by definition a click-through — we have no ad-impression
  pixel — so the click-window concept is the only one that applies to us; there is no
  view-through case to design for.
- **How the window interacts with cookie/session expiry**: the window is enforced by
  however long the identifier persists client-side (cookie/localStorage) or server-side
  (session record tied to a device/user). If the cookie is cleared or expires before the
  window ends, attribution is lost regardless of the nominal window value — the *storage
  TTL* is a hard ceiling on the *attribution window*. Practically this means: whatever
  window we might someday score against, we must persist the raw touch data for at least
  that long (and ideally indefinitely, since storage is cheap and we're only observing).

## 3. Conflicting touches: code A then later code B before converting

Real systems resolve this in one of two ways, and it is a **configurable policy**, not a
law of nature:

- **Overwrite / last-click-wins (most common default)**: the second touch (code B)
  replaces the stored attribution value entirely. Affiliate A loses credit even though
  they referred first. This is the default behavior in most affiliate plugins/platforms
  unless "keep first click" is explicitly enabled. ([Post Affiliate Pro](https://www.postaffiliatepro.com/faq/first-last-affiliate-attribution-tracking/), [WP Affiliate forum](https://support.tipsandtricks-hq.com/forums/topic/wp-affiliate-first-click-does-affiliates-link-overwrite-our-own))
- **No-overwrite / first-click-sticky**: the platform ignores subsequent referral touches
  as long as the first touch is still within its window; code A keeps credit no matter how
  many other codes are seen later. This is offered as an opt-in setting on the same
  platforms, precisely because merchants disagree on which is fairer.
- GA4 takes a third position for its own session-scoped campaign dimensions: mid-session
  UTM changes normally do **not** override the session's original attribution unless the
  referrer is on GA4's paid-source override list — i.e., GA4 defaults to "ignore internal
  re-tags, only trust new external campaign touches," which is yet another variant of
  "some touches count, some don't" policy-making rather than a single universal rule.
  ([Analytics Mania](https://www.analyticsmania.com/post/utm-parameters-in-google-analytics-4/))

**Takeaway:** there is no single correct resolution for "A then B" — it's a business
policy choice (who gets the commission), and every real system implements it as a
*setting*, applied at read/scoring time against a full log of touches, not by mutating a
single "the" referral field at write time. This strongly supports storing every touch as
its own row (append-only) rather than a single "current referral" field that gets
overwritten in place.

## 4. Anonymous-to-known-user linkage

The standard pattern (CDP/analytics vendors: Segment, Tealium, Acquia) is:

1. On first observed visit, assign an anonymous identifier (cookie/session key) and log
   the touch(es) against it.
2. When the visitor authenticates/registers, "stitch" identity: the newly created `User`
   is linked to the anonymous identifier, and all touches previously logged under that
   anonymous ID are retroactively associated with the user. ([Segment](https://segment.com/docs/connections/spec/best-practices-identify/), [Tealium](https://docs.tealium.com/server-side/visitor-stitching/anonymous-user-visitor-id-attributes/))
3. This stitching typically only works within some bounded time/session validity — if the
   anonymous cookie already expired before signup, the pre-signup touches are unrecoverable
   (there is no ID left to stitch from). This mirrors the attribution-window vs
   cookie-TTL relationship in §2: the "window" for *anonymous → known* linkage is really
   just "however long we keep the anonymous session/identifier alive server-side."

Given the product decision already made ("track anonymous browsing and link it to the
User at signup"), the practical implication is:
- Store touches keyed by a durable **anonymous visitor/session identifier** (not by user,
  since the user doesn't exist yet).
- On signup, write a single linking event/foreign key from that anonymous identifier to
  the new `User`, rather than rewriting historical rows — this keeps an audit trail of
  "touch happened anonymously, was later attributed to user X on date Y" which is exactly
  the kind of provenance that makes it possible to apply *any* attribution model later.

## 5. Recommendation for this LMS

Given "store only for now" (no dashboard/webhook, no scoring logic needed yet):

1. **Do not encode an attribution model into the schema.** Don't add a single
   `referral_code` foreign key on `User` or on a session that gets overwritten in place
   when a new code is seen. That silently commits to last-touch-wins and destroys the
   data needed to ever compute first-touch, linear, or a custom "sticky for N days"
   policy later.

2. **Store every touch as an immutable, timestamped row** (append-only log), each
   recording at minimum: the referral code/UTM params observed, timestamp, the anonymous
   visitor identifier, the request path/referrer, and (once known) the linked `User`. This
   is exactly the pattern that lets a future feature compute first-touch, last-touch,
   last-touch-within-a-30-day-window, or GA4-style multi-touch entirely at query time,
   with zero schema migration — because the model becomes a `SELECT`/aggregation choice,
   not a write-time decision. This "store raw events, decide the model later" approach is
   consistent with how CDPs (Segment/Tealium) and analytics warehouses (GA4 → BigQuery)
   actually operate: the raw event/conversion-path log is the source of truth, and
   "attribution model" is a reporting-layer concept applied on top of it. ([Napkyn — GA4→BigQuery UTM attribution](https://www.napkyn.com/blog/advanced-utm-attribution-in-ga4-aligning-with-universal-analytics-using-bigquery))

3. **Do not implement conflict-resolution (A-then-B) logic now.** Since we're storing
   only, there is nothing to resolve yet — just make sure both touches are captured as
   separate rows with distinct timestamps so that *whichever* policy (overwrite/last-wins,
   sticky/first-wins, or windowed) is chosen later can be derived without re-instrumenting
   collection.

4. **No windows/expiry to implement yet either** — but do not silently expire/delete touch
   rows. Since attribution windows (7/30/90 days) are a scoring-time concept, and the
   external system owns commission logic anyway, the only thing this app needs to get
   right now is *not losing data* that a window calculation would need later (i.e. don't
   cap retention to "30 days then delete" — that would hard-bake a window nobody has
   decided on).

5. **Anonymous → known-user linkage**: store an anonymous visitor/session identifier on
   each touch row, and record a separate link (anonymous-id → `User`, with a timestamp)
   at signup rather than mutating historical rows to point at the user directly. This
   preserves the "was anonymous until this date" fact, which is itself useful metadata if
   attribution logic is added later (e.g., "only count anonymous touches from the last 30
   days before signup" is a plausible future business rule that requires this to be
   queryable, not just implicit).

In short: **treat this as an event log, not a scoring engine.** Every research question
above (which model, which window, how to resolve conflicts) is answerable later purely by
adding query/reporting logic on top of the stored touches — as long as the write path
never throws away a touch or collapses multiple touches into one mutable field.

---
status: ok
