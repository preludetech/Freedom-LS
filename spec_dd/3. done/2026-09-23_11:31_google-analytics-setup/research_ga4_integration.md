# Research: GA4 base integration for FLS (page views + wiring)

Scope: the base gtag.js load, measurement ID setting, CSP, dev/staff exclusion, and
coexistence with PostHog. Custom event tracking scope is covered by a sibling
research file — this one stops at "page views work correctly and nothing else is
double-loaded."

## 1. Current PostHog pattern (precedent to mirror)

- `freedom_ls/deployment/config.py` — `DeploymentSettings(AppSettings)` declares
  `POSTHOG_API_KEY: str | None` with `Setting(default=None)`, plus a host setting
  with a real default (`POSTHOG_API_HOST` defaults to the region host) and an
  optional UI host. The comment there is explicit: "declared here to own the
  region-host default; the client-side snippet (context processor + `_base.html`)
  reads these."
- `freedom_ls/deployment/context_processors.py` — `posthog_config(request)` returns
  a plain dict of the three values read from `deployment_config`, nothing else.
- `config/settings_base.py` — raw env reads live near line 540 under a `# PostHog /
  Sentry` comment (`POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")`, etc.),
  and the context processor is registered in `TEMPLATES[0]["OPTIONS"]
  ["context_processors"]` at line 196.
- `freedom_ls/base/templates/_base.html` — the whole snippet is wrapped in `{% if
  posthog_api_key %}`; nothing is loaded when the key is unset. This is the single
  gate — there's no separate `POSTHOG_ENABLED` flag.
- `docs/product/deployment.md` line 30: "**Analytics (PostHog)** — a client-side
  snippet configured by project token and region host. With no token set the
  snippet does not render, so development deployments send nothing." This is the
  sentence GA4 should get an equivalent of.
- Tests (`test_context_processors.py`) cover: key set → renders with host; key
  unset → snippet absent; host override; UI host conditional rendering. The GA4
  equivalent should mirror this shape (config-returns-right-values tests + a
  snippet-presence/absence test through the test client).

**Recommendation:** don't invent a new pattern. Add `GOOGLE_ANALYTICS_MEASUREMENT_ID`
(see §8) to the same `DeploymentSettings` class, a `google_analytics_config` context
processor next to `posthog_config`, and an `{% if google_analytics_measurement_id %}`
block in `_base.html` next to the PostHog block. One ID per deployment as decided;
no ID → nothing loads, exactly like PostHog.

## 2. GA4 gtag.js snippet and config options

Google's current recommended snippet is two `<script>` tags: an async loader from
`https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX` and an inline block that
defines `dataLayer`, `gtag()`, and calls `gtag('js', new Date())` then
`gtag('config', 'G-XXXXXXXXXX', {...})`. Unlike PostHog's IIFE-stubbing snippet,
GA4's loader is a real external `<script src>` tag, not an inlined stub — this
matters for CSP (`script-src`, not just `script-src 'unsafe-inline'`) and for the
`interface-swap-fallback.js` / hx-boost head-script concern below.

Config options relevant here:
- **`send_page_view`** (default `true`) — whether `gtag('config', ...)` itself
  fires an initial `page_view` event. Needed as `false` if FLS hand-fires
  `page_view` on HTMX navigations (see §3); otherwise leave default.
- **`debug_mode`** — routes events to GA4 DebugView instead of standard reports.
  Should never be `true` in production; only useful for local manual verification,
  and even then it's arguably unnecessary since no ID is configured in dev at all
  (§4).
- **`cookie_domain`** — defaults to `'auto'`, which is normally correct and
  requires no override. FLS is multi-site (multiple `Site` records potentially on
  different domains), so this default is actually what's wanted: each site's cookie
  stays scoped to that site's own domain rather than a shared apex.
- Nothing else (`cookie_expires`, `anonymize_ip` — already default in GA4, `allow_google_signals`,
  etc.) is needed for a base integration; these are optional tuning knobs, not
  requirements, and should not be added speculatively per the "don't build what
  isn't asked" convention.

