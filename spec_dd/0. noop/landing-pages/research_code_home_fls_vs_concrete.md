# Research: where landing-page code should live — FLS vs. concrete project

## Terminology collision (resolve before naming anything)

"Landing page" already has two unrelated, established meanings in this codebase, neither of them
the marketing page from the idea:

1. **The pre-start view of a `Form`.** `learner_interface/tests/playwright/form_ui_tests.py` calls
   this "a form landing page" throughout (`navigate_to_form`, `test_view_form_landing_page`,
   `test_completed_quiz_shows_scores_on_landing_page`) — the screen a learner sees before starting
   a quiz/form, showing its title, instructions and (if retaken) prior score.
2. **Generic "the page a flow lands you on."** `accounts/tests/test_signup_messages.py` calls the
   post-signup and post-email-confirmation pages "landing pages" in prose. `panel_framework/views.py:585`
   uses "root landing page" in a comment for the panel-framework breadcrumb root — again just English,
   not a noun for a model or route.

None of these are marketing pages, but all three uses are load-bearing test names and docstrings —
they will not be renamed for this feature. **Coin a distinct noun for the new concept.** The idea
itself already supplies one: it describes these as used "per-campaign (one page per advert /
audience / course)." **Campaign page** is recommended: it says what FLS doesn't have a word for yet
(a public, developer-authored, single-purpose conversion page tied to one advert/audience/course),
and it doesn't collide with "landing page" as already used for forms or as loose English. Use
"landing page" freely in product/marketing prose (it's the industry-standard term and the idea uses
it that way throughout) but reserve "campaign page" for code identifiers, template paths, URL names,
and app/module names, so a search for "landing" in the codebase keeps meaning what it already means.

This is a **new word being coined here** — it is not established elsewhere in the codebase or in
`.claude/skills/domain-glossary/SKILL.md` — and is proposed, not settled.

## What FLS actually has today, that a campaign page would reuse

### The four conversion actions map onto four different levels of existing machinery

The idea names four target actions. Each already exists in FLS to a different degree:

| Action | Existing FLS entry point | State |
|---|---|---|
| Platform signup | allauth `account_signup`, threaded via `?next=` | Fully built (`spec_dd/3. done/2026-07-01_19:44_home_page/1. spec.md` §4) |
| Course application | `course_applications:apply` (`freedom_ls/course_applications/urls.py:8`) | Fully built, `@login_required`, backend-resolved CTA (`course_access/backends.py:212-223`, gated variant in `course_applications`) |
| Register interest (coming-soon course) | `course_interest:express_interest` / `deferred_express_interest` (`freedom_ls/course_interest/urls.py`, `views.py:27-118`) | Fully built, but **requires an account** — `CourseInterest.user` is a mandatory FK (`freedom_ls/course_interest/models.py:28-32`); an anonymous click is deferred through login/signup exactly like the other two (`redirect_to_auth`, `views.py:44-50`) |
| Contact-detail capture, **no account created** | — | **Does not exist.** No `Lead`/`ContactRequest`/enquiry model anywhere in `freedom_ls/` (verified: no model, form, or view matches this shape in the whole tree) |

This matters for the "where does the code live" question: three of the four actions are pure
*consumption* of existing FLS URLs/views — a campaign page just needs a CTA `<a href>` or form
`action` pointed at an existing, already-portable, already-tested route. The fourth is **new
machinery that has to be built somewhere**, and it is the one action that is genuinely
account-less — it cannot piggyback on `CourseInterest` (which insists on a `user`) or on the
allauth signup flow. Whichever option is chosen, this fourth action forces at least one new model
and one new (unauthenticated, spam-exposed) view into existence. That single piece of new machinery
is the one part of "landing pages" that cannot be answered with "ship nothing, just document the
seam" — see the Middle option below.

### Attribution/referral capture is already a separate, adjacent, in-flight idea

`spec_dd/2. in progress/referal_tracking/idea.md` describes exactly the "which advert/referrer did
this visitor arrive from" capture a campaign page needs: a `?ref=`/UTM-capturing middleware, a
first-party cookie, and — on signup — a one-time attribution row keyed to the learner. It is not yet
spec'd (only `idea.md` and a stock `todo.md` exist in that directory). `docs/app_conventions.md:33-34`
already names its likely destination as an **extractable app**, `referral-link-tracker`, alongside
`icons` and `markdown_rendering` — i.e. FLS-side, plain `django.db.models.Model` (no
`SiteAwareModel`), no app-label prefix, so it can later leave `freedom_ls/` as its own package.
Landing-page work should **consume** whatever that spec lands (the cookie/session values it
captures) rather than invent a second attribution mechanism; the two ideas are sequenced, not
independent.

