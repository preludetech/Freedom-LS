# Research: different versions of a landing page

`idea.md` defers A/B variants and says to leave the referral idea's `v` parameter reserved and
build nothing. This looks at what "different versions of a landing page" could actually mean, what
FLS has today, what the evidence says about testing at a first deployment's traffic, and what I
would build.

Short answer: three of the four meanings need no new machinery at all, and the fourth is not worth
building yet. The recommendation in `idea.md` holds, but for a sharper reason than "it is new
machinery". The reason is that the split belongs in the advertising platform, not in FLS.

---

## 1. Four things "different versions" can mean

These get conflated constantly, and they have completely different costs.

| Meaning | What it is | New FLS machinery |
|---------|-----------|-------------------|
| Different promises | Three adverts, three audiences, three pages, three URLs | None. This is already the design. |
| Platform-split test | Two URLs for one promise; Google Ads or Meta splits the traffic and reports conversions per arm | None |
| App-split test | One URL; the server picks a version per visitor and holds it steady | Registry, assignment, stickiness, `Vary`, measurement |
| Sequential versions | Change the page, compare the period before against the period after | None |

`idea.md` already covers the first: one page per distinct promise, not one per campaign. A campaign
running three adverts at three audiences needs three headlines, and that is three pages, not one
page with three variants. Most of what people want when they ask for variants is this, and it is
already the plan.

The interesting question is only about the middle two.

---

## 2. What FLS has today

Verified against the code, not assumed.

**No full-page caching.** Production sets `CACHES` to `fls_defaults.DATABASE_CACHES`
(`config/settings_prod.py:85`), a DB-backed cache, but nothing uses it for page output. There is no
`CacheMiddleware` in `MIDDLEWARE` (`config/settings_base.py:147-163`) and no `cache_page` anywhere
in the tree. Production sits behind a cloudflared tunnel, which the trusted-IP header default
records (`TRUSTED_CLIENT_IP_HEADER = "CF-Connecting-IP"`,
`freedom_ls/deployment/settings_defaults.py:51`), and Cloudflare does not cache HTML by default.

So the cache-key problem that `research_attribution_and_measurement.md` §3 raises is not live. It
is one "Cache Everything" rule away from being live, which is worth writing down somewhere, but
today nothing has to vary a cache key.

**PostHog is client-side only.** `freedom_ls/deployment/context_processors.py` hands the browser
`posthog_api_key`, `posthog_api_host` and `posthog_ui_host`, and `_base.html` inlines the JS
snippet. There is no `posthog` Python package in the dependency tree. PostHog feature flags and
experiments are therefore available today only in the browser, after the page has painted.
Server-side evaluation would mean a new dependency and a new outbound call in the request path.

**Sessions are database-backed.** No `SESSION_ENGINE` override exists, so the default
`django.contrib.sessions.backends.db` applies. Django only creates a session row and sets the
cookie when something writes to `request.session`, so today an anonymous visitor browsing the
catalogue costs no row. Storing a variant assignment in the session would change that: one
`django_session` insert per cold advert click, on the exact traffic that is spikiest and least
likely to convert. A signed cookie avoids the write entirely.

**The canonical link now exists.** `{% block canonical_link %}` inside `head_seo` in `_base.html`
emits `<link rel="canonical">` at the current path with the query string stripped. That is exactly
the primitive Google's testing guidance asks for, and it already works, which removes one of the
costs `idea.md` counted against variants.

**`v` is capture only.** The referral-tracking idea
(`spec_dd/2. in progress/referal_tracking/idea.md`) captures `v` from the query string, accepts
only `a` or `b`, and stores it in the `fc_attr` cookie and session. It records a decision. It does
not make one, and nothing in FLS makes one.

**Nothing rate-limits an anonymous GET.** `axes` guards authentication views only
(`config/settings_base.py:318-341`). Relevant because every variant scheme has to survive crawler
and scraper traffic that never converts.

---

## 3. What the evidence says

### Google is explicit, and the advice is cheap to follow