**Minimum viable base config:** just the loader script tag plus
`gtag('config', '{{ measurement_id }}')` with no extra options, mirroring how
PostHog's block passes only `api_host` (required) and `ui_host` (optional) and
skips every other PostHog init option.

Sources:
- https://developers.google.com/analytics/devguides/collection/ga4/views
- https://www.analyticsmania.com/post/how-to-install-google-analytics-4-with-google-tag-manager/

## 3. HTMX page views: hx-boost / hx-push-url are used extensively — real double-counting risk

Grep confirms FLS relies on both:
- `freedom_ls/learner_interface/templates/cotton/player-nav.html` — `hx-boost="true"`,
  comment: "hx-boost auto-pushes the URL (so back/forward and bookmarking keep
  working...)".
- `freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html` —
  `hx-push-url="true"` (two places).
- `freedom_ls/base/templates/cotton/breadcrumbs.html` — `hx-get` + `hx-push-url`
  swaps instead of full-page loads.
- `freedom_ls/base/templates/cotton/data-table-cells/link.html` — `hx-push-url="true"`.
- `freedom_ls/educator_interface/templates/educator_interface/partials/organisation_switcher.html`
  — `hx-push-url="true"`.
- `freedom_ls/base/templates/partials/header_bar_user_menu.html` explicitly opts
  *out* with `hx-boost="false"` on the Django admin link — showing the team is
  already deliberate about where boosting applies.
- `_base.html` itself notes "With hx-boost, htmx does not run `<script>` tags in a
  swapped-in `<head>`" — the reason `interface-swap-fallback.js` is loaded globally
  rather than relying on it re-running after a boosted navigation.

**Why this matters for GA4 specifically:** GA4's Enhanced Measurement has a
"Page changes based on browser history events" toggle (on by default for new
GA4 properties/data streams) that makes gtag automatically fire a `page_view`
whenever the browser's History API is used (`pushState`/`replaceState`/
popstate) — which is exactly what `hx-push-url` and boosted `hx-boost`
navigations trigger. Combined with `gtag('config', ...)` also firing a
`page_view` when the base page first loads, and with any htmx-triggered
navigation *not* actually being a full page load (no new `_base.html` render,
so no new `gtag('config', ...)` call either) — the practical failure modes are:

1. **Enhanced Measurement's history-based `page_view` fires on every
   `hx-push-url`/boosted swap "for free"** — since `_base.html` (and hence the
   gtag script tags) is loaded once per full page load, and htmx swaps update
   `document.location` via the History API on subsequent navigations, GA4's
   built-in listener catches those and fires `page_view` correctly *without any
   FLS code change*, as long as the gtag loader stays present in the DOM (which
   it does — `<head>` is not re-executed by htmx, but the already-installed
   `history.pushState` monkey-patch from Enhanced Measurement persists on the
   page regardless of DOM swaps below `<head>`).
2. The risk of **double-counting** only arises if FLS also hand-fires
   `gtag('event', 'page_view', ...)` on `htmx:afterSwap` (the naive way to
   "make sure HTMX page views are tracked") *while* Enhanced Measurement's
   history-based tracking stays on — that produces two `page_view` events per
   htmx navigation.
3. The risk of **under-counting / missed views** would arise the other way:
   if Enhanced Measurement's "Page changes based on browser history" is turned
   off (e.g. copied from a SPA guide that says to disable it before manual
   tracking) but no manual `page_view` firing is added to htmx swaps.