### The base template and header are already campaign-page-safe

`freedom_ls/base/templates/_base.html` makes no learner-interface assumptions: `head_title`,
`meta_description`, `extra_head`, `content` blocks, a PostHog snippet, and
`{% include "partials/header_bar.html" %}`. `header_bar.html` branches only on
`user.is_authenticated`, showing `partials/login_prompt.html` (Login + Sign Up) for anonymous
visitors (`freedom_ls/base/templates/partials/header_bar.html:19-23`) — this is precisely what a
campaign page needs in its chrome, and it already exists because the home-page work
(`spec_dd/3. done/2026-07-01_19:44_home_page/1. spec.md`) made the dashboard, catalogue and course
detail public on this same base. There is no separate "public site" base template to build.

### The SEO conventions are already established, once, by the home-page spec

Per-page `head_title`/`meta_description` overrides, JSON-LD via `extra_head`, a dynamic per-site
`sitemap.xml` (`django.contrib.sitemaps`, registered in `config/urls.py`, `Sitemap` classes in
`config/sitemaps.py` — the **composition root**), and a dynamic per-tenant `robots.txt` view are all
specified and (per the spec being in `spec_dd/3. done/`) built. `freedom_ls/learner_interface/checks.py`
(`W001`) already warns if a `sitemap` URL is wired without `django.contrib.sitemaps` installed — the
house pattern for "warn the downstream about missing wiring" that a campaign-page feature would
reuse rather than reinvent. `freedom_ls/contrib/conformance/test_urls.py:88-106` is the existing
portable assertion that a downstream project has replicated the reference `sitemap`/`robots_txt`
wiring — any new campaign-page URLs a downstream adds to its sitemap are the downstream's own
responsibility to add to `config/sitemaps.py`, exactly as course URLs already are.

### Theming already has three tiers, and a campaign page is a Tier-3-shaped problem at most

`docs/how tos/theme-fls.md` documents CSS tokens (Tier 1), component classes (Tier 2), and full
template overrides (Tier 3, "escape hatch only"). A campaign page's hero/CTA-panel/feature-grid
sections are naturally **new cotton components** (`<c-vars>`-driven, theme-shadowable at
`themes/<slug>/templates/cotton/<name>.html` exactly like every other component) — this is Tier 2/3
of an existing mechanism, not a new one. Nothing about theming assumes only the learner interface
uses cotton components; `content_engine`, `panel_framework` and `learner_interface` all ship their
own. A `landing_pages`-labelled app is not required merely to get theme-overridable markup — any app
can ship cotton components under its own `templates/cotton/` namespace (`claude_plugins/fls-dev/skills/template/SKILL.md:16`,
"the `cotton/` namespace is flat").

### Multi-tenancy: campaigns are request-scoped, not `Site`-scoped, by any existing mechanism

`freedom_ls/site_aware_models/` and `get_cached_site(request)` resolve tenancy per-request from the
domain; `FLS_THEME` is a single, deployment-wide environment variable (`docs/how tos/theme-fls.md`
§`FLS_THEME` and `FLS_THEMES_DIRS`), not per-`Site`. So a deployment serving several `Site`s already
has exactly one active theme for all of them — a campaign page inherits that same constraint with no
new problem to solve, but it also means "a different look per tenant for the same campaign" is not
something the theming layer gives for free; that would need the downstream's own view logic (e.g.
branching a campaign template by `get_cached_site(request)`), which is squarely inside "how a
concrete project builds one page," not an FLS extension point.

## Option A — FLS ships a landing pages app (`freedom_ls/landing_pages/`)

**What it would contain**, if built: a Django app with `urls.py` (a generic dispatch route, e.g.
`path("go/<slug:campaign_slug>/", views.render_campaign_page)`), a view that resolves a template by
slug (`landing_pages/campaigns/<slug>.html`, `TemplateDoesNotExist` → 404) so a concrete project
supplies pages purely by dropping template files, plus the one genuinely new piece of machinery: a
`Lead`/`ContactRequest` model + unauthenticated capture view for the "contact details, no account"
action, and cotton section components (hero, CTA panel, stat strip) under
`landing_pages/templates/cotton/`.

