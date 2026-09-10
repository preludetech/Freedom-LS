# Research: mechanics of first-party server-side attribution capture

Scope: evidence on capture mechanics only — first-touch/last-touch semantics, cookie/session
storage, the 90-day window, which click-ID parameters matter, `Referer` reliability, failure
modes, and field sizing. Written against the current draft (middleware on GET with query
params, 90-day first-party cookie + session, per-user row written once at signup).

## Findings that would change a design decision

1. **The draft's first-touch/last-touch split is directionally normal but the labelling is
   backwards for one thing you actually want.** Mature systems (HubSpot, Salesforce-adjacent
   marketing tooling) keep *two full parallel sets*, not a per-field mix: an "Original Source"
   (first-touch, frozen forever) and a "Latest Source" (last-touch, overwritten every visit)
   [HubSpot Original Source vs Latest Source](https://www.iv-lead.com/hubspot-by-iv-lead/understand-original-and-latest-source-properties),
   [HubSpot UTM tracking guide](https://www.terminusapp.com/blog/hubspot-utm-tracking-definitive-guide/).
   Mixing granularity — UTMs last-touch but `ref` first-touch, inside the *same* row — produces a
   record that is neither a clean first-touch nor a clean last-touch view: if a user clicks a
   referrer-code link in January and then arrives again in March via a paid ad, the stored row
   says "referred by partner X, campaign Y" — a combination that never actually happened
   together. This is interpretable only if the two fields are documented as independently-scoped,
   not as one coherent "how did they get here" story. **Recommendation for the idea doc to
   consider:** either (a) explicitly document that `ref` and UTM fields are independently scoped
   (first-touch survives regardless of subsequent UTM traffic, and that's a deliberate partner-
   protection decision, not an attribution model), or (b) store both a first-touch UTM set and a
   last-touch UTM set (doubles the field count but matches established practice and removes the
   ambiguity). Given FLS's only consumer is Django admin CSV export, option (a) is cheaper and
   probably sufficient if labelled clearly in the admin (e.g. `ref_code` documented as "first
   touch, sticky" vs `utm_*` documented as "most recent touch").

2. **Writing to the Django session on every anonymous GET that carries query parameters is a
   known footgun and should not be the primary store.** Django only writes a session row when
   the session dict is *modified*; touching `request.session['whatever'] = x` on an anonymous
   GET forces a session row to be created and a `Set-Cookie: sessionid=...` to be sent to every
   visitor who lands with any query parameter — including every bot and every ad click — even
   though they may never sign up. This is a documented real-world problem (django-users thread
   reports "10K session rows in one day" from this exact pattern)
   [Django sessions docs](https://docs.djangoproject.com/en/5.0/topics/http/sessions/),
   [django-users SESSION_SAVE_EVERY_REQUEST thread](https://groups.google.com/g/django-users/c/99f3N6Wnb6Q).
   It also silently changes cacheability (see finding 4) and forces a cookie on users who might
   otherwise never receive one. **The cookie should be the source of truth; the session should
   not be written to on every GET.** If session state is wanted as a convenience during the
   current browser tab's lifetime, write it only once per session (e.g. only if not already
   present), not unconditionally.

3. **CDN/reverse-proxy caching is a real hazard for a middleware that reads query params and
   sets cookies on GET.** If any caching layer sits in front of Django (even just a CDN for
   static/media, or a future page cache), a middleware that (a) varies its `Set-Cookie` behaviour
   by query string and (b) is not excluded from caching can leak one visitor's attribution cookie
   to another, or can prevent caching entirely if `Vary: Cookie` is naively added. `Vary: Cookie`
   or `Vary: *` effectively disables caching for that response; the standard fix is to strip
   `Set-Cookie` at the edge for cacheable routes and to normalize/strip tracking query parameters
   from the cache key rather than varying cache entries by them
   [CDN cache keys and Vary headers](https://www.webstackbuilders.com/articles/cdn-edge-caching-cache-keys-vary-headers),
   [Google Cloud CDN cache key guidance](https://oneuptime.com/blog/post/2026-02-17-how-to-configure-cache-key-policies-to-improve-hit-ratios-in-google-cloud-cdn/view).
   Concretely: this middleware must only run (or only set cookies) on responses that are already
   uncacheable (i.e. normal authenticated/dynamic Django views), and must never be relied on for
   any URL that a CDN might cache verbatim (landing pages behind a CDN, static marketing pages
   served by a different system). If FLS's landing/marketing pages are ever served through a CDN
   in front of Django, cookie-setting-on-GET must be excluded from cached routes or done via a
   client-side beacon instead.

4. **Query parameters and the pre-signup cookie do not reliably survive OAuth/social-login or
   email-verification round trips unless deliberately carried through.** This is a widely
   reported gap: OAuth redirect URIs and post-verification return targets are commonly lost
   because the provider's callback URL is fixed and doesn't carry the original query string
   forward, and many implementations reset to a default landing page after email confirmation
   [Dynamic Yield: "UTMs are being lost in redirects"](https://support.dynamicyield.com/hc/en-us/community/posts/360009906757-UTMs-are-being-lost-in-redirects-Can-this-be-fixed),
   [OpenStreetMap `oauth_return_url` gets lost during registration](https://lists.openstreetmap.org/pipermail/rails-dev/2025-June/041901.html).
   The first-party cookie approach in the draft (90-day cookie set at landing, read at signup)
   is actually the *robust* answer to this — because attribution isn't threaded through the
   OAuth/email-verification URL chain at all, it survives independently of those redirects, as
   long as the cookie's `Domain`/`SameSite` scope covers wherever signup actually completes. The
   risk is narrower than the general problem: it only breaks if (a) the OAuth provider or email
   link opens in a different browser/device than the one that landed (very common — mobile email
   client vs. desktop browser), in which case no cookie-based approach can survive it, and there
   is no server-side fix for that without an account-linking or magic-token bridge; or (b) the
   landing subdomain and signup subdomain differ and cookie `Domain` isn't set to the parent
   domain (see finding 5).

5. **Cross-subdomain landing/signup breaks silently unless `Domain` is set to the parent
   domain.** A cookie set with no explicit `Domain` is host-only and invisible to other
   subdomains; a cookie set with `Domain=example.com` is visible to all subdomains
   [cross-domain cookie tracking overview](https://docs.descope.com/security-best-practices/crossite-cookies),
   [Simo Ahava: cross-domain tracking across subdomains](https://www.simoahava.com/analytics/cross-domain-tracking-across-subdomains/).
   If marketing/landing pages live on `www.` or a campaign subdomain and signup happens on
   `app.` or a site-specific subdomain (FLS is explicitly multi-site/multi-tenant via
   `site_aware_models`), the attribution cookie must be set with `Domain` scoped to the shared
   parent domain, not the specific host — otherwise every cross-subdomain journey silently loses
   attribution and shows as organic/direct with no error. Given FLS is multi-tenant per site,
   this needs an explicit decision: is there always a shared parent domain across a tenant's
   subdomains, or can tenants use fully separate domains where cross-domain attribution is
   simply impossible without a server-side bridge (redirect-with-query-string handoff)? This is
   worth resolving in the idea doc rather than discovering later.

## 1. First-touch vs last-touch

- Single-touch models (100% credit to one touch) are the industry baseline vocabulary:
  first-touch credits the initial interaction, last-touch credits the final one before
  conversion
  [First-Touch vs Last-Touch overview](https://avidtrak.com/resource/first-touch-vs-last-touch-attribution),
  [DiGGrowth on ROI decoding](https://diggrowth.com/blogs/data-management/first-touch-vs-last-touch-reports-decoding-roi-in-marketing-attribution/).
- Mature CRM/marketing-ops tooling (HubSpot's Original Source / Latest Source is the clearest
  documented example) stores **both** as parallel, independently-updated field sets rather than
  blending granularity within one record
  [HubSpot Original vs Latest Source](https://www.iv-lead.com/hubspot-by-iv-lead/understand-original-and-latest-source-properties).
  "Run both models in parallel" is called out explicitly as the practical recommendation until a
  team has volume for true multi-touch
  [stackmatix First-Touch vs Last-Touch](https://www.stackmatix.com/blog/first-touch-vs-last-touch-attribution).
- Given FLS's stated scope (Django admin only, no dashboards, no multi-touch modelling), full
  multi-touch is over-engineering. The realistic choice is between (a) the draft's mixed
  first/last split, documented clearly, or (b) doubling the UTM fields into first-touch and
  last-touch copies. See Finding 1 above.

## 2. Cookie vs session vs both

- Recommended baseline for any first-party tracking cookie: `Secure`, `SameSite=Lax` (not
  `Strict`, since the whole point is the cookie must survive a cross-site navigation arriving
  from an ad or partner link — `Strict` cookies are not sent on top-level cross-site navigation
  in some browsers' interpretations, though `Lax` does permit top-level GET navigations, which
  is the relevant case here), and `HttpOnly` if the value is never read by client-side JS (which
  it isn't in this design)
  [cookie security flags overview](https://inventivehq.com/blog/what-do-secure-httponly-samesite-cookie-attributes-do).
- **Size**: individual cookies are capped at ~4096 bytes by browser convention (RFC 6265 requires
  browsers to accept at least 4096 bytes per cookie), and browsers cap total cookies per domain
  (commonly cited: ≤50 cookies/domain for broad compatibility, though Chrome allows up to ~180)
  [browser cookie limits reference](http://browsercookielimits.iain.guru/),
  [RFC 2109/2965/6265 cookie size](https://ingestlabs.com/browser-cookie-limitation-modern-browsers/).
  The proposed payload (ref, 5 UTMs, gclid, fbclid, landing path, Referer, timestamp) as a
  compact JSON or delimited string is realistically 150–400 bytes depending on path/Referer
  length — comfortably under the 4096-byte cap, but landing path and `Referer` are the
  unbounded-length fields worth truncating explicitly (see §7).
- **Domain**: see Finding 5 — must be set to the shared parent domain if landing and signup can
  occur on different subdomains, otherwise the cookie is host-only.
- **Cookie vs session**: the cookie is the durable pre-signup store (survives redirects, new
  tabs, days/weeks between landing and signup); the session is a same-browser-session
  convenience only and should not be written unconditionally (Finding 2). A defensible pattern:
  read-only session use (e.g. avoid re-parsing the cookie on every request) is fine; writing to
  the session on every anonymous GET is not.

## 3. The 90-day window

- 90 days is not an arbitrary number — it is Google Analytics 4's default lookback/attribution
  window for most non-acquisition conversion events (GA4 allows 1–90 days, replacing the old
  fixed 1/7/14/30/60/90 presets), while GA4's *acquisition* events (`first_open`/`first_visit`)
  default to 30 days
  [GA4 AttributionSettings](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1alpha/AttributionSettings),
  [GA4 attribution window guidance](https://avanahub.com/blog/ga4-attribution-window).
  Universal Analytics (GA's predecessor) used a 6-month window for its acquisition/`_utmz`
  cookie, so "90 days" is itself already a *tightening* relative to the older standard, not the
  historical default
  [UTM parameters / _utmz history](https://en.wikipedia.org/wiki/UTM_parameters).
- Common alternatives seen in the wild: 30 days (short B2C sales cycles, GA4 acquisition
  default), 90 days (GA4 general default — matches the draft), and 6 months–1 year for long B2B
  sales cycles. There's no universal "correct" number; it's a trade-off between attribution
  accuracy (longer = captures longer consideration journeys) and false-positive risk (longer =
  more chance an unrelated later signup gets credited to a stale ad click). 90 days is a
  reasonable, industry-recognizable default for FLS to keep, but it should be treated as a
  configurable/documented business decision, not a technical constant.
- What happens when the journey exceeds it: the cookie simply expires and is not resent: the
  visitor who returns after day 91 without parameters looks identical to a fresh
  direct/organic arrival — no error, no gap marker, just silent reversion to "no attribution."
  This is the same behaviour as GA4 and every cookie-based system; it's expected, not a bug, but
  worth stating explicitly so nobody is surprised the admin CSV shows blank attribution for a
  91-day-later signup.

## 4. Click identifiers worth capturing beyond the 5 UTMs

- **`gclid`** — Google Ads' original per-click identifier since 2008. Still the primary
  identifier for Google Ads web conversions.
- **`gbraid`** — privacy-preserving identifier used specifically for iOS web-to-app journeys from
  Google web ads.
- **`wbraid`** — the reverse: appended when an iOS user clicks a Google *in-app* ad landing on a
  website. Both `gbraid`/`wbraid` were introduced to survive iOS ATT/App Tracking Transparency
  constraints and, notably, **survive Safari Private Browsing (including "full protection")
  where `gclid` does not**
  [gclid vs gbraid vs wbraid explainer](https://enalitica.com/blog/gclid-vs-gbraid-wbraid-google-ads-click-ids),
  [Safari stripping gclid — ppc.land](https://ppc.land/safari-is-quietly-killing-your-gclid-and-here-is-the-fix/).
- **`fbclid`** — Meta/Facebook Ads. **`msclkid`** — Microsoft (Bing) Ads. **`ttclid`** — TikTok
  Ads. **`li_fat_id`** — LinkedIn Ads. All function the same way: a per-click token the ad
  platform can use for server-side conversion matching
  [click ID reference — Terminus](https://www.terminusapp.com/blog/utm-vs-gclid-vs-fbclid-vs-ttclid/),
  [click ID glossary — leadtrackr 2026](https://leadtrackr.io/learn/advertising-click-ids).
- **Deprecation/reliability note**: Safari Private Browsing mode strips `gclid`, `dclid`,
  `fbclid`, `msclkid`, and `ttclid` from URLs automatically before the page even loads;
  `gbraid`/`wbraid` are specifically designed to survive that stripping
  [Safari gclid stripping](https://ppc.land/safari-is-quietly-killing-your-gclid-and-here-is-the-fix/).
  This means: capturing `gclid` alone increasingly under-counts Safari traffic; if Google Ads
  traffic matters to FLS's partners, `gbraid`/`wbraid` are the more future-proof pair to add
  alongside `gclid`, not instead of it.
  **Recommendation for the idea doc:** if there's realistic near-term appetite for Google Ads
  attribution specifically, add `gbraid`/`wbraid` now rather than treating them as a later
  addition, since they're low-cost (two more string columns) and directly address a known and
  worsening gap in `gclid` alone. `msclkid`, `ttclid`, `li_fat_id` are lower priority unless FLS
  or its partners actually run campaigns on those platforms — capturing them "just in case" is
  cheap but adds columns with likely near-zero fill rate.

## 5. The `Referer` header

- Modern browsers (Chrome since v85, and this is now the de facto cross-browser default) send
  `strict-origin-when-cross-origin` as the referrer policy when a site sets none explicitly. That
  means: **same-origin navigations still get the full URL; cross-origin navigations get only the
  scheme+host+port (no path, no query string); and the header is omitted entirely on an HTTPS→HTTP
  downgrade**
  [Chrome referrer-policy default change](https://developer.chrome.com/blog/referrer-policy-new-chrome-default/),
  [MDN Referrer-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy).
- Practical consequence for FLS: for a genuine external referral (partner site → FLS signup
  page), the stored `Referer` value will almost always be just the partner's origin
  (`https://partner.example.com`), never their path — so it's useful for "which domain sent this
  visitor" but not for "which page on their site." That's still a real signal worth storing
  (distinguishing partner domains, or catching unexpected referrers), but the idea doc shouldn't
  overstate its precision.
- It's also unreliable/absent whenever: the referring page sets `rel="noopener noreferrer"` on
  the link, the referring site sends `Referrer-Policy: no-referrer`, the user arrives via a
  bookmark/typed URL/most password managers/many email clients (these commonly strip or omit
  Referer entirely), or navigation happens via a redirect chain that drops it. This is exactly
  the mechanism that inflates "(direct)/(none)"-style buckets in every analytics platform
  [web.dev referrer best practices](https://web.dev/articles/referrer-best-practices),
  [(direct)/(none) explainer](https://support.google.com/analytics/answer/15258820?hl=fr).
- **Verdict**: worth storing (cheap, occasionally useful, especially for confirming a referrer
  code's partner-site origin actually matches expectations), but it should never be treated as a
  reliable or complete signal and the idea doc should not lean on it as a primary attribution
  field — `ref`/UTMs are the reliable mechanism; `Referer` is corroborating metadata at best.

## 6. Failure modes and pitfalls (priority section)

- **Bot/crawler inflation.** Industry estimates put bot/crawler share of raw web traffic
  extremely high (one source cites 80–95% of "observed traffic" as AI-bot/crawler-driven in
  2026), and bots that follow ad links or crawl marketing URLs with UTM parameters intact will
  create attribution rows with no possibility of ever converting, unless the row is only created
  at signup (which the draft already does — the per-user row is written once at signup, not per
  visit). This substantially de-risks the *stored* data from bot pollution, since a crawler will
  essentially never complete a signup form. The remaining bot risk is narrower: automated
  account-creation abuse (credential-stuffing bots, fake-signup bots) *would* produce polluted
  per-user attribution rows, but that's an account-abuse problem, not an attribution-mechanism
  problem, and is out of scope here
  [bot traffic and attribution — taggrs](https://taggrs.io/filter-bot-traffic/),
  [Cloudflare BotBase/Attribution Business Insights](https://developers.cloudflare.com/changelog/post/2026-07-01-botbase-attribution-business-insights/).
- **Session churn from writing on every anonymous GET.** Covered in Finding 2 — this is the
  single highest-value mechanical risk in the draft as described, because it's an operational
  cost (session table growth, forced cookies) that scales with *all* traffic including bots and
  bounces, not just signups.
- **CDN/cache interaction.** Covered in Finding 3.
- **Survival across OAuth/email-verification round trips.** Covered in Finding 4 — the
  cookie-based approach is inherently more robust here than URL-parameter-threading, but only
  within the same browser/device.
- **Parameter injection / malicious values.** Query parameters are fully attacker-controlled —
  anyone can craft a landing URL with arbitrary `utm_source` etc. Concrete risks:
  - *Oversized values*: an attacker can send arbitrarily long query strings; without an explicit
    max length on each captured field, a single crafted URL could bloat the cookie past the
    ~4096-byte cap (silently dropping the whole cookie in some browsers) or bloat the database
    row. Truncate every captured field at ingestion (see §7).
  - *Control characters / unicode*: values can contain newlines, null bytes, RTL-override
    characters, zero-width characters, or emoji-heavy unicode designed to break admin-list
    rendering or CSV parsing. Strip/reject control characters (`\x00`-`\x1f` except normal
    whitespace) at capture time.
  - *CSV formula injection*: this is the concrete, well-documented risk for the "Django admin CSV
    export" consumer named in scope. If any captured field (most plausibly `ref`, `utm_campaign`,
    `utm_content`, or landing path) starts with `=`, `+`, `-`, or `@` (or certain unicode
    homoglyphs of them), and that value is written verbatim into a CSV cell, Excel/Sheets will
    interpret it as a formula when opened — enabling data exfiltration or arbitrary command
    execution via DDE in older Excel versions. Standard mitigation: at CSV-export time (not
    necessarily at capture time), prefix any cell value starting with a formula-trigger character
    with a single quote `'` or a leading `\t`/space to force text interpretation, after also
    checking for the character appearing after a field-separator/quote in a way that could start
    a new cell. This is a well-established, named vulnerability class (OWASP has a specific test
    guide for it) and directly applicable to this feature's stated CSV-export consumer
    [OWASP CSV Injection testing guide](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection),
    [CSV/formula injection prevention overview](https://www.cyberchief.ai/2024/09/csv-formula-injection-attacks.html).
  - *Header/log injection*: if the `Referer` header or any query param is ever written into a log
    line, HTTP response header, or email without escaping, CRLF sequences in the value could
    inject fake log lines or (if ever reflected into a header) split the HTTP response. Standard
    mitigation is to strip `\r`/`\n` from captured values before storage/use, and never reflect
    captured attribution values into response headers.
- **Duplicate/conflicting parameters** (`?utm_source=a&utm_source=b`). Django's `QueryDict`
  resolves `.get()`/`request.GET['key']` to the **last** value when a key repeats — this is
  documented, intentional Django behaviour, not a bug
  [Django QueryDict duplicate-key behaviour](https://groups.google.com/g/django-developers/c/snBepnO5AjY).
  That's a reasonable default to rely on (last value wins) but should be stated explicitly in the
  idea doc so it's a deliberate choice rather than an accidental one, since "last wins" for a
  *first-touch* field like `ref` interacts oddly with the first-touch/last-touch design if
  someone crafts `?ref=partnerA&ref=partnerB` on a single landing URL.
- **No parameters at all (direct/organic).** Every mature analytics platform has a dedicated
  representation for this rather than leaving fields null-and-indistinguishable-from-error — GA's
  `(direct)/(none)` is the canonical example, explicitly meaning "no UTM parameters and no usable
  referrer," and is deliberately a visible category rather than blank rows
  [(direct)/(none) explainer](https://support.google.com/analytics/answer/15258820?hl=fr). FLS's
  admin should adopt the same principle: an explicit stored value (e.g. a literal `"direct"` or
  a boolean/enum flag) for "no attribution data was present at all," distinct from "attribution
  cookie existed but this specific field was empty," so the admin list/filter/CSV export doesn't
  conflate "we have no idea" with "the field wasn't set." This also matters for the 90-day-expiry
  case (Finding, §3) — a lapsed-cookie signup and a genuinely-organic signup will look identical,
  which is expected but worth a one-line note in the doc.

## 7. Field sizing and normalisation

- **Max lengths** (inference, not a cited standard — these are pragmatic bounds informed by the
  4096-byte total cookie budget and typical real-world UTM usage): UTM fields and `ref`/click-IDs
  are conventionally short tokens (tens of characters); a generous but defensive cap of 200–255
  characters per field comfortably covers legitimate use while bounding worst-case cookie/row
  size. Landing path and raw query string are the fields most likely to be long or attacker-
  controlled and deserve an explicit, tighter cap (e.g. 500 characters) with truncation (not
  rejection) so capture never hard-fails a legitimate but verbose URL.
- **`Referer`** should also be capped — per finding in §5, with `strict-origin-when-cross-origin`
  as the modern default, a genuine cross-origin `Referer` is just an origin (short), so a cap
  around 255 characters is generous; same-origin referrers (which leak full URLs) are the case
  that could be long, and truncation is the right response rather than rejection.
- **Case normalisation**: UTM values are frequently entered inconsistently by different people
  building campaign links (`Google` vs `google` vs `GOOGLE`). Lower-casing `utm_source`/
  `utm_medium` at capture time (but *not* `utm_campaign`/`utm_content`/`utm_term`, which are often
  meaningfully mixed-case identifiers or free text) is a common practical normalisation to avoid
  the admin list fragmenting into near-duplicate values. This is inference from common analytics
  practice, not a cited standard.
- **Whitespace**: strip leading/trailing whitespace on all captured string fields; reject/ignore
  (rather than store) an all-whitespace value as equivalent to absent.
- **Store the raw query string too?** Storing the raw, undecoded query string alongside parsed
  fields is worth doing — it's cheap (bounded by the truncation above), and it's the only way to
  debug "why didn't this get parsed correctly" after the fact (encoding oddities, unexpected
  parameter names, a partner's link builder producing something slightly off-spec) without being
  able to reproduce the original visit. The main cost is it duplicates data already captured in
  parsed form and needs the same injection defenses (control-character stripping, CSV-formula
  escaping at export) as every other field, since it's just as attacker-controlled.

---

status: ok
