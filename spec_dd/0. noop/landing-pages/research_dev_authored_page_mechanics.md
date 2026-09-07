## Research: Django mechanism for developer-authored landing pages

Scope per the idea: developer-authored, per-campaign public pages, roughly one per advert/audience/
course, that persuade a visitor to sign up, apply, register interest, or leave contact details.
Authoring model is settled (templates/markdown committed to a repo, no CMS). This note works out
routing, per-page metadata, layout reuse, and SEO wiring so that page twelve is cheap.

### Naming collision to flag

"Landing page" already names two different things in FLS, neither of them this feature:

- `panel_framework/views.py:585` calls the educator interface's root breadcrumb-less view the
  "root landing page."
- `accounts/tests/test_signup_messages.py` calls the post-signup and post-email-confirmation
  allauth pages "landing pages" (where a toast renders after redirect).

Neither collides badly in code (no shared identifier), but product prose and a future spec should
say "campaign page" or "marketing page" somewhere once, and note it is the *idea.md* sense, not
either of the above. `docs/product/` and the domain glossary have no existing entry for this
concept — it is genuinely new vocabulary; coin it once in the spec.

The referral-tracking work in progress (`spec_dd/2. in progress/referal_tracking/idea.md`) already
plans to capture a `landing_path` GET-parameter/cookie value on **any** URL via middleware. A
campaign page needs no special integration with it — it is attributed the same way any other URL
is, as long as its URL carries the campaign's `utm_*`/`ref` query parameters. This is a reason the
per-page URL should be stable and shareable (see Routing), not a reason to add tracking logic to
the pages themselves.

---

## 1. Routing

**Recommendation: one small Django app in the downstream project (not in `freedom_ls/`), with a
registry-driven dispatch view behind a single URL pattern, keyed by a Django `slug` path converter.**

FLS itself gives no precedent for shipping marketing content inside `freedom_ls/` — the composition
root (`config/`) is where the current install adds site-wide-but-not-FLS-core concerns
(`config/urls.py`, `config/sitemaps.py`, `config/views.py`). A concrete project's `landing_pages`
app sits at that same layer: a normal Django app (own `templates/`, `urls.py` with
`app_name = "landing_pages"`, added to `INSTALLED_APPS`), picked up automatically by the
`app_directories.Loader` already configured in `TEMPLATES[0]["OPTIONS"]["loaders"]`
(`config/settings_base.py:169-184`) — no `TEMPLATES[0]["DIRS"]` change needed, mirroring how every
FLS app's own templates resolve today. This directly answers the idea's own question ("should we
just have a separate Django app called landing pages") — yes, and FLS's own conventions (one
concern per app, `app_name` required, apps depend "downward" per `docs/app_structure.md`) support
it cleanly, since a landing page needs read-only access to `Course`/access-backend data (for its
CTA) but nothing depends back on it.