**What it must NOT contain**, per the settled "developer-authored, no CMS" decision: no admin-editable
page model, no page-builder, no rich-text/blocks field, no template stored in the database, nothing
resembling Wagtail's `Page` tree. Every campaign page's copy and layout is a `.html` file committed
to a repo — FLS supplying "an app" must not smuggle a CMS back in through a generic
`slug → database-stored content` model; the slug → **template path** resolution described above stays
purely filesystem-based for exactly this reason.

**Cross-app edges this introduces** (checked against `docs/app_structure.md`): a `landing_pages` app
that wires CTAs into all four actions would import `accounts` (signup/`next` helpers), `course_access`
(reading `CourseAccessDecision.cta_label`/`cta_url` the way `learner_interface` already does — this
means `landing_pages --> course_access`, mirroring `learner_interface --> course_access`), optionally
`course_applications` and `course_interest` for their URL names (or these can stay reversed by name
only, avoiding an import), `content_engine` (looking up a `Course` for a campaign tied to one), and
`site_aware_models` (if the `Lead` model extends `SiteAwareModel`, which it should, per house
convention — every concrete model in the codebase except `accounts.User` and
`role_based_permissions.SystemRoleAssignment` does, per `docs/app_conventions.md:88-97`). That is a
five-or-six-edge fan-in comparable to `learner_interface`'s own dependency list
(`docs/app_structure.md:93-104`), which is currently the single most heavily-depended-on-from app in
the graph. **Any implementation plan that introduces these edges should be called out and approved
in the plan-structure review** per `docs/app_structure.md:5`, and `docs/app_structure.md` itself must
be regenerated (`/app_map`) once the edges land.

**What downstream would supply into it**: campaign template files at the app's slug-resolved template
path — this is filesystem convention, not theme shadowing (theme shadowing exists to let a theme
*override an FLS-authored default*; a campaign page has no FLS-authored default to override, it is
net-new content). It is closer to a settings-declared registry or a bare URL-include pattern than to
Tier-3 theming.

**What FLS gets to test and guarantee, if it ships this app**: that the dispatch view 404s cleanly on
an unknown slug, that the `Lead` model's constraints/spam-safety hold, that CTA resolution reads
`CourseAccessDecision` correctly, and — via `freedom_ls/contrib/conformance/` — that a downstream's
URLconf still wires the app's routes (the same `test_fls_namespace_reverses` pattern used for every
other contract route today, `freedom_ls/contrib/conformance/test_urls.py:28-101`). What it explicitly
**cannot** guarantee is that any given campaign page reads well, converts, or matches a brand — that
content is unowned by FLS by design, so the app's own test suite would be almost entirely about the
generic dispatch/lead-capture machinery, not about "landing pages" as a feature.

**The strongest problem with this option**: every other FLS extension point that ships as "an app"
or "a backend" ships with a **working, sensible zero-config default** —
`FreeOnlyCourseAccessBackend` is a real, usable access policy (`freedom_ls/course_access/backends.py:226-301`);
the `default` theme is a real, usable brand (`freedom_ls/themes/default/`); `panel_framework` renders
real, usable admin screens out of the box. A `landing_pages` app has **no possible default** — there
is no copy FLS could ship that would be right for an unknown downstream's unknown campaign, and the
"no CMS" decision means it can't fall back to "an admin-editable stub page" either. So a
`freedom_ls/landing_pages/` app would, on a fresh install, do precisely nothing until a downstream
writes templates into it — which is a different shape of "ships out of the box" than anything else in
`CLAUDE.md`'s "FLS will work out of the box" promise (`CLAUDE.md`, opening paragraph) currently covers.
That is not disqualifying on its own (an empty, well-tested dispatch mechanism is still "working"),
but it is the tell that the *routing* half of this feature is thin enough not to need an app boundary
at all, even if the *lead-capture* half genuinely does.

## Option B — concrete project only