[Search Central: A/B Testing Best Practices](https://developers.google.com/search/docs/crawling-indexing/website-testing):

- "Don't show one set of URLs to Googlebot, and a different set to humans. This is called cloaking,
  and is against our spam policies."
- "Use the `rel="canonical"` link attribute on all of your alternate URLs to indicate that the
  original URL is the preferred version."
- "Use a 302 (temporary) redirect, not a 301 (permanent) redirect."
- "Once you've concluded the test, update your site with the desired content variation(s) and
  remove all elements of the test as soon as possible."

One correction to `research_attribution_and_measurement.md` §3, which reads `noindex` and canonical
as interchangeable here. Google prefers canonical and says so: "We recommend using
`rel="canonical"` rather than a noindex meta tag because it more closely matches your intent in
this situation." For a two-URL test the variant URL should carry a canonical pointing at the
original, not a `noindex`. `noindex` stays the right tool for a page that should never rank at all,
which is a different case.

The no-cloaking rule has a practical consequence people miss: Googlebot has to be assignable to a
variant like any other visitor. A scheme that detects the crawler and always serves arm A is
cloaking.

### The sample size numbers are unforgiving

The commonly cited rule of thumb for a reliable test is on the order of
[30,000 visitors and 3,000 conversions per variant](https://fibr.ai/ab-testing/ab-testing-sample-size),
and the three inputs that set the real number are baseline conversion rate, minimum detectable
effect and statistical power. A low baseline rate needs a bigger sample. A small effect needs a
bigger sample. Standard power is 80%.

Treat the 30,000 figure as a directional benchmark rather than a hard threshold, because the real
number depends entirely on those three inputs. The direction is what matters here. A landing page
converting in the low single digits, at a first deployment's traffic, can detect a headline
rewrite that moves conversion by half, and cannot detect one that moves it by a tenth. Most real
copy changes are in the second category.

[CXL](https://cxl.com/blog/ab-testing-alternatives/) and
[Convert](https://www.convert.com/blog/a-b-testing/how-to-successfully-optimize-when-you-cant-ab-test/)
both land on the same answer for low traffic: sequential testing where you mainly want to avoid
going backwards, and qualitative methods (user recordings, five-second tests, preference tests,
copy testing panels) for everything else. Both flag the history effect as the weakness of
sequential testing. A period-over-period comparison confounds the change you made with everything
else that changed, including the campaign, the season and the ad spend.

The honest reading: at this traffic, a formal test is a way of producing the appearance of rigour
without the substance. A test that never reaches its stopping rule, stopped when someone likes the
number, is worse than no test.

### The ad platforms already do this

[Google Ads help](https://support.google.com/google-ads/answer/6328603) supports landing page tests
directly through campaign experiments, and the practitioner guidance is that
[custom experiments, not ad variations, are the right tool](https://www.blobr.io/how-to-guides/how-to-a-b-test-landing-pages-in-google-ads-a-step-by-step-guide)
when what you are testing is the page. Either two distinct URLs or one URL with a variant
parameter works, as long as each arm reliably gets a distinct experience and the conversion
tracking survives the split.

One trap worth naming in the spec: Performance Max campaigns with final URL expansion enabled will
send traffic to other pages on the domain, which silently destroys a landing page test. Whoever
runs the campaign has to turn that off for the test.

This matters more than it first appears. The platform is already splitting traffic, already
holding the assignment, already deduplicating, already counting conversions per arm, and already
excluding most invalid traffic. Rebuilding a worse version of that inside FLS buys nothing.

---

## 4. If you did build app-side variants, what it would take

Setting aside whether to, here is the actual shape, so the cost is concrete rather than vague.

### The shape I would build

A page's registry entry grows an optional variant map:

```python
LandingPage(
    slug="python-evenings",
    variants={"a": "landing/python_evenings_a.html", "b": "landing/python_evenings_b.html"},
    noindex=False,
)
```

The dispatch view resolves the variant in this order: an explicit `?v=` from the query string, then
an existing assignment cookie, then a fresh assignment. It renders the matching template and sets
the cookie if it was not already set.

Six things have to be right:

**Assignment.** A signed cookie, not a session write, for the reason in §2. Django's
`signing.get_cookie_signer` and `set_signed_cookie` already exist. Assign by hashing a random value
per visitor rather than by hashing the IP, because a shared mobile network or a corporate NAT would
put a whole cohort in one arm.

**Stickiness.** The same visitor must see the same version on reload and on return, or the
conversion gets attributed to whichever arm happened to be live at signup rather than the one that
actually persuaded them. `research_attribution_and_measurement.md` §2 already establishes that the
attribution row is written in the signup submission view, so the assignment has to survive from the
first page view to that POST. A 90-day cookie alongside `fc_attr` does it. A session does not,
because the session dies before a returning visitor comes back.

**`Vary: Cookie`.** Without it, any cache that ever gets put in front of this serves one arm to
everybody. Nothing caches HTML today, so this is a guard against a future Cloudflare rule rather
than a present bug, but it costs one decorator and the failure mode is silent.

**Canonical.** Already correct. Both templates extend `_base.html` and the canonical link resolves
to the same bare URL, because both arms live at one path and the query string is stripped. This is
the shape Google asks for, and it comes free.

**Crawler handling.** Googlebot gets assigned like anyone else, per the no-cloaking rule. It will
never convert, so its page views inflate the denominator of one arm. At low traffic that skew is
not negligible, and the fix is to measure conversions per arm rather than conversion rate per arm,
or to exclude known crawlers from the denominator only in reporting, never in assignment.

**Measurement.** `v` gets recorded on the attribution row, which the referral-tracking work already
provides for. Without that row nothing can join a conversion back to an arm, so app-side variants
depend on referral tracking shipping first. That dependency is the real sequencing constraint.

### What I would not build

**Client-side swapping via PostHog feature flags.** PostHog is already in the page, so this looks
like the free option. It is not, for this traffic.

The flag resolves after the JS loads and evaluates, so the visitor sees arm A and then watches it
become arm B. PostHog's own docs call this out and recommend
[bootstrapping flags from the server](https://posthog.com/docs/feature-flags/bootstrapping) to
avoid it, which means adding the Python SDK and doing server-side evaluation, which is the thing
that was supposed to be avoided. It also makes the page's primary content depend on JavaScript,
which directly contradicts the rule already in `idea.md`: every CTA is server-rendered, HTMX is
enhancement, never the only path. A page whose whole audience arrives cold from an advert cannot
afford a JS-dependent hero.

**Redirect-based variants.** Sending `/python-evenings/` to `/python-evenings-b/` with a 302 works
and is what Google's guidance covers, but it adds a round trip on exactly the mobile connections
`research_landing_page_conversion_ux.md` identifies as the best-evidenced conversion variable.
Same-URL rendering avoids it entirely.

---

## 5. Recommendation

**Do not build variant machinery. Split at the advertising platform.**

For one promise you want to test two ways, write two pages at two URLs, point two ad arms at them,
and read the result in the platform's own conversion reporting. Give the losing URL a canonical
pointing at the winner, or retire it. This works today, on the code that just shipped, with no FLS
change at all.

It is better than an app-side split on every axis that matters here. The platform holds the
assignment and holds it correctly. It counts conversions per arm without needing an attribution
row, so it does not block on referral tracking. It filters invalid traffic. And it keeps FLS out of
a feature whose correct implementation depends on traffic volumes the first deployment does not
have.

**Keep `v` reserved and keep it capture-only.** Recording which version a visitor declared costs
nothing and stays useful under every scheme above, including the platform-split one, where the ad
can append `?v=b` to its own URL. Deciding a version is the part not worth building.

**Say the sample-size constraint out loud in the spec.** Not as a caveat but as a decision rule:
before running any test, state the baseline rate, the minimum effect worth acting on, and the
number of conversions per arm that implies. If the campaign cannot deliver that number in the time
it runs, do not run a test. Rewrite the page on judgement and evidence from qualitative work
instead, which is what the low-traffic literature recommends anyway.

**Revisit when one of two things changes.** Either a single landing page is reliably clearing a few
hundred conversions per arm in a campaign's lifetime, or a second deployment appears that wants the
same machinery. Until then, app-side variants are a feature with a real cost and no reachable
payoff.

If you decide to build them anyway, build the shape in §4, and build it after referral tracking,
because without the attribution row the test cannot be read.

---

## 6. Suggested changes to `idea.md`

The existing "A/B variants" paragraph under "Deliberately not in the first release" is right but
underspecified. Three things to fold in:

1. Name the platform split as the supported answer, so "not in the first release" does not read as
   "you cannot test anything". You can, today, with more pages.
2. Correct the canonical-versus-`noindex` point. A variant URL takes a canonical to the original.
   `noindex` is for a page that should never rank.
3. Record the dependency: app-side variants cannot be measured until referral tracking writes the
   attribution row, so they sequence after it, not alongside it.

Also worth a line under "A note on the word". Neither "variant" nor "version" appears in the domain
glossary, so both are free, but a spec that uses them interchangeably will confuse the four
meanings in §1. Pick "variant" for the app-side split and "version" for nothing, or say which
sense is meant.

---

## Sources

- [Google Search Central: A/B Testing Best Practices](https://developers.google.com/search/docs/crawling-indexing/website-testing)
- [Google Ads Help: Test your landing page](https://support.google.com/google-ads/answer/6328603)
- [How to A/B Test Landing Pages in Google Ads](https://www.blobr.io/how-to-guides/how-to-a-b-test-landing-pages-in-google-ads-a-step-by-step-guide)
- [A/B Testing Sample Size: A Definitive Guide](https://fibr.ai/ab-testing/ab-testing-sample-size)
- [CXL: A/B Testing Alternatives for Low-Traffic Websites](https://cxl.com/blog/ab-testing-alternatives/)
- [Convert: How to successfully optimize when you can't A/B test](https://www.convert.com/blog/a-b-testing/how-to-successfully-optimize-when-you-cant-ab-test/)
- [PostHog: Bootstrapping feature flags](https://posthog.com/docs/feature-flags/bootstrapping)
- [PostHog: Python library](https://posthog.com/docs/libraries/python)