**Slug-to-template safety, concretely.** Django's `<slug:...>` path converter matches
`[-a-zA-Z0-9_]+` — no `/`, no `.`, so a value coming through that converter cannot contain a path
separator or a `..` traversal segment by construction
([Django path converters docs](https://docs.djangoproject.com/en/5.2/topics/http/urls/#path-converters)).
That rules out the literal traversal attack, but it does not make `render(request,
f"landing_pages/{slug}.html")` a good idea: it would resolve *any* file that happens to sit in that
template directory (including partials never meant to be a page), it can't attach per-page metadata
(OG image, `noindex`, campaign CTA target) that isn't derivable from the slug, and it turns "which
slugs exist" into "whatever files happen to be on disk" rather than an auditable list.

The safer and more useful shape is a small in-app **registry** — a module-level `dict[str, LandingPage]`
(dataclass: `template_name`, `title`, `meta_description`, `og_image`, `cta_url_name`, `noindex`,
`sitemap: bool`) — with one dispatch view:

```python
# landing_pages/urls.py
app_name = "landing_pages"
urlpatterns = [path("landing/<slug:slug>/", views.landing_page, name="landing_page")]

# landing_pages/views.py
def landing_page(request, slug):
    page = LANDING_PAGES.get(slug)
    if page is None:
        raise Http404
    return render(request, page.template_name, {"page": page, ...})
```

Unregistered slugs 404 the same way `get_object_or_404` does elsewhere in FLS (`course_detail`
follows this pattern for hidden courses). Adding page twelve is one registry entry plus one
template — no new `path()` line, no new view function, and the registry is the one place that
answers "what campaign pages exist" for the sitemap (§3) and for tests.

**Rejected alternative: one explicit `path()` + view per page**, matching `learner_interface/urls.py`'s
style (`path("courses/<slug:course_slug>/detail/", views.course_detail, name="course_detail")`).
This is more idiomatic Django for a handful of pages and is exactly what CLAUDE.md's "URL names
snake_case / paths kebab-case / every app defines `app_name`" already covers without adding a
registry concept. It stops paying for itself once campaign pages number in the dozens: every page
needs its own `urls.py` line, its own (often near-identical) view function, and — critically — page
metadata (title/description/OG/noindex) ends up duplicated as template blocks with no single place
to audit which pages exist or are in the sitemap. Recommend it only if the count is expected to
stay in the single digits; otherwise the registry dispatch view above is the one that makes page
twelve cheap. A hybrid also works: explicit `path()`s that all point at the same registry-driven
view function, keeping URLs fully explicit while still centralising metadata — worth it if the
security/audit story matters more than DRYness of the `urls.py` file.

---

## 2. Per-page metadata

Reuse the exact blocks `_base.html` and the home-page spec (`spec_dd/3. done/2026-07-01_19:44_home_page/1. spec.md`
§5) already established — do not invent a parallel metadata system.

- **Title**: override `{% block head_title %}` (`_base.html:16-19`). Follow the existing
  `{{ course.title }} — {{ site_name }}` / `All Courses — {{ site_name }}` suffix pattern
  (`course_detail.html:10-12`, `all_courses.html:3-5`) — `site_name` comes free from
  `site_config` context processor (`freedom_ls/site_aware_models/context_processors.py`).
- **Meta description**: override `{% block meta_description %}` (`_base.html:12-13`, default
  "Learning management system"). For a campaign page this is developer-authored copy on the
  registry entry or hardcoded in the page's own template block — there is no "honestly-sourced
  field" constraint here the way there is for `course.description`, because the page *is* the
  authored copy.
- **Canonical URL**: `_base.html` has no `<link rel="canonical">` today — course/catalogue pages
  don't emit one either. Add it once, as a new optional block in `_base.html`
  (`{% block canonical_url %}{% endblock %}`, empty by default so nothing else regresses), built
  server-side via `request.build_absolute_uri(reverse(...))` exactly as `course_detail`'s JSON-LD
  `url` field already does (`learner_interface/views.py:449-451`). A campaign page matters more
  here than most FLS pages: the same slug run behind several `utm_*`/`ref` query strings must
  canonicalise to the bare URL, not one canonical per query-string variant.
- **Open Graph / Twitter card**: FLS has no OG/Twitter meta today anywhere in `_base.html` — this
  is a genuine gap for landing pages specifically (course/catalogue pages don't need share-card
  images; campaign pages, being link-shared in ads/socials, do). Add `og:title`, `og:description`,
  `og:image`, `og:url`, `twitter:card` as new blocks in `_base.html`'s `<head>`, each defaulting to
  the existing `head_title`/`meta_description` block values so pages that don't override them still
  emit something coherent, following the same block-with-sane-default idiom already used for
  `meta_description`.
- **`noindex`**: no existing mechanism. Add one block, e.g. `{% block robots_meta %}{% endblock %}`,
  emitting `<meta name="robots" content="noindex">` when a page sets it — needed for pages that
  should be reachable (e.g. a still-running paid-ad landing page after the campaign ends, or an A/B
  variant) but not ranked or duplicated in search results. Drive it from the registry entry
  (`noindex: bool`) rather than per-template boilerplate, so it's visible in the one place that
  already lists every page.
- **JSON-LD**: reuse `{% block extra_head %}` (`_base.html:52-53`) with `{{ json_ld|json_script:"..." }}`,
  exactly as `course_detail.html:16-18` and `all_courses.html:9-11` do. Discipline carries over
  unchanged: only honestly-sourced fields. A course-promoting campaign page can reasonably emit
  `schema.org/Course` referencing the real course (same shape as `course_detail`'s JSON-LD,
  `learner_interface/views.py:452-466`); a pure lead-capture or coming-soon page should emit
  nothing rather than fabricate structured data — the home-page spec's decision record
  (`1. spec.md` §7, "JSON-LD limited to honestly-sourced fields") applies verbatim.

None of this needs a database row. Every value above is either static per-page copy (committed with
the template) or derived at request time from `request`/`reverse()`, matching how `course_detail`
already derives its `meta_description` and JSON-LD `url` once per request rather than storing them.

---

## 3. Sitemap and robots

`config/sitemaps.py` and `config/urls.py` are the existing wiring; extend them, don't parallel them.

- Add a `LandingPageSitemap(Sitemap)` alongside `StaticViewSitemap`/`CourseSitemap`
  (`config/sitemaps.py:19-56`). Its `items()` returns the registry entries whose `sitemap` flag is
  `True` (unregistered/`noindex` pages are excluded here too — sitemap and `noindex` should never
  disagree on a page). Its `location(item)` reverses `landing_pages:landing_page` with the slug,
  same shape as `CourseSitemap.location`. Register it in the `_sitemaps` dict in `config/urls.py:40-43`.
- `django.contrib.sitemaps` is already in `INSTALLED_APPS` (`config/settings_base.py:81`) and
  `learner_interface/checks.py`'s W001 check only warns if a `sitemap` URL exists without the app
  installed — nothing new to wire there for a downstream project that already followed the
  home-page spec.
- **Per-site behaviour**: `sitemap.xml` and `robots.txt` are already dynamic and per-tenant —
  `CourseSitemap.items()` relies on `SiteAwareManager`'s automatic site filter and
  `robots_txt` builds its `Sitemap:` line from `request.build_absolute_uri` (`config/views.py:9-17`).
  A landing page has no DB row, so it isn't automatically site-filtered; if a campaign is meant to
  run on only one tenant's domain, that has to be encoded explicitly (§6) and the sitemap's
  `items()` must skip pages not registered for the current request's site, the same way
  `CourseSitemap` skips another site's courses — except here it's a registry lookup by
  `get_cached_site(request).name` instead of a queryset filter.
- **Which pages should stay out of the sitemap or be `noindex`**: a live paid-ad landing page
  usually *wants* to stay unlisted (organic search shouldn't rank a page whose copy assumes the
  visitor already clicked a specific ad and knows the offer/price it references), while a
  coming-soon or evergreen recruiting page usually wants full indexing — matching how
  `CourseSitemap` already keeps coming-soon course pages in while dropping hidden ones
  (`config/sitemaps.py:32-41`, `test_seo_discoverability.py::test_sitemap_excludes_hidden_but_keeps_coming_soon`).
  Put the choice on the registry entry per page rather than deciding it once for the whole app.
- `robots.txt`'s current `Allow: /courses/` line (`config/views.py:16`) does not disallow
  `/landing/` by omission — a plain `robots.txt` with no `Disallow` line allows everything not
  explicitly disallowed, so no change is required there for landing pages to be crawlable. A
  `noindex` page still gets crawled (robots.txt controls crawling, the meta tag controls indexing)
  and that's the correct behaviour for a page a visitor should still be able to *reach* via a direct
  ad link.

---

## 4. Layout and components

**Parent template: `_base.html`, not `_base_interface.html`.** Both existing public pages
(`all_courses.html:1`, `course_detail.html:1`) extend `_base.html` directly.
`_base_interface.html` (`freedom_ls/base/templates/_base_interface.html`) is the logged-in shell —
side panel, breadcrumb header, `#interface-main` swap target — built for the learner/educator
interface, and none of that chrome belongs on a page a visitor lands on from an ad. `_base.html`'s
`{% block header %}` already includes `partials/header_bar.html`, which itself branches on
`user.is_authenticated` to show `login_prompt.html` for anonymous visitors and the user menu for
authenticated ones (`freedom_ls/base/templates/partials/header_bar.html:19-23`) — a landing page
gets a correct anonymous-vs-signed-in header for free, no extra branching needed.

**What's reusable as-is** from `freedom_ls/base/templates/cotton/`:

- `c-page` (`page.html`) — the content-well wrapper (max-width, padding, `width="narrow"` variant)
  every section should sit inside, same as `all_courses.html` does.
- `c-button` (`button.html`) — every CTA ("Apply now", "Register interest", "Enrol for free")
  should be this, not a hand-rolled `<a>`, for cursor/disabled/loading/icon consistency.
- `c-callout` — offer/urgency banners, deadline notices.
- `c-media-card` — a generic bordered figure-with-caption card; usable for a feature grid or
  logos/testimonial cards, though it has no built-in grid layout (that's Tailwind utility classes
  on the caller).
- `c-chip` — small "Free" / "Limited spots" / "Coming soon" badges, same component the catalogue
  already uses for the access badge.
- `c-breadcrumbs` — only relevant if a campaign page sits under a browsable hierarchy; most
  standalone campaign pages won't need it.
- `c-error-page` (`error-page.html`) is the closest existing example of a full centred hero panel
  (eyebrow + heading + prose + CTA row) and is worth reading as a *pattern* even though its actual
  component (status codes, error tone) doesn't fit — it demonstrates the FLS idiom for "one
  full-bleed centred block with a heading and a CTA row" that a landing-page hero component should
  follow.

**What's genuinely missing** — none of these exist anywhere in `freedom_ls/base/templates/cotton/`
or `content_engine/templates/cotton/` today, and would need to be built (in the downstream app, or
upstreamed into `freedom_ls/base` if more than one campaign page needs the same shape):

- **Hero band** — large heading + subhead + primary/secondary CTA pair, optionally with a
  background image or gradient. `c-error-page`'s markup is the nearest relative but is scoped to
  error semantics (status code, level colouring) that don't transfer.
- **Feature/benefit grid** — a 2-4 column responsive grid of icon+title+text blocks. `c-media-card`
  gives the individual card chrome; the grid layout itself would be new.
- **Testimonial/quote block** — nothing in the cotton inventory is a quote component; the closest
  relative is `c-pull-quote` in `content_engine/templates/cotton/`, but that's a markdown-embedded
  content-authoring component (goes through `nh3` sanitisation and expects a `content_instance`
  context, see §5) — not directly droppable into a plain landing-page template.
- **FAQ / accordion** — `c-accordion` exists but, like `c-pull-quote`, lives under
  `content_engine/templates/cotton/` as a markdown-body component (in the `MARKDOWN_ALLOWED_TAGS`
  allowlist, `config/settings_base.py:359-375`), not a general-purpose UI primitive. A plain-template
  landing page needs its own FAQ block (can reuse `<details>`/`<summary>` or Alpine, styled with
  existing surface/border tokens) rather than importing the content-engine one.
- **CTA band** — a full-width closing "Ready to start? [Button]" strip. Trivial to compose from
  `c-page` + `c-button`, but worth naming as a shared partial once more than one campaign page wants
  it, so the closing pitch is visually consistent.

**Template-shadowing-by-path answers the override question directly.** Because Django's
`app_directories.Loader` and `configure_theme`'s `TEMPLATES[0]["DIRS"]` prepending both work by
first-match-wins path resolution, a concrete project can override a single landing page, a single
section partial, or a single cotton component purely by placing a same-path file earlier in the
search order — exactly the mechanism `docs/how tos/theme-fls.md` documents for Tier-3 theme
overrides (`theme-fls.md:280-352`). A landing-page app doesn't need the theme system at all for
*its own* pages (it owns those templates outright, nothing to shadow), but if it wants a
downstream-specific hero variant while reusing a shared FLS-side landing-page skeleton, the theme
directory's `templates/<app>/...` override path is the same mechanism, no new machinery needed.

**Tailwind class scanning — a real gap to flag, not a maybe.** `tailwind.input.css`'s `@source`
globs (`tailwind.input.css:9-12`) only cover `./freedom_ls/**/templates/**/*.html` (plus the theme
subtree). A `landing_pages` app living in the downstream project, outside `freedom_ls/`, is **not**
covered by FLS's own `tailwind.input.css` — but per `theme-fls.md`'s "Build-time half" section,
downstream projects own their own `tailwind.input.css` and hardcode their own `@source` globs
already. The concrete action for whoever builds this app: add
`@source "./landing_pages/templates/**/*.html";` (or wherever the app's templates live) to the
downstream `tailwind.input.css`, or any Tailwind utility class used only inside a landing-page
template compiles to nothing and the page silently loses styling — exactly the failure mode
`theme-fls.md`'s "New utility classes in theme templates" section already warns about for Tier-3
overrides (`theme-fls.md:374-382`).

---

## 5. Template vs markdown — recommendation: plain Django templates (with cotton), not the
markdown pipeline

`render_markdown()` (`freedom_ls/markdown_rendering/markdown_utils.py:15-73`) is a pure function —
it takes a markdown string, an optional `request`, and a context dict, and returns rendered,
sanitised HTML. Nothing about it requires a database row; `MarkdownContent.rendered_content()`
(`freedom_ls/content_base/models.py:85-96`) is the only caller and it happens to be a model method,
but the function itself could be called directly from a landing-page view against a `.md` file read
straight off disk. So "does it require a DB row" — no, but that's not where the real cost is.

The pipeline exists to defend against **content authored by someone other than the developer with
repo-write access** — it runs `nh3.clean()` against a strict, curated tag/attribute allowlist
(`markdown_utils.py:39-57`) before any cotton component is compiled, and the cotton tags allowed
through that allowlist are a small, deliberately narrow set of *content-authoring* components:
`c-youtube`, `c-picture`, `c-content-link`, `c-pdf-embed`, `c-file-download`, `c-pull-quote`,
`c-equation`, `c-image-grid`, `c-table`, `c-code-block`, `c-admonition`, `c-flashcard`,
`c-accordion`, `c-card`, `c-slot` (`config/settings_base.py:359-375`). **`c-button`, `c-page`,
`c-callout`, `c-media-card`, `c-chip` — every general-layout component a landing page actually
needs — are not on that list**, and would be stripped by `nh3.clean()` if written inside markdown
source. The content-authoring cotton components that *are* on the list also resolve their images
via `get_file_by_path` against a `content_instance` template variable (`content_engine/templates/cotton/card.html:30`,
same pattern in `picture.html`/`image-grid.html`) — i.e. they expect a real `File` row loaded
through `content_save`, which a landing page's hero/campaign image (a plain static asset, not
ingested course content) does not have.

For a landing page, the sanitisation boundary buys nothing (the "author" is a developer committing
to the repo, already trusted with arbitrary template code) and the curated-tag allowlist actively
works against the page (hero, CTA band, feature grid are exactly the components it excludes). Plain
Django templates using the full cotton component set, `{% static %}` for images, and ordinary
`<h1>`/`<p>` for prose is the direct, friction-free choice — no sanitisation pass, no allowlist to
extend, no `content_instance` to fake. If a page has a long prose section (e.g. an FAQ or an "About
this course" block) and the author would rather write Markdown than raw HTML for just that section,
call `render_markdown()` directly with a plain string (own `.md` file next to the template, or a
Python string constant) inside `c-markdown-container`, accepting that only the narrow
content-authoring tag allowlist works inside it — that's an option per-section, not a reason to
route the whole page through it.

---

## 6. Multi-site scoping

FLS already has an established pattern for **per-site configuration that is not a database row**:
`settings.site_conf`, a dict keyed by `Site.name`, resolved per-request through
`get_cached_site(request)` in the `site_config` context processor
(`freedom_ls/site_aware_models/context_processors.py:9-31`) — `site_conf.get(site_name, {})` reads
`SITE_TITLE`/`SITE_HEADER` per tenant, falling back to a default when a site has no entry. This is
the concrete precedent to extend, not a new mechanism to invent.

**Concrete answer**: the landing-page registry (§1) is keyed first by slug, and each entry either
applies to every site (the common case — a page that just happens to be reachable on every tenant
domain, same URL) or carries an explicit `sites: set[str] | None` field (site names it's registered
for, `None` meaning all). The dispatch view checks
`get_cached_site(request).name in page.sites` (when `page.sites` is not `None`) before rendering,
404ing otherwise — same shape as `raise_404_if_hidden_unregistered` gating course detail pages for
users without access (`learner_interface/views.py:399`, `:508`). `LandingPageSitemap.items()` (§3)
applies the identical filter so a page scoped to one tenant never appears in another tenant's
sitemap, mirroring `CourseSitemap`'s existing site isolation
(`test_sitemap_excludes_other_site_courses`).

This is deliberately **not** per-site template directories or a settings-declared registry-of-registries
keyed by domain — those add a second axis of indirection for a need that, per `site_conf`'s own
shape, is satisfied by one flat dict with an optional site filter per entry. It is also not
per-site URL prefixes: FLS's tenancy model is one Django process/URLconf serving multiple domains,
distinguished by the `Host` header through `django.contrib.sites`
(`freedom_ls/site_aware_models/models.py:32-62`), not by path prefix — a campaign page's URL is the
same `/landing/<slug>/` on every domain it's registered for, and the domain itself (via the request)
is what's already tenant-specific.

One asymmetry worth naming: FLS's *theme* (visual brand — `FLS_THEME`) is resolved once, at process
start, from an environment variable (`docs/how tos/theme-fls.md`'s resolver section) — it is not
per-`Site`. A single deployment serving several tenants therefore already shares one visual theme
across all of them today; a landing page inherits that same constraint (its base styling is the one
active theme for the whole deployment) and this feature doesn't need to solve per-site theming to
ship — it would be solving a problem FLS hasn't solved for the rest of the product either.

---

## 7. Performance and accessibility notes that actually apply

- **Images are not automatically optimised for landing pages.** The image pipeline added in
  `spec_dd/3. done/2026-09-03_12:41_optimise-content-images/` is scoped explicitly to
  `content_engine.File` rows written through `content_save`
  (`1. spec.md` "Scope" §In/§Out) — course-authored content images only. A landing page's hero/OG
  image, served as a plain static asset via `{% static %}`, gets none of that re-encoding. The
  developer authoring the page is responsible for pre-optimising (WebP, sane dimensions) before
  committing it — there is no serve-time or ingest-time safety net for a `static/` asset the way
  there is for course content.
- `c-picture` (`content_engine/templates/cotton/picture.html`) is not a fit for a landing-page hero
  image either — it resolves through `get_file_by_path` against a `File` row and a `content_instance`,
  the same content-authoring coupling noted in §5. A landing page hero is a plain `<img>` (or CSS
  background) against a static asset.
- **Heading order**: `_base.html` renders no `<h1>` of its own (unlike `_base_interface.html`, which
  gets one from `partials/page_title.html`) — a landing page's hero is free to own the page's single
  `<h1>`, same as `all_courses.html`'s `<h1>All Courses</h1>` inside `c-page` (`all_courses.html:15-17`).
  Keep every subsequent section heading at `<h2>`/`<h3>` in document order — nothing enforces this
  automatically, it's a template-authoring discipline the same way it is on every other FLS page.
- **Contrast tokens**: use the paired role tokens (`bg-primary`/`text-on-primary`, etc.) documented
  in `docs/how tos/theme-fls.md`'s "Colour roles" table and enforced by
  `claude_plugins/fls-dev/skills/frontend-styling/SKILL.md` — a hero band with a coloured or
  gradient background must pair with its `on-*` foreground, not an assumed white/black, so the page
  survives a theme swap without a manual contrast re-check.
- **No client-side-only content**: every CTA target (enrol, apply, express interest, or a future
  contact-details form) must be a real server-rendered `<a href>`/`<form action>` reachable without
  JavaScript — HTMX is used for progressive enhancement elsewhere in FLS (`hx-boost`,
  `#interface-main` swaps), never as the only path to content, and a landing page's entire purpose
  (a visitor from a paid ad or a crawler indexing it) makes a JS-only CTA the single worst failure
  mode available.

---

## 8. What would make page twelve cheap

The smallest set of shared pieces, in the order they pay for themselves:

1. **The registry + dispatch view** (§1) — the one piece every other section leans on. Without it,
   page twelve is a new `urls.py` line, a new view function, and metadata scattered across template
   blocks with nowhere to audit "what pages exist."
2. **A `_base.html`-extending landing-page skeleton template** (hero block + content slot + CTA band
   block) that individual campaign templates `{% extends %}` and fill in — so a new page is "write
   the hero copy and the body," not "assemble page chrome from scratch." This is the single biggest
   lever once more than two or three pages exist.
3. **The genuinely-missing components from §4** (hero, feature grid, testimonial, FAQ, CTA band) —
   built once, reused across every campaign page. Each one built ad hoc inside a single page's
   template is the thing that makes page twelve expensive; built once as a cotton component (or a
   landing-page-scoped partial) it's a one-line include.
4. **The metadata defaults added to `_base.html`** (canonical, OG/Twitter blocks, `noindex` block,
   §2) — built once, every page gets correct sharing/indexing behaviour by default and only
   overrides what's campaign-specific.
5. **The sitemap/site-scoping filter on the registry** (§3, §6) — built once, every new registry
   entry just sets `sitemap` and `sites` fields rather than anyone touching `config/sitemaps.py`
   again.

Everything above lives outside `freedom_ls/` in the downstream project's own app, consistent with
the "developer-authored, in the repo" decision already made — FLS's role here is the substrate
(base template, cotton primitives, sitemap framework, site-awareness) it already provides, not a
new subsystem.

---

status: ok