**What each concrete project would write from scratch**: its own Django app (or a few views inside an
existing project app) with a URL per campaign, a template per campaign extending `_base.html`, its
own `head_title`/`meta_description`/JSON-LD blocks per the already-documented pattern, its own
contact-capture model/view (because Option A's one piece of shared machinery does not exist in this
option), and its own wiring of each campaign URL into `config/sitemaps.py`.

**What FLS would have to change or document for this to be easy and correct**, none of it code:

- Confirm (in a how-to, alongside `docs/how tos/theme-fls.md`) that `_base.html` is intentionally
  usable outside the learner interface — this research found nothing in `_base.html` that assumes
  otherwise, but nothing states it as a contract either, so a downstream author currently has to infer
  it. A short doc removes that ambiguity.
- Document the SEO block conventions the home-page spec established (`head_title`, `meta_description`,
  `extra_head` for JSON-LD, the `sitemap.xml`/`robots.txt` composition-root pattern) as a **recipe**,
  the way `theme-fls.md` documents theming as a recipe.
- Document `next` threading and the deferred-login pattern end-to-end from a campaign page's point of
  view: link straight at the backend-resolved `cta_url` (never build `?next=` by hand — let
  `@login_required` generate it, exactly as `course_detail` already does per
  `spec_dd/3. done/2026-07-01_19:44_home_page/1. spec.md` §4.1) and validate any other `next` with
  `url_has_allowed_host_and_scheme` (`accounts/utils.py:110-139`, `redirect_to_auth`).
- Document the reusable cotton section components — but if none of these exist in FLS yet (verified:
  no hero/CTA-panel/feature-grid components exist in any app today), "document" is aspirational until
  something is actually built; this option either accepts each concrete project rebuilding these from
  Tailwind utility classes and existing primitives (`<c-button>`, `<c-chip>`) every time, or it quietly
  reintroduces a shared-components question that Option A's cotton components would have answered.
- The template-repo scaffolding (`spec_dd/3. done/2026-07-18_17:09_support-concrete-project-deployment-5-template-repo-scaffolding/`)
  is the natural home for a **starter example** campaign page/app — matching that spec's own reuse
  boundary: "artifacts" (a worked example a new project copies and edits) live in the template repo,
  while "code primitives" (anything genuinely reusable) live in `freedom_ls` itself
  (`spec_dd/3. done/2026-07-18_17:09_.../1. spec.md` §3). A worked example is not the same as shared
  machinery — it forks the moment it's copied.

**What gets duplicated across concrete projects, and does it matter?**

- The contact-capture `Lead` model and its spam/validation handling (honeypot fields, rate limiting,
  `SiteAwareModel` isolation) — duplicated per project, and this one *does* matter: it is genuinely
  reusable, security-sensitive machinery (comparable to `CourseInterest`'s own minimal, deliberate
  shape), and re-implementing it per concrete project is exactly the kind of divergence FLS otherwise
  avoids by design (`app_conventions.md`'s house patterns, the `CourseAccessBackend` seam, etc. all
  exist to stop exactly this kind of per-project reinvention of infrastructure).
- The SEO/CTA/`next` wiring — duplicated only in the sense of "each project writes its own template
  tags calling the same underlying FLS URLs and backends"; this is low-risk duplication because it is
  thin glue over already-tested FLS surfaces, not new logic.
- Campaign copy and layout — duplication is **the point**; per-campaign, per-audience pages are
  supposed to diverge, and forcing them through one shared app would work against the "developer,
  in-repo, per-campaign" authoring model the idea already settled on.

## Middle option — FLS ships machinery, not an app; the concrete project owns the page

The codebase evidence above narrows to a seam that doesn't require a `freedom_ls/landing_pages/`
label at all:

1. **FLS ships the one piece of genuinely new, security-sensitive, zero-config-able machinery**: a
   contact-capture (`Lead`) model and an unauthenticated capture view/form, sized like
   `CourseInterest` (`freedom_ls/course_interest/models.py`) — minimal, `SiteAwareModel`-based, one
   migration. Whether this lives in a new minimal app (candidate name: `contact_capture` or
   `lead_capture`, following the extractable-app naming precedent) or is folded into an existing
   adjacent app is a decision for the spec, not this research — but the model has to live in an FLS
   app, not the concrete project, for the same reason `CourseAccessBackend` lives in FLS and not in
   every downstream: it is infrastructure with a sensible default, not campaign content, and
   duplicating it per project reproduces exactly the migration-divergence risk
   `spec_dd/3. done/2026-06-26_14:55_concrete-implementation-helpers/idea.md` was written to avoid
   ("Concrete implementations must also never need to *fork* FLS models/migrations").