**Recommendation:** Leave GA4's default Enhanced Measurement history-based
page view tracking **on** (it is on by default for a new GA4 data stream) and
do **not** add any custom `htmx:afterSwap` → `gtag('event', 'page_view', ...)`
code in the base integration. This is the zero-code option and matches how
`hx-push-url` already keeps the URL bar and browser history in sync — GA4's
listener needs nothing FLS-specific to key off. The one thing to verify at
implementation time (not a research blocker) is that a *boosted but not
`hx-push-url`'d* fragment swap (there don't appear to be any in this grep —
every `hx-boost`/swap site found also pushes the URL) doesn't silently skip
tracking; since none exist today, this is not a current gap, only a rule to
document for future htmx usage ("if you boost/swap without pushing the URL,
GA4 won't see it as a page view — that may be desired or may need a manual
event, which is out of scope for this base integration").

The "custom event tracking" worker should decide whether any manual
`gtag('event', ...)` calls are wanted at all for HTMX-partial interactions
that are *not* full navigations (e.g. form submissions, modal opens) — that's
a different question from page views and is explicitly out of scope here.

Sources:
- https://developers.google.com/analytics/devguides/collection/ga4/views
- https://developers.google.com/analytics/devguides/collection/ga4/single-page-applications

## 4. CSP domains GA4 needs, and FLS's current CSP posture

Current `SECURE_CSP_REPORT_ONLY` in `config/settings_base.py` (~line 479):

```python
SECURE_CSP_REPORT_ONLY = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:"],
    "connect-src": [CSP.SELF],
    "frame-src": [CSP.SELF, "https://www.youtube.com", "https://www.youtube-nocookie.com"],
}
```

**No precedent exists for PostHog in this CSP** — `connect-src` is `[CSP.SELF]`
only, yet PostHog's snippet loads a script from
`https://<region>-assets.i.posthog.com` and calls out to `POSTHOG_API_HOST`
(`https://us.i.posthog.com` by default), neither of which is in `script-src` or
`connect-src`. This currently "works" only because `SECURE_CSP_REPORT_ONLY` is
report-only (violations are reported, not blocked) — so PostHog is silently
generating CSP violation reports today (if report-uri/report-to is configured) or
simply not policed at all (if it isn't — no `report-uri`/`report-to` directive is
present in the dict shown). Either way, there is no working example in this
codebase of a third-party analytics domain actually added to the CSP dict.

**What GA4 needs**, per Google's own CSP guide for the tag platform:
- `script-src` (or `script-src-elem`): `https://www.googletagmanager.com`
- `img-src`: `https://*.google-analytics.com`, `https://www.googletagmanager.com`
- `connect-src`: `https://*.google-analytics.com`, `https://*.analytics.google.com`,
  `https://www.googletagmanager.com`

The wildcard (`*.google-analytics.com`) is required, not optional, because GA4
sends collection requests to a **region-specific subdomain** (e.g. `region1.google-analytics.com`)
that is assigned dynamically and cannot be pinned to one literal hostname — CSP
does not support wildcards on the right of the hostname (can't do
`google-analytics.*`), but a left-side wildcard subdomain match is standard and
is what Google's own guide uses.

**Recommendation:**
- Add `https://www.googletagmanager.com` to `script-src`.
- Add `https://*.google-analytics.com`, `https://*.analytics.google.com`, and
  `https://www.googletagmanager.com` to `connect-src`.
- Add `https://*.google-analytics.com` and `https://www.googletagmanager.com` to
  `img-src` (belt-and-braces; GA4 can fall back to a `<img>`-pixel transport in
  some environments).
- Given the CSP is currently report-only and PostHog's domains aren't listed
  either, this is not a hard blocker for GA4 to function today, but it should be
  fixed for both services in the same change (or flagged as a pre-existing gap)
  rather than treated as GA4-specific debt. Whether to also formally add PostHog's
  domains is arguably out of this ticket's scope, but the inconsistency is worth
  surfacing to whoever owns tightening `SECURE_CSP_REPORT_ONLY` to enforcing mode
  later — GA4 and PostHog will both need domains listed before enforcement can
  ship without breaking analytics.

Sources:
- https://developers.google.com/tag-platform/security/guides/csp
- https://content-security-policy.com/examples/google-analytics/

## 5. Dev/test/staff exclusion

Common practice, and what the "no ID → not loaded" decision already buys FLS:
- **No measurement ID configured in dev/test** is the simplest and already-decided
  mechanism — identical to how PostHog and Sentry behave in this codebase (`docs/product/deployment.md`:
  "a complete no-op until one is set, so development and unconfigured deployments
  send nothing"). No extra dev-specific code path is needed; this is a deployment/
  environment-variable concern, not an application one.
- **`debug_mode`** is a *manual verification* tool (routes events into DebugView),
  not an exclusion mechanism — it does not stop events from otherwise counting
  unless a GA4 "Developer traffic" data filter is also configured *in the GA4
  property itself* to drop `debug_mode=1` events. That's GA4-property
  configuration, not FLS code, and is out of scope for a code-level integration.
- **Internal traffic filters** (excluding staff/employees by IP, in GA4's Admin →
  Data Settings → Data Filters) are also GA4-property configuration, not
  something FLS's codebase can implement — FLS has no way to know an operator's
  office IP range. This is worth a one-line mention in `docs/product/deployment.md`
  (the operator should set this up in the GA4 property) but not application code.
- **Excluding staff/logged-in-as-staff users at the template level** (e.g. don't
  render the gtag snippet for `request.user.is_staff`) is a *possible* extra, but
  it isn't how PostHog does it today (PostHog renders for everyone once a key is
  configured, staff included) and wasn't asked for. Recommend **not** adding this
  to stay consistent with the existing PostHog precedent and the "don't build
  what's not explicitly requested" convention — an operator who wants staff
  excluded from GA4 reporting has the GA4-side internal-traffic filter for that,
  same as they would for PostHog (which has an equivalent "internal and test
  accounts" filter).

**Recommendation:** rely entirely on "no ID set → not loaded" for dev/test (already
decided), document the GA4-side internal-traffic-filter and developer-traffic-filter
options in deployment docs as operator responsibilities, and add no staff-exclusion
code.

Sources:
- https://www.analyticsmania.com/post/how-to-exclude-internal-traffic-in-google-analytics-4/
- https://measureschool.com/exclude-internal-traffic-in-ga4/

## 6. Coexistence with PostHog

No technical conflict running both simultaneously — this is an extremely common
pairing (GA4 for marketing/traffic reporting, PostHog for product analytics/session
replay/feature flags) and neither library patches or interferes with the other's
globals (`window.gtag`/`window.dataLayer` vs `window.posthog`). Two points worth
noting rather than acting on:
- Both set first-party cookies; a strict cookie-consent regime would need to gate
  both snippets identically, but FLS has no existing consent-gating mechanism for
  PostHog today, so adding one for GA4 alone would be new scope, not parity with
  the existing pattern. Not recommended unless separately requested.
- Load order in `_base.html` doesn't matter functionally since they don't interact,
  but for consistency it makes sense to place the GA4 block next to (immediately
  before or after) the existing `{% if posthog_api_key %}` block rather than
  scattering it elsewhere in `<head>`.

## 7. Measurement Protocol (server-side) — brief

Needed when an event happens **without a live browser context to fire gtag from**
— e.g. a webhook callback, a background task (`fls_run_worker`), a POST-then-redirect
flow where the conversion actually completes server-side after the page has
navigated away, or any event a Django management command triggers. FLS already has
exactly this kind of infrastructure (Django's task framework, webhook delivery) so
it's a realistic future need, just not this ticket's.

Requirements if/when it's built:
- A **Measurement Protocol API secret**, created per GA4 data stream (distinct
  from the public measurement ID — this one must stay server-side only, never
  exposed to a template, and should live in the same `DeploymentSettings` /
  env-var pattern as `POSTHOG_API_KEY`/`SENTRY_DSN`).
- A **`client_id`** for every request sent to `https://www.google-analytics.com/mp/collect`
  — GA4 uses it to stitch server events into the same user/session as their
  client-side activity. For a logged-in-user server event, the correct approach
  is to read the `client_id` GA4 already set in that user's `_ga` cookie (if the
  request has one) rather than mint an unrelated ID — a random or static
  per-server client_id groups unrelated users together in GA4's reporting and
  breaks attribution.
- Server events sent this way do **not** go through gtag/Enhanced Measurement at
  all, so none of the CSP or htmx page-view discussion above applies to them.

**Recommendation for this base-integration ticket:** do not build any Measurement
Protocol scaffolding now. The base integration (measurement ID setting, gtag
snippet, CSP entries) needs no changes to accommodate it later — when it's needed,
it's an additive server-side setting (API secret) and a small client, not a
rework of the client-side pieces this ticket covers. Leave it to the events worker
/ a future ticket to decide if any FLS event actually requires server-side
delivery.

Sources:
- https://optimizesmart.com/blog/ga4-google-analytics-4-measurement-protocol-tutorial/
- https://www.w3tutorials.net/blog/what-should-the-client-id-be-when-sending-events-to-google-analytics-4-using-the-measurement-protocol/

## 8. Reference implementations: is a dependency worth it?

- **`django-analytical`** (jazzband) has a `google_analytics_gtag` module
  (`GOOGLE_ANALYTICS_GTAG_PROPERTY_ID` setting, `{% analytical_head_top %}` /
  `{% analytical_body_bottom %}` template tags). It's a real, maintained option,
  but it brings its own settings-naming convention, template-tag-based rendering
  model, and a whole multi-service abstraction (it also wraps Mixpanel, Google
  Tag Manager, HubSpot, etc.) that doesn't match how FLS already renders PostHog
  — a raw `{% if %}` block reading FLS's own `DeploymentSettings`, no third-party
  template tags.
- **`google-analytics-django` / `google_analytics_django`** (smaller, less
  established PyPI packages) exist but are thin wrappers around the same
  gtag.js snippet with far less adoption/maintenance signal than
  `django-analytical`, and still don't match FLS's settings/context-processor
  shape.
- The actual gtag.js integration is **two `<script>` tags and one settings
  value** — there is no meaningful parsing, API-calling, or protocol logic on
  the client-side base-integration path that a dependency would meaningfully
  encapsulate (unlike, say, WeasyPrint or `django-fernet-encrypted-fields`,
  which wrap real complexity). PostHog's own snippet in `_base.html` is inlined
  directly rather than pulled from a `django-analytical`-style package, despite
  `django-analytical` also having a PostHog-adjacent story — this is already the
  established precedent in this codebase.

**Recommendation: no new dependency.** Follow the PostHog precedent exactly —
a template snippet in `_base.html`, a setting in `DeploymentSettings`, and a
context processor. This keeps GA4 consistent with every other third-party
integration in this project and avoids taking on a dependency (`django-analytical`)
whose abstraction (multi-service, template-tag-driven) doesn't fit how FLS
already does this.

Sources:
- https://github.com/jazzband/django-analytical/issues/183
- https://django-analytical.readthedocs.io/en/stable/services/google_analytics_gtag.html
- https://pypi.org/project/google-analytics-django/0.1.0

## 9. Setting name recommendation

`freedom_ls/base/app_settings.py`'s pattern (see `COURSE_ACCESS_BACKEND` in the
app-settings skill, and `POSTHOG_API_KEY`/`SENTRY_DSN` in `DeploymentSettings`)
uses the **service's own name spelled out**, not an internal abbreviation:
`POSTHOG_API_KEY`, `POSTHOG_API_HOST`, `SENTRY_DSN`. There is no precedent in this
codebase for abbreviating a vendor name (no `PH_API_KEY`, no `GA_...` shorthand
anywhere).

Google's own docs and support material consistently call this value the
"Measurement ID" (format `G-XXXXXXXXXX`), distinct from the older Universal
Analytics "Tracking ID" (`UA-...`) — using the word "Measurement" also
future-proofs the name against confusion if a Measurement Protocol API secret is
ever added alongside it later (§7), since that second value would naturally be
named `GOOGLE_ANALYTICS_API_SECRET` or similar, sitting clearly next to it.

**Recommendation: `GOOGLE_ANALYTICS_MEASUREMENT_ID`** (not `GA_MEASUREMENT_ID` or
`GOOGLE_ANALYTICS_ID`) — spelled out like `POSTHOG_API_KEY`/`SENTRY_DSN`, and named
after GA4's own terminology for the value rather than an internal abbreviation.

---

status: ok
