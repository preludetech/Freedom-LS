# Landing pages

Public marketing pages that turn advert and referral traffic into learners. One page per promise,
meaning a specific advert, audience or course, with a headline that continues whatever the link the
visitor followed said, and a single primary action.

They are developer-authored. A template committed to a repo, changed by a commit and a deploy.
There is no page model, no admin editing, no CMS.

They live in the concrete implementation. FLS ships the shared parts.

## Why not send that traffic to the home page or the catalogue

The home page, catalogue and course detail pages are already public and already SEO-wired
(`spec_dd/3. done/2026-07-01_19:44_home_page/`). They exist to let a visitor browse everything on
offer and work out what suits them. An advert has already done that work. It made one promise to one
audience, and a page that answers a broader question loses the visitor who arrived with a narrow
one. Dedicated pages measurably outperform generic ones for paid and referral traffic, and the
mechanism is message match rather than the page merely being a landing page.

That also fixes the granularity. One page per **distinct promise**, not one per campaign. A campaign
running three adverts at three audiences needs three headlines, not one page hedging across all of
them.

## The seam

FLS owns anything with a sensible default. The concrete project owns anything inherently
per-campaign. That is the line FLS already draws for course access, where `CourseAccessBackend`
ships the machinery and a real default policy while the catalogue's contents belong to the
deployment, and for theming, where FLS ships one real default theme and the brand belongs to the
deployment.

A `freedom_ls/landing_pages/` app would be the only extension point in FLS with no possible working
default. There is no copy FLS could ship that is right for an unknown campaign, and the
developer-authored decision rules out falling back on an admin-editable stub. The app would ship
inert until a downstream project wrote every byte of its output, which is a different thing from
working out of the box.

### What FLS adds

**Head metadata blocks in `_base.html`.** FLS emits `head_title` and `meta_description` and nothing
else. A landing page needs three more, each a block with a default derived from the existing title
and description so no current page changes behaviour.

A canonical URL, because the same page behind a dozen `utm_*` query strings must canonicalise to the
bare URL rather than fragmenting into one indexed variant per advert. Open Graph and Twitter card
tags, because these pages get link-shared into ad units and messaging apps in a way course pages
never are, and today they would share with no title, description or image. And a `noindex` switch,
for a page that should stay reachable by direct link without being ranked. A paid-advert page whose
copy assumes the visitor already saw the advert reads badly as an organic search result.

**Landing-page section components.** Hero, feature grid, testimonial, FAQ and CTA band. None exist.
`<c-page>`, `<c-button>`, `<c-callout>`, `<c-chip>` and `<c-media-card>` already cover the small
pieces. The sections are what a page is actually assembled from, and building them once is what
makes the twelfth page cheap. `<c-accordion>` and `<c-pull-quote>` look like matches but are
markdown-authoring components tied to `content_engine`'s sanitiser allowlist and a
`content_instance`, so they cannot be dropped into a plain template.

**A how-to,** sibling to `docs/how tos/theme-fls.md`, covering the seam. Extend `_base.html`, set the
metadata blocks, point CTAs at the backend-resolved `cta_url` rather than hand-building `?next=`,
register pages in your own `config/sitemaps.py`, and add the app's template directory to the
project's `tailwind.input.css` `@source` globs. A directory outside `freedom_ls/` is not scanned, and
every utility class on an unscanned page silently compiles to nothing.

### What the concrete project owns

Its own Django app: routing, every template, every word of copy, the per-page metadata values, and
the sitemap entries. Nothing depends back on it, so it sits at the composition layer alongside
`config/`.

Pages should be driven by a registry keyed on slug behind one dispatch view, not a `path()` and a
view function per page. That is what makes page twelve one registry entry plus one template, and it
is the one place that can answer which pages exist, for the sitemap, for site-scoping and for tests.
Resolving a URL slug straight onto a template path is the wrong shape. Beyond traversal safety it
would serve any file that happens to sit in the directory, and it leaves nowhere to put per-page
metadata that the slug does not imply.

A page's sitemap membership and its `noindex` setting are the same decision and belong on the same
registry entry, so the two can never disagree.

