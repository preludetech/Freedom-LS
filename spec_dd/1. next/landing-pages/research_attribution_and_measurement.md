# Research: attribution and measurement for landing pages

Scope: what landing pages need from `spec_dd/2. in progress/referal_tracking/` (hereafter "the
referral idea"), what the referral idea needs from landing pages, and what neither yet covers.

**Nothing in the referral idea is built.** A repo-wide search for `fc_attr`, `utm_`,
`attribution`, `referral`, `referrer`, `gclid`, `fbclid` across `freedom_ls/` and `config/` finds
no middleware, no cookie, no attribution model, no referrer table — only unrelated hits (HTTP
`Referrer-Policy` meta tags in content templates, a coincidental `referrer` match in
`markdown_rendering` tests). Every mechanism named below from the referral idea (`fc_attr`
cookie, `v`/`ref`/UTM capture, the referrer table, the attribution row) is a **proposal**, cited
as such, not existing code. Where this file describes FLS as it stands, it cites files that exist
today.

---

## 1. The seam between the two specs

### `landing_path` vs UTMs — what each carries that the other doesn't

The referral idea's capture list already includes `landing_path` (the request path the visitor
arrived on) alongside `utm_source/medium/campaign/content/term`. These are not redundant, but
they answer different questions and a landing-pages spec should say so precisely rather than
picking one:

- **`landing_path` identifies the page**, not the campaign. Two different adverts can point at
  the same landing page (`/lp/spring-cohort/`) with different `utm_campaign` values (a Google
  Search push vs a Facebook retargeting push), and one advert's link can appoint different
  `utm_content` values for creative-A/creative-B testing while `landing_path` stays fixed. If
  landing pages ever get reused across campaigns (likely — a developer authors one page per
  *offer*, not necessarily one per *campaign*), `landing_path` alone under-identifies the traffic
  source.
- **UTMs identify the campaign/channel/creative**, independent of which page they land on. A
  single campaign can send traffic to several pages (the landing page, the catalogue, a specific
  course detail page) and `utm_campaign` stays constant across all of them while `landing_path`
  varies.
- **They are not substitutable, but `landing_path` is the fallback when UTMs are absent** (see
  next point) — a link with no query string still carries page identity via the request path
  itself, which is why the referral idea captures it unconditionally rather than only when other
  parameters are present.

A landing-pages spec should say: UTMs name the *campaign*, `landing_path` names the *page*; a
report that groups by campaign groups on UTMs, a report that groups by page groups on
`landing_path`, and a landing page's own campaign-attribution story (see next point) is a third,
narrower mechanism that only helps when UTMs are missing.

### Does the "any GET carrying parameters" assumption hold for landing pages?

The referral idea's middleware trigger is "on any GET carrying parameters." Four landing-page
realities test that assumption:

- **A landing page with no query string at all.** A partner sends out a bare link
  (`https://.../lp/spring-cohort/`) with no `?ref=` or `?utm_*`. The middleware, triggered only
  by *parameters*, does nothing — `ref` and UTM fields stay unset in the cookie/session, but
  `landing_path` would still identify the page if the middleware also fires on parameter-less GETs
  to a page it recognises as a landing page (it is unclear from the idea's one-line "on any GET
  carrying parameters" whether that includes parameter-less GETs to a landing path; the idea does
  not currently distinguish). This is the strongest argument for point 3 below: a landing page
  declaring its own campaign identity server-side gives you attribution even when the URL is
  bare.
- **CDN/cache in front of a landing page.** A cache keyed only on path (not query string) would
  serve a cached response to `/lp/spring-cohort/?utm_source=google` and
  `/lp/spring-cohort/?utm_source=facebook` alike, but that is a caching-layer decision, not a
  middleware decision — the middleware runs Django-side, after any cache miss, and does not
  itself change. The risk is the opposite direction: if the landing page's *response* is cached
  and served from the edge without hitting Django at all, the middleware never runs and nothing is
  captured for that visit. Cache-key configuration (vary-by-querystring, or exclude landing pages
  from full-page caching) is a landing-pages concern, not a referral-tracking concern, and this
  spec should flag it as a dependency the referral idea cannot solve for it.