2. **FLS ships reusable cotton section components** (hero, CTA panel, stat strip, feature grid) as
   Tier-2/3-theme-overridable primitives, the same way `<c-button>`/`<c-chip>` already are — this adds
   templates, not an app boundary, and needs no migration.
3. **FLS documents, but does not code, the routing/SEO/CTA seam**: a how-to (sibling to
   `theme-fls.md`) that says: extend `_base.html`; set `head_title`/`meta_description`/`extra_head`
   per the existing convention; link CTAs at the backend-resolved `cta_url`/`cta_url` for course
   actions, at `account_signup?next=...` for platform signup, and at the new contact-capture view for
   the no-account action; register each campaign URL in your own `config/sitemaps.py`; consume
   whatever cookie/session values `referral-link-tracker` lands for attribution.
4. **The concrete project owns everything else**: routing (its own `urls.py`/app), every campaign
   template, every page's copy, and the decision of how many campaign pages to build and when.

Where precisely the seam falls: **FLS owns infrastructure with a real default (the lead-capture
model, the shared components); the concrete project owns anything that is inherently per-campaign
(routing, copy, layout, SEO metadata values)**. This is the same line FLS already draws for course
access (`CourseAccessBackend` ships the machinery and a real default policy; the *course catalogue's
content* is entirely the downstream's own `Course` rows) and for theming (FLS ships the token/class
mechanism and one real default theme; the *brand* is the downstream's).

## Recommendation

**Do not ship a `freedom_ls/landing_pages/` app.** Ship the lead-capture model/view as a small,
focused FLS app (or an addition to an existing adjacent one — a spec-time decision), ship a handful
of reusable cotton section components, and document the routing/SEO/CTA seam as a how-to. Everything
else — every actual campaign page — lives in the concrete project.

**Reasoning, tied to how FLS already draws this line:**

- `CourseAccessBackend` (`freedom_ls/course_access/backends.py`) is FLS's clearest precedent for "ship
  the machinery, let the project supply the policy" — and it works because the machinery
  (`CourseAccessDecision`, the resolution protocol) is genuinely reusable across every access model,
  while the *policy* (which courses are free, which are gated) is unavoidably per-deployment. Campaign
  pages split the same way: the *conversion mechanics* (CTA targets, `next` threading, contact
  capture) are reusable; the *campaign* is not.
- Theming (`docs/how tos/theme-fls.md`) is FLS's clearest precedent for "ship a real default plus an
  override mechanism" — and it works because there is one sensible default brand. Landing pages have
  no equivalent sensible default copy, which is the strongest single argument in this research against
  an app boundary: an app with no possible working default doesn't earn the label "ships out of the
  box" the way every sibling extension point does.
- `freedom_ls/contrib/conformance/` and the panel-framework/theme precedents show FLS is willing to
  test a *contract* (a route reverses, a backend instantiates, a theme resolves) without owning the
  *content* behind it. The same shape applies here: FLS can test that the lead-capture view exists and
  behaves safely, without ever testing a campaign page's copy — because there is no campaign page in
  FLS to test.
- The single strongest argument **for** shipping more into FLS (an app, not just a model) is
  discoverability and consistency: a documented how-to can be skipped or drift out of date across many
  concrete projects in a way that an actual, imported, tested Python module cannot. If several
  concrete projects end up independently reinventing the same slug→template dispatch view, that is a
  sign this middle option under-shipped and a thin `campaign_pages` dispatch helper (still no models,
  still no content) should graduate into FLS later — but that graduation should wait for at least one
  real concrete project's routing pattern to exist, per the "keep the template thin, push proven
  reusable logic into FLS" principle already stated in
  `spec_dd/3. done/2026-06-26_14:55_concrete-implementation-helpers/idea.md` and its
  `research_comparable_frameworks.md` (§7(b): "Keep template logic minimal; push functionality into
  FLS itself" — but only *proven* functionality, which a first implementation is not yet).
- The single strongest argument **for Option B all the way down** (no new FLS app at all, not even for
  contact capture) is minimalism: "don't build functionality that is not explicitly requested"
  (`CLAUDE.md`). But the idea *does* explicitly request "contact-detail capture with no account
  created" as one of exactly four required conversion actions, so this argument only wins if the spec
  author decides that action can be deferred rather than built now — a legitimate scope decision, but
  a different one than "where should the code live."

## A short, labelled aside: how comparable Django-distributable products draw this line

(Web research, kept short per the brief; the FLS-specific analysis above is repo-grounded and does the
real work.)

- **django-oscar** and **Saleor** are e-commerce platforms, not CMSes, and neither ships marketing/
  landing-page authoring at all — merchants are expected to bring their own storefront/marketing layer
  (Saleor's headless storefront is a *separate* repo entirely; Oscar expects a themed Django frontend
  built by the integrator). Neither treats "the marketing page" as core-framework territory, which is
  the same conclusion this research reaches for FLS. [Saleor FAQ](https://docs.saleor.io/docs/3.x/developer/community/faq),
  [django-oscar customisation docs](https://django-oscar.readthedocs.io/en/latest/topics/customisation.html).
- **Mezzanine** and **django CMS**, by contrast, exist specifically to be the marketing/landing-page
  authoring layer, database-editable pages included — i.e. exactly the CMS shape this idea has already
  ruled out. Their existence is useful mainly as a negative reference: they demonstrate what "ship an
  app for this" looks like when the app *is* meant to own content authoring, which sharpens the
  contrast with what a `freedom_ls/landing_pages/` app would have to be instead (content-free
  scaffolding) if it were built anyway. [django CMS](https://www.django-cms.org/), [Mezzanine](https://mezzanine.jupo.org/).

## Costs a recommendation must own

- **Migrations**: the routing/SEO/documentation half needs none. The lead-capture model, wherever it
  lands, needs exactly one new migration (comparable in size to `course_interest`'s
  `0001_initial.py`) — every concrete project runs it once, the same as any other FLS app addition.
  If the recommendation's lead-capture piece is deferred out of the first iteration, this cost is
  zero for now.
- **Downstream test suite**: any new FLS app/module adds to the vendored `freedom_ls/` test tree that
  a downstream's `pytest` collects by default (`spec_dd/3. done/2026-07-18_13:35_test_portability_2_conformance_suite/upgrade_notes.md`).
  A lead-capture app's own tests are genuinely portable contract tests (no brand/demo-content
  dependency) and should carry no `fls_internal` marker; if FLS is ever tempted to ship *example*
  campaign pages to demonstrate the pattern, those examples' tests would need `fls_internal`
  (`spec_dd/3. done/2026-07-09_09:37_fls-test-portability-part1/upgrade_notes.md`'s definition: "marks
  tests that only pass under FLS's own settings, theme, branding or demo content") — another reason to
  keep FLS's shipped surface to machinery only, with no example content to test. If the lead-capture
  view is reachable and app-installed, add a `test_fls_namespace_reverses` probe
  (`freedom_ls/contrib/conformance/test_urls.py:28-86`) for its URL, matching every other contract
  route.
- **Upgrade notes**: per the structured `upgrade_notes.md` format now required at spec completion
  (worked examples throughout `spec_dd/3. done/*/upgrade_notes.md`), a new lead-capture app sets
  `requires_migrations: true` and documents the manual `migrate` step; the documentation-only half of
  this recommendation (the how-to) needs no upgrade notes at all, since it changes no FLS-shipped
  code, model, template, setting or dependency for existing downstreams.
- **`docs/app_structure.md` regeneration**: needed only if the lead-capture app is built and gains
  runtime imports (most likely `site_aware_models`, possibly `accounts` if it links a `Lead` to a
  `User` on later conversion). Run `/app_map` once that app's dependencies are final; the
  documentation-only and cotton-component halves of this recommendation add no new cross-app edges at
  all.
- **The "works out of the box" promise** (`CLAUDE.md`, opening paragraph): the recommendation is
  compatible with it precisely because it ships nothing that requires a downstream to write content
  before it functions — the lead-capture app works out of the box (a working, empty-until-used
  capture endpoint, comparable to `CourseInterest` requiring no course-specific configuration to
  function), and the how-to/components require no downstream action at all until a campaign page is
  actually being built. An app framed as "landing pages" would have broken this promise, since it
  would have shipped inert until a downstream supplied every byte of its actual output.

status: ok