Each page also carries an optional site filter on its registry entry, resolved through
`get_cached_site(request)`. That is the shape `settings.site_conf` already uses for per-site
configuration that is not a database row, and it keeps a page scoped to one tenant out of another
tenant's sitemap by construction. Because each `Site` is its own domain, nothing leaks across
tenants.

## What a landing page asks for

Three actions, all of which already work end to end:

- **Sign up for the platform**, through allauth signup.
- **Apply to a course**, through `course_applications` and its backend-resolved CTA.
- **Register interest in a coming-soon course**, through `course_interest`.

All three require an account, and all three are already solved for an anonymous visitor by the
deferred-login flow. Link at the `@login_required` view and let Django build `?next=`, or use
`redirect_to_auth` for an HTMX-triggered action. Landing pages reuse this as-is. They must not
smuggle campaign data through `next`, which would conflate the redirect target with the traffic
source and widen the open-redirect risk `next` is deliberately kept narrow to avoid.

**A CTA has to say what is behind it.** Signup runs under
`ACCOUNT_EMAIL_VERIFICATION = "mandatory"`, so "sign up" actually means "we email you a link to
finish", and applying means filling in a form after logging in. A page that does not name the next
step breaks its own promise one screen later, which is the same failure as an advert that does not
match its landing page.

Every CTA is a server-rendered link or form. HTMX is enhancement here, never the only path. A page
whose whole audience arrives cold from an advert or a crawler cannot afford a JavaScript-only route
to its one action.

**The page's chrome competes with its CTA.** `partials/header_bar.html` offers an anonymous visitor
Login and Sign Up, which is right for the catalogue and wrong for a page whose one action is already
on the screen. Landing pages should render a stripped header rather than dropping it entirely.
Applying to a course is a bigger commitment than a trial signup, and a visitor arriving cold who
cannot confirm the organisation is real will leave and search instead of clicking. `_base.html`
already exposes a `header` block, so this is the concrete project's choice per page and needs
nothing new from FLS.

## Copy and page quality

Conversion practice and the FLS brand voice mostly agree, which is convenient. Both rule out vague
superlatives, unattributed testimonials and manufactured scarcity. The last is not a matter of
taste. Fake countdowns and stale "3 spots left" banners are documented deceptive practice with
regulatory consequences. Real, dated urgency, "applications close 20 October", is both good brand
voice and defensible.

The one real tension is volume. Conversion practice wants the CTA repeated at each persuasive pause
point, and FLS's voice wants evidence before claims. Repeat the same CTA with the same words, and
keep the surrounding prose factual rather than escalating in enthusiasm at each repetition.

Testimonials need to clear a higher bar than usual. Visitors read on-page quotes as unverifiable by
default, assuming a site publishes only the flattering ones, so attribution and something checkable
matter more than the quote itself.

Two things carry real weight here rather than being polish. Page weight is the first. The traffic is
mobile and often on a poor connection, and load time is the best-evidenced conversion variable in
the whole research set. The content image pipeline covers `content_engine.File` rows only, so a hero
image committed as a static asset gets no re-encoding and has to arrive in the repo already
optimised. Form and heading accessibility is the second. A visitor who cannot tell which field
failed validation abandons, regardless of ability.

## Deliberately not in the first release

**Contact capture with no account.** A visitor leaving contact details without signing up is a real
fourth CTA and it should be built, but not yet and not as part of this. It is the only one of the
four with no existing consent machinery in FLS. `CourseInterest` requires a `User` and its
`(site, user, course)` uniqueness cannot represent an anonymous row, and `LegalConsent` requires a
`User` FK, so a lead's consent evidence has nowhere to live. POPIA's direct-marketing rules are
current law with an active regulator for the first deployment, and the consent copy and retention
policy need a real legal review rather than a placeholder. It also needs abuse handling FLS has no
precedent for, since nothing currently rate-limits an anonymous form POST outside allauth's own
views, and it must not become an oracle for whether an email is already registered, which
`ACCOUNT_PREVENT_ENUMERATION` exists to prevent. `research_lead_capture.md` has the data shape, the
legal grounding and the minimal version, ready for its own spec.