- **HTMX partial requests.** FLS's own deferred-login helper (`redirect_to_auth`,
  `freedom_ls/accounts/utils.py:110-139`) already special-cases HTMX: an `HX-Request` gets a 204
  with `HX-Redirect` rather than a 302, because "htmx follows a 302 inside its own XHR and swaps
  the target page's HTML into the element that made the request." If a landing page's CTA is an
  HTMX-driven button (the pattern used by `course_interest`'s express-interest CTA,
  `freedom_ls/course_interest/views.py`), the GET/POST that fires it is an XHR carrying no query
  parameters of its own — the UTM/`ref` parameters live on the *page* the visitor is already on,
  captured (or not) when that page first loaded, not on the CTA click. This is not a problem for a
  middleware that captures on page-load, but it does mean a landing page must not assume the
  attribution middleware re-fires on every subsequent interaction; the cookie/session written on
  first load is what the CTA click and any later signup rely on.
- **The `next=` parameter of the deferred-login flow.** `next` is a same-host path, validated with
  `url_has_allowed_host_and_scheme` (`spec_dd/3. done/2026-07-01_19:44_home_page/1. spec.md`
  §4.4, `freedom_ls/accounts/views.py:60-68`), and is never itself a UTM/`ref` carrier — it exists
  purely to route the visitor back after auth. It is a GET parameter, though, so if the referral
  middleware's "any GET carrying parameters" trigger is naive about *which* parameters justify a
  write, a login/signup URL like `/accounts/login/?next=/lp/spring-cohort/apply/` could
  spuriously re-fire the middleware on the login page itself. That is harmless only if the
  overwrite rules (UTMs/click-IDs last-touch, `ref` first-touch-never-overwritten) are applied
  consistently to a GET with *no* UTM/`ref`/click-ID parameters present — i.e. "no relevant
  parameters present" must mean "write nothing" rather than "clear existing attribution." The
  referral idea's one-line spec does not state this explicitly; it is a concern for whoever
  writes that spec, flagged and not designed here.

### Should a landing page declare its own campaign identity server-side?

Yes, and it does not duplicate the cookie/session capture — it is a different, complementary
identification path with a different failure mode:

- **Cookie/session capture answers "what did this URL's query string say?"** — it needs
  parameters to be present in the link.
- **A landing page declaring its own campaign identity server-side answers "which page is this?"**
  — it works with a bare URL, because the page itself (its slug, its developer-authored config)
  carries a fixed campcampaign/offer association that does not depend on what the visitor typed
  or what the ad platform appended.

Concretely: if each landing page is authored with its own identifying slug/config (the shape of
that config is landing-pages' own decision, not researched here), the landing-pages view can pass
that identity into the same capture mechanism the referral idea already uses for `landing_path`
— effectively treating the page's own campaign identity as a **fallback source for
`utm_campaign`-shaped attribution** when the URL carries none, not a second field that
duplicates or overrides `utm_campaign` when the URL *does* carry query parameters. The referral
idea's last-touch overwrite rule for UTMs would need to say explicitly that page-declared identity
never overwrites a UTM present on the URL, only fills the gap when none exists — again, a concern
for the referral spec to state, not to redesign here.

---

## 2. Carrying intent through a multi-step conversion

### The deferred-login mechanism already exists — reuse it, do not rebuild it

`spec_dd/3. done/2026-07-01_19:44_home_page/1. spec.md` §4 describes the shipped (per its
"3. done" location) deferred-login flow: an anonymous visitor's committing-action CTA either
links straight at a `@login_required` view (letting Django's own redirect build `?next=`,
§4.1) or, for HTMX-triggered actions, uses `redirect_to_auth` (`freedom_ls/accounts/utils.py:110`)
which threads `next_url` through `redirect_to_login` and handles the HTMX/non-HTMX response split.
`next` survives login, signup, and the post-signup `complete_registration` step (§4.3, the one
gap that spec had to close — `RegistrationCompletionMiddleware` was dropping `next` on its forced
redirect). `course_interest`'s deferred-express-interest view (`freedom_ls/course_interest/views.py:98`)
is a second, independent implementation of the same pattern with the same session-stash technique
for POST-only actions.

**Landing-page CTAs should reuse this verbatim, not build a parallel mechanism.** All four CTAs
named in the idea (sign up, apply, register interest, leave contact details) are "commit later,
after auth" actions for at least three of them (see next point on the fourth). `next` already
carries *where to send the visitor back to* through login/signup; it says nothing about
attribution and needs to say nothing about attribution, because attribution is being captured
independently, in the cookie/session, at first page-load — the two mechanisms are complementary
and should stay separate. A landing-pages spec should **not** try to smuggle campaign data through
`next` (e.g. `next=/lp/spring-cohort/?utm_source=...`) — that conflates "where to redirect" with
"what caused this visit," reopens the open-redirect surface `next` is deliberately kept narrow to
avoid (§4.4: "prefer server-constructed `next` targets... over client-supplied values"), and is
unnecessary because the cookie already holds the attribution data independent of `next`.

### The email-verification round trip is the risk — say plainly what survives it

`ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (`config/settings_base.py:404`) means every new
signup goes through allauth's email-confirmation flow before the account is usable, and
`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` means clicking the confirmation link logs the user
in. The confirmation link is delivered by email and can be, and often is, opened in a **different
browser or device** than the one that submitted the signup form — the referral idea's own
proposal writes the attribution row "in the same view that creates the account," which is the
signup-submission view, not the confirmation-click view.

Working through what that means concretely:

- **The signup-submission view runs in the original browser**, where `fc_attr` and the session
  exist. If the attribution row is written *there* — at signup submission, before email
  confirmation completes — it captures everything correctly, because the account already exists
  (allauth creates the `User` row at signup; confirmation only activates the associated
  `EmailAddress`) and the cookie/session are still present in that request.
  `AccountAdapter.save_user` (`freedom_ls/accounts/allauth_account_adapter.py:136-156`) already
  fires a `user.registered` webhook synchronously inside the signup view, which is the concrete
  evidence that "the same view that creates the account" is reachable and already does
  request-scoped work at signup time — the attribution write can hang off the same point.
- **If instead the attribution write were deferred to the confirmation-click view** (a plausible
  misreading of "on signup" as "once the account is confirmed"), it would silently lose
  attribution for every visitor who confirms on a different device — `fc_attr` and the session
  cookie belong to the browser that requested them, and a mobile-email-client tap on a desktop
  browser's signup link has neither. There is no reliable way to bridge a first-party cookie
  across that hop; server-side attribution data cannot follow an email link into a browser that
  never made the original request.
- **Practical implication for the referral idea's wording**: "the same view that creates the
  account" already resolves this correctly if read as *the signup-submission view*, and a
  landing-pages spec should say explicitly that it depends on that reading — the attribution row
  must be written at signup, not at confirmation. This is worth stating as an explicit dependency
  rather than assuming the referral spec's author intended it, since the sentence is ambiguous on
  its own.

### `heard_about` (simple-application-forms) is a second consumer of the same data

`spec_dd/2. in progress/simple-application-forms/idea.md` specifies a `heard_about` /
`heard_about_detail` field pair on the application form, prefilled `"Dealer — [name]"` when `ref`
is set. This reads the *same* `ref` value the referral idea's middleware captures, but as a
**form prefill at a different point in the flow** (application submission, which happens after
signup and login) rather than as a row write. Two consumers of one captured value:

1. The referral idea's attribution row (written once, at signup, keyed to the learner).
2. `simple-application-forms`'s `heard_about_detail` prefill (read from the cookie/session at
   application time, editable by the applicant).

They stay consistent only if both read the *same* stored value — the `ref` cookie/session field,
not a copy baked into the attribution row at signup that could drift if `ref` were (against the
idea's own first-touch-never-overwritten rule) somehow re-derived. Because `ref` is first-touch
and never overwritten per the referral idea, the value read by `heard_about_detail` at
application time (potentially days after signup) should equal the value written into the
attribution row at signup, *provided the cookie is still alive* — the referral idea's 90-day
`fc_attr` cookie lifetime is the binding constraint here, not the session (Django sessions expire
independently and are shorter-lived by default). A visitor who signs up, then applies more than
90 days later, or in a different browser, sees an unprefilled `heard_about` field — that is a
gap the application-forms spec should be aware it inherits, not something this file resolves.

### `course_interest` has the identical deferred-login problem, already solved the same way

`freedom_ls/course_interest/views.py` requires authentication to record interest
(`partial_express_interest`, `deferred_express_interest`), and solves the deferred-intent problem
with the same `redirect_to_auth` + session-stash pattern used elsewhere — an anonymous "register
interest" click on a landing page is not a new problem; it is the third instance of a pattern FLS
already has twice. A landing-pages spec should point at this pattern rather than re-derive it.

### The lead-capture CTA has nowhere to hang attribution — this is the central finding

The fourth CTA — "leave contact details without creating an account" — creates **no `User`,
`Learner`, `CourseApplication`, or `CourseInterest` row**. No model in FLS today represents a
contact-details-only lead; a repo-wide search for a lead/contact-capture model
(`class.*Lead`, `contact_detail`, `ContactRequest`) finds nothing. This is not a gap in the
search — it is a gap in the domain: FLS's identity chain runs `User` → `Learner` (per
organisation) → registrations/applications/interests, and every one of those needs a `User` to
key on.

The referral idea's attribution row is explicitly "keyed to the learner" and written "on signup."
A lead has neither. **If landing pages ship the lead-capture CTA in the same release as
attribution, the attribution row model as proposed cannot represent lead attribution at all** —
there is no learner to key the row on, and no signup event to hang the write off. Two honest
options exist and neither is designed here (that is the referral spec's decision, and the
landing-pages spec's decision about whether to ship the lead CTA at all in v1):

1. The lead-capture record itself (whatever new model represents "someone left contact details")
   carries its own copy of the cookie/session attribution fields directly, independent of the
   referral idea's learner-keyed row — meaning attribution logic would need to be written twice,
   once against `User` and once against whatever the lead model turns out to be.
2. Attribution for leads is out of scope for the first release, and the lead CTA either doesn't
   ship first, or ships unattributed.

State this as the single most load-bearing dependency this research surfaces: **the referral
idea's attribution row, as written, has no representation for a lead.** A landing-pages spec that
lists "leave contact details" as a first-release CTA is implicitly asking the referral idea to
either grow a second attribution surface or accept that this CTA is unattributed — that decision
belongs to whoever writes the landing-pages spec, informed by this finding, not to this research
file.

---

## 3. A/B variants

The referral idea reserves `v` (accepts only `a`/`b`, anything else defaults to `a`) — that is
purely a **capture mechanism** (which variant a request declares). Landing pages, to actually run
a test, need everything upstream and downstream of that capture:

- **Variant choice and rendering.** Something must decide, for a developer-authored template, which
  of two (or more, though the referral idea's field only anticipates two) variants a given visitor
  sees, and the template layer must be able to render either. FLS has no existing variant-selection
  mechanism to point at — this would be new landing-pages machinery, not something `v` capture
  provides on its own. `v` records the outcome of a decision that has to be made somewhere else.
- **Stickiness.** A visitor who reloads or returns must see the same variant they were first
  assigned, or the test is meaningless (and the CTA-through-signup funnel described in §2 would
  attribute a conversion to whichever variant happened to be live at signup, not the one that
  actually influenced the visitor). Stickiness needs either a cookie (separate from, or riding
  alongside, `fc_attr`) or deterministic hashing (e.g. of a session id) — not specified anywhere
  today.
- **Caching and SEO consequences of two versions at one URL.** Google's own guidance
  ([Search Central: A/B Testing Best Practices](https://developers.google.com/search/docs/crawling-indexing/website-testing))
  is explicit: use `rel="canonical"` on every variant pointing at the original URL so variants are
  treated as duplicates of one canonical page rather than indexed separately, and if the test
  redirects to a different URL for the variant, use a **302** (temporary), never a 301 — a 301
  tells search engines the redirect is permanent and gets the variant URL indexed instead of the
  original. A CDN or full-page cache sitting in front of a landing page (already a live concern
  from §1) compounds this: caching by URL alone would serve one variant to every visitor
  regardless of assignment unless the cache key includes the variant (or the variant assignment
  happens before any cacheable response is generated).
- **Sample-size honesty for a small deployment.** FLS's first deployment is a single South
  African site (§5). A meaningful A/B test needs enough independent conversions per arm to detect
  a real difference — for a landing page converting at, say, low single-digit percent, with
  traffic volumes in the hundreds or low thousands rather than the tens of thousands typical of
  A/B-testing case studies, reaching statistical significance within a useful timeframe is
  optimistic. Running a test that never reaches significance produces the appearance of rigor
  without the substance, which is worse than not testing at all if a decision gets made on noise.

**Recommendation:** A/B testing does not belong in the first release. It requires new
variant-selection/rendering/stickiness machinery the referral idea's `v` field alone does not
supply, adds caching and SEO complexity (canonicalization, cache-key variance) to pages that are
otherwise straightforward to cache and index, and is unlikely to reach a trustworthy sample size
at FLS's initial traffic scale. The referral idea's `v` capture costs nothing to keep reserved for
later use, but a landing-pages spec should treat it as exactly that — a reserved field, not a
committed feature — and scope actual variant testing out of v1.

---

## 4. What actually gets measured

### The funnel, and what FLS can already observe

Page view → CTA click → form started → account created → application submitted → course started:

- **Account created** is already an observable event: `AccountAdapter.save_user`
  (`freedom_ls/accounts/allauth_account_adapter.py:147`) fires a `user.registered` webhook
  synchronously at signup, one of exactly three event types FLS's webhook system knows about
  (`freedom_ls/base/webhook_event_types.py`: `user.registered`, `course.completed`,
  `course.registered`).
- **Course started** has no dedicated webhook event today — `course.registered` fires on
  registration (enrolment), not on first content access (`started_at` on `CourseProgress`, per
  the domain glossary, is a separate, later moment). Whether "course started" needs its own event
  is a question for whoever specs the funnel's instrumentation, not answered here.
- **Application submitted has no webhook event at all.** `course_applications` creates a
  `CourseApplication` row (`freedom_ls/course_applications/views.py:55`) with no corresponding
  entry in `FLS_WEBHOOK_EVENT_TYPES`. A landing-page funnel that wants to report "application
  submitted" as a measured step needs either a new webhook event type or a report that reads the
  `CourseApplication` table directly — the former is the outward-webhooks system doing what it's
  for (`spec_dd/3. done/2026-03-16_16:20_outward-webhooks/`); the latter is a reporting-layer
  decision (§ below).
- **Page view, CTA click, form started** are pre-account-creation events with no learner to key
  them on yet (the same identity gap as §2's lead-capture finding) — none of FLS's existing
  event/webhook plumbing observes anything before a `User` exists.

### Neither `webhooks` nor `xapi_learning_record_store` is the right destination for a landing-page conversion event

- **`freedom_ls/webhooks/`** is an *outward* delivery system — it pushes FLS-originated events to
  external endpoints (with an optional Jinja2 translation layer per
  `spec_dd/3. done/2026-03-18_13:49_webhook-translation-layer/1. spec.md`, for reshaping payloads
  to match e.g. Brevo or Slack). It is the right mechanism for *notifying an external system* that
  a landing-page conversion happened (e.g. pushing "application submitted" to a marketing
  automation tool), once such an event type exists — but it is not itself a place to store or
  query conversion data; `WebhookEvent`/`WebhookDelivery` rows exist to drive delivery attempts,
  not to serve as an analytics table.
- **`freedom_ls/xapi_learning_record_store/`** is unimplemented — `models.py` is entirely
  commented-out scaffolding (`Agent`, `AgentGroup`, `LearningExperience` are sketched, not real
  Django models) with a placeholder `apps.py`/`api.py`. It is not a working destination for
  anything today, landing-page events included, and building it out is a much larger undertaking
  than this idea's scope. xAPI's statement model (actor/verb/object) is also built for *learning*
  activity, not marketing funnel events — even once implemented, a landing-page page-view or
  CTA-click would be a stretch fit for its vocabulary.

Neither is the right place. A landing-page conversion event, if it needs a first-party record at
all, needs either a small dedicated model of its own or a new webhook event type layered onto the
existing outward-webhooks pipeline once an account/application exists to key it on — again, a
decision for the spec that owns this idea, not resolved here.

### Server-side vs client-side measurement

A first-party, server-side record (the referral idea's proposed cookie + attribution row) is not
merely an alternative to a Google Analytics-style tag — it is measurably more complete, for
reasons independent of GDPR/POPIA:

- **Ad blockers.** Client-side analytics tags are blocked at rates estimated between roughly 25%
  and 40% of browser traffic, and industry sources report server-side collection recovering
  20–40% more captured events than the equivalent client-side setup because a server-rendered
  first-party cookie write is invisible to a browser extension that only intercepts
  browser-initiated script requests
  ([ClickCease](https://www.clickcease.com/blog/how-much-traffic-can-ad-blockers-hide-from-ga4/),
  [Medium/Lukas Oldenburg](https://lukas-oldenburg.medium.com/ad-blockers-and-server-side-tracking-part-1-the-ever-more-challenging-world-of-client-side-ace3b1c049b)).
- **Safari ITP's 7-day cap on JavaScript-set cookies.** Safari's Intelligent Tracking Prevention
  caps any cookie written via `document.cookie` (i.e. client-side, by a tag like `gtag.js` or the
  Facebook pixel) at a 7-day lifetime, regardless of the `Max-Age` the script requests; a
  server-set cookie (written via an HTTP `Set-Cookie` response header on a genuine first-party
  domain) is not subject to that cap and can live for its declared lifetime
  ([Stape](https://stape.io/blog/safari-itp), [Datafly Signal](https://www.dataflysignal.com/blog/itp-7-day-cookies-and-how-to-fix-them)).
  This bears directly on the referral idea's own design: `fc_attr` is proposed as a 90-day
  cookie, which only survives that long in Safari if it is written **server-side** (via Django's
  response, as the middleware proposal implies) rather than client-side via JavaScript — a point
  worth confirming explicitly when that spec is written, since a JS-set fallback anywhere in the
  implementation would silently cap the cookie at 7 days for a meaningful share of mobile
  visitors. It also means the `_ga`/`_fbp`/`_fbc` values the referral idea proposes copying into
  the attribution row are themselves **client-set** (Google Analytics's and Meta's own tags write
  them via JavaScript) and therefore subject to the same 7-day Safari cap — a Safari visitor who
  first sees an ad and signs up more than a week later may already have lost `_fbc`/`_fbp` by the
  time the attribution row is written, independent of anything FLS does.
- **Chrome's current position** is not a driver of urgency here: as of 2026 Chrome has abandoned
  forced third-party-cookie deprecation in favour of a user-facing choice prompt
  ([OneTrust](https://www.onetrust.com/blog/google-may-not-deprecate-third-party-cookies-after-all/)),
  and `fc_attr` is a first-party cookie regardless, so Chrome's third-party-cookie stance does not
  bear on it directly — Safari's client-set-cookie cap is the relevant browser constraint here,
  not Chrome's third-party posture.

The practical takeaway for a landing-pages spec: a server-side record captures more of the true
traffic than a client-side tag would, for reasons that have nothing to do with legal compliance —
but it is not a substitute for GA-style behavioural analytics (scroll depth, time-on-page,
multi-page session paths), which genuinely need client-side instrumentation. The two serve
different purposes and a landing-pages spec should not present the first-party attribution
mechanism as replacing the value a GA-style tool would add, only as being more complete for
*conversion* measurement specifically.

### Consent: POPIA and ePrivacy/GDPR, and where a real legal review is needed

FLS's first deployment is South African, governed by POPIA; comparable EU deployments would sit
under the ePrivacy Directive and GDPR. This section states the shape of the question and flags
where legal review is required — it does not assert compliance for any specific FLS
implementation, because none exists yet to assess.

- **Client IP and user agent are personal information/personal data**, without qualification, in
  both regimes. Under POPIA, "personal information" explicitly extends to online identifiers
  including IP addresses and device/browser identifiers
  ([Termageddon](https://termageddon.com/protection-of-personal-information-act-popia-compliance-guide/),
  [Mondaq: "ID Like To Know" — Unique Identifiers Under POPIA](https://www.mondaq.com/southafrica/data-protection/1813672/id-like-to-know-unique-identifiers-under-popia)).
  The referral idea proposes capturing exactly these two fields (client IP and user agent) into
  the attribution row at signup. FLS already has a sanctioned helper for client IP capture —
  `get_client_ip` (`freedom_ls/accounts/utils.py:20-57`), used today for `LegalConsent` records
  and django-axes lockouts, explicitly documented as "the only sanctioned way to derive a client
  IP" for evidence trails. A landing-pages/referral implementation should reuse that helper rather
  than deriving IP a second way, both for consistency and because it already encodes the
  proxy-header trust decisions this deployment has made.
- **A `ref`/UTM/click-ID attribution cookie is not "strictly necessary"** under the ePrivacy
  Directive's consent exemption, which is interpreted narrowly to cover only cookies essential to
  a service the visitor explicitly asked for (login sessions, shopping carts) — "if the site
  still works for the user without the cookie, it is not strictly necessary"
  ([pii.ai](https://www.pii.ai/blog/Strictly-Necessary-Cookies-a-Cookie-Consent-Exemption-A-Guide-for-eCommerce)).
  A marketing-attribution cookie exists to benefit the site operator's reporting, not to deliver
  something the visitor asked for, so under ePrivacy/GDPR it would need consent before being set,
  the same as an analytics or advertising cookie — even though it is first-party and even though
  it stores no name/email. "Even anonymized analytics cookies require consent under ePrivacy" is
  the general position; a narrow first-party-audience-measurement exemption exists in some
  jurisdictions (e.g. France's CNIL) under strict conditions (aggregated, not shared with third
  parties, limited retention) but that is a jurisdiction-specific carve-out, not a general EU rule
  ([Legiscope](https://www.legiscope.com/blog/cookie-consent-compliance-guide.html)).
- **POPIA's framing is different in mechanism but similar in effect.** POPIA requires "voluntary,
  specific and informed" consent for processing personal information, and cookie IDs/IP addresses
  qualify as personal information subject to that requirement
  ([CookieYes: POPIA](https://www.cookieyes.com/blog/popia-south-africa/)). POPIA does not have
  ePrivacy's specific "cookie" carve-out structure, but the practical requirement — a landing page
  that writes `fc_attr` and later captures IP/user-agent needs a lawful basis, and consent is the
  most defensible one for marketing attribution specifically — lands in roughly the same place: a
  consent mechanism (banner or equivalent) is very likely needed before the attribution cookie is
  set, not just before a Google Analytics tag fires.
- **What this means for a landing page's consent banner and conversion.** If the attribution
  cookie legally needs consent before being written, a landing page's *first* GET (an advert
  click, carrying the UTM/`ref`/click-ID parameters that make the whole scheme work) is exactly
  the request the middleware needs to capture — and exactly the request that precedes any consent
  interaction. A banner that blocks the write until the visitor clicks "accept" loses first-touch
  attribution for every visitor who doesn't accept, or who converts before deciding. This is a
  real tension between the referral idea's design (capture on the very first GET) and a
  consent-gated implementation, and it is not resolved by anything researched here.
- **This is exactly where a real legal review is needed, not an inference from these sources.**
  The specific facts that matter — whether FLS's attribution cookie qualifies for any narrow
  exemption, what POPIA's "operator" vs "responsible party" distinctions mean for a
  multi-tenant SaaS platform serving several client organisations' sites, whether a South African
  deployment with EU-facing traffic needs to satisfy both regimes simultaneously — are legal
  questions this research file is not qualified to answer and does not attempt to. State the
  attribution cookie's likely consent requirement as a design constraint for whichever spec
  implements it, and get that constraint confirmed by counsel before shipping, rather than
  building on the assumption used above.

### Reporting: no existing surface fits; Django admin + CSV export is the honest first answer

`freedom_ls/reports/` generates PDF cohort-progress reports for educators
(`GeneratedReport`, `freedom_ls/reports/models.py:42`) — a per-cohort, per-learner-progress
artifact, not a marketing/campaign performance surface, and has no natural extension point for
"conversions by UTM campaign" without building something new inside it.
`freedom_ls/educator_interface/` is scoped to educators managing cohorts and viewing learner
progress (per `docs/app_structure.md`'s app description) — again, not a fit for campaign
reporting, which is a builder/admin concern, not an educator one. Neither surface should be
stretched to cover this. FLS has no existing CSV-export convention to point to either — a
repo-wide search for CSV export patterns finds nothing outside `educator_interface`'s own report
downloads. The honest first answer for "who sees campaign performance" is the Django admin over
the attribution/application/registration tables, plus a CSV export if aggregate reporting is
needed sooner than a dedicated dashboard — building a bespoke campaign-reporting UI is a
follow-on decision, not a first-release necessity.

---

## 5. Multi-site

`freedom_ls/site_aware_models/` and the `fls-dev:multi-tenant` skill establish that `Site` is
the tenant and isolation boundary, and every `SiteAwareModel` auto-filters by the current site
(`claude_plugins/fls-dev/skills/multi-tenant/SKILL.md`). Applied to attribution and campaign
identity:

- **Referral codes and campaign identity are very likely per-site.** A partner organisation
  handed a referral code for one tenant's platform should not have that code recognised (or, worse,
  silently accepted) on a different tenant's site — the referral idea's proposed "referrer table"
  validation (`ref` checked against both a regex and a referrer table) would need to be a
  `SiteAwareModel` like everything else, so a code registered for site A's referrer table is
  invalid on site B by construction, not by extra application logic. This is not designed here;
  it is the natural consequence of the multi-tenant convention already in force.
- **Cookie scope across domains.** Each `Site` in FLS's multi-tenant setup is a distinct domain
  (the `sitemap`/`robots.txt` work in the home-page spec §5.3–5.4 builds per-tenant-domain URLs
  precisely because sites are separate domains, not path prefixes on one domain). A cookie set on
  one tenant's domain does not exist on another's — there is no cross-site cookie-scope problem
  to solve, because there is no shared domain for a cookie to leak across. This works in
  landing-pages' favour: `fc_attr` set while visiting site A's landing page is simply absent on
  site B, which is the correct behaviour for tenant isolation, not a defect to fix.
- **Per-site reporting** follows directly from `SiteAwareManager`'s automatic filtering — Django
  admin access to attribution/application data, scoped correctly per site, requires no extra
  design beyond what every other `SiteAwareModel` in FLS already gets. A campaign-performance
  report (§4) would need to be either run per-site (the default, automatic case) or, if a
  platform operator ever needs a cross-site rollup, would have to explicitly bypass
  `SiteAwareManager`'s filtering the way `dispatch_event` in `freedom_ls/webhooks/events.py:48-93`
  does for background-task contexts with no ambient request — a deliberate, explicit choice each
  time, not something to allow by default.

---

status: ok