**App-side A/B variants.** The referral-tracking idea reserves a `v` parameter, but capturing which
variant a request declares is the small half of the problem. Choosing a variant, rendering it,
keeping the assignment sticky from the first page view through to the signup POST, and keeping the
cache key honest are all new machinery, and at the traffic volumes of a first deployment a test
would not reach a trustworthy sample size. Leave `v` reserved and build nothing.

Not testing anything is a different decision, and not this one. Two pages at two URLs, with the
advertising platform splitting the traffic and reporting conversions per arm, tests the same
question and needs no FLS code. Google Ads runs this as a campaign experiment. The platform already
holds the assignment, counts conversions per arm and filters invalid traffic, so an app-side split
would be rebuilding a worse version of it. Turn off Performance Max final URL expansion first, or
the campaign sends traffic to other pages and there is no test left.

Two corrections to carry forward. A variant URL takes a `rel="canonical"` pointing at the original,
not a `noindex`; Google's testing guidance prefers the canonical because it matches the intent, and
`noindex` stays the tool for a page that should never rank at all. And app-side variants sequence
*after* referral tracking rather than alongside it, because without the attribution row nothing can
join a conversion back to an arm. `research_page_variants.md` has the four things "different
versions" can mean, the sample-size arithmetic, and the shape to build if the traffic ever
justifies it.

**Attribution.** Landing pages ship unattributed. Nothing in the referral-tracking idea exists yet,
no middleware, no cookie, no attribution model, and landing pages work without it. They simply
cannot yet report where their traffic came from. Building a second attribution mechanism here would
be worse than waiting.

Three findings from `research_attribution_and_measurement.md` are worth carrying into that spec
rather than rediscovering.

The attribution row must be written in the signup-submission view, not on confirmation-click. A
confirmation link opened on another device has neither the cookie nor the session, and no
server-side value can follow an email link into a browser that never made the original request.

A landing page should be able to declare its own campaign identity server-side, so a bare partner
link with no query string is still attributable. It fills the gap when UTMs are absent and never
overwrites a UTM that is present. `landing_path` names the page, UTMs name the campaign, and neither
substitutes for the other.

Any full-page caching in front of a landing page must not short-circuit the request before Django
sees it, or nothing is captured at all. That is a landing-pages problem, not one the middleware can
solve.

## A note on the word

"Landing page" already appears in FLS for a `Form`'s pre-start view and for the pages the signup
flow lands on. Those are test names and comments rather than models or routes, so nothing collides
at the identifier level and we keep the word for these pages too. It is the term the people doing
this work actually use. Anything ambiguous in a spec or a template path should say which sense it
means.

"Variant" and "version" are both free, neither appears in the domain glossary, and they get used
interchangeably for at least four different things: a page per promise, a platform-split test arm,
an app-split test arm, and the same page rewritten over time. Reserve "variant" for a test arm and
say which kind. Nothing else in the spec should use it.

## Companion research

- `research_code_home_fls_vs_concrete.md`. The app-boundary question against the dependency graph,
  the downstream test suite and the upgrade-note cost of a new FLS app.
- `research_dev_authored_page_mechanics.md`. Routing, per-page metadata, the component gap,
  multi-site scoping, and why the markdown pipeline is the wrong tool for a page body.
- `research_landing_page_conversion_ux.md`. What converts and what fails, with evidence quality
  marked claim by claim, plus the brand-voice tension.
- `research_lead_capture.md`. The deferred contact-capture CTA: data shape, POPIA and GDPR consent,
  abuse handling, and why `CourseInterest` cannot represent an anonymous row.
- `research_attribution_and_measurement.md`. The seam with referral tracking, the email-verification
  hop, and the gap where a lead has no learner to key attribution on.
- `research_page_variants.md`. The four meanings of "different versions", why the split belongs in
  the advertising platform, the sample-size arithmetic at a first deployment's traffic, and the
  shape an app-side split would take if it ever earns its place.
