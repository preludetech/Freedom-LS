# Research: what a git-managed markdown blog needs, and common blog UX patterns and complaints

Method note: the URLs below are the canonical documentation pages for each system. They were cited from prior knowledge and not re-fetched in this session, so check details against them before relying on specifics. The codebase section was verified by grep.

## 1. What FLS already has (verified)

- `config/sitemaps.py`: `StaticViewSitemap` (course catalogue) and `CourseSitemap`. They are built per request, so they are multi-tenant safe. Course visibility reuses the access backend's `filter_visible`, evaluated as an anonymous user.
- `config/urls.py`: `/sitemap.xml` is wired to `_sitemaps = {"static", "courses"}`. `django.contrib.sitemaps` is in `INSTALLED_APPS` (`settings_base.py:83`).
- `config/views.py` `robots_txt`: dynamic. It emits `User-agent: *`, `Allow: /courses/` and an absolute `Sitemap:` line. Articles would need an Allow entry and a sitemap class. Whether anything else is disallowed by default needs a check, since the output only allows `/courses/`.
- Not found anywhere in `freedom_ls/` or `config/` (py or html): Open Graph tags, Twitter card tags, `rel=canonical`, RSS/Atom feeds (no `syndication` use), and schema.org JSON-LD. The only "canonical" hits were unrelated.
- Consequence: the sitemap and robots plumbing exists and can be extended. The meta-tag, feed and structured-data layers would be new.
- Not checked in this pass: whether a logged-out base layout exists. The course catalogue is public, so one probably does.

## 2. Frontmatter fields across reference systems

| Field | Hugo | Jekyll | Eleventy | Astro collections | Ghost | Wagtail |
|---|---|---|---|---|---|---|
| title | `title` | `title` | `title` | schema (user-defined) | title | `title` |
| slug / URL | `slug`, `url` | `permalink`, or filename | `permalink` | file id, or `slug` | slug | `slug` |
| date | `date` | `date` (or filename) | `date` | schema (`pubDate`) | published_at | `first_published_at` |
| updated | `lastmod` | `last_modified_at` (jekyll-seo-tag or sitemap plugin) | custom | schema (`updatedDate`) | updated_at | `last_published_at` |
| author | `author` (param) | `author` | custom | schema, or `reference()` to authors | authors | custom FK |
| summary | `description`, `summary` | `excerpt`, `description` | custom | schema | custom_excerpt | `search_description` or custom |
| hero image | `images`, or a page bundle `feature` | `image` | custom | `image()` helper | feature_image | custom |
| tags / categories | `taxonomies` (`tags`, `categories`) | `tags`, `categories` | `tags` (also drives collections) | schema | tags | tags |
| draft | `draft: true` | `published: false`, or the `_drafts/` folder | `draft` (via a pattern) | schema `draft` plus a filter | status | live flag |
| future dates | `publishDate`, `expiryDate` | `future: false` default | custom | custom filter | scheduled | go_live_at, expire_at |
| canonical | `canonicalUrl` (often a theme param) | `canonical_url` (jekyll-seo-tag) | custom | custom | canonical_url | custom |
| og image | `images` | `image` | custom | custom | og_image | custom |

Sources:
- https://gohugo.io/content-management/front-matter/
- https://jekyllrb.com/docs/front-matter/
- https://jekyllrb.com/docs/posts/
- https://www.11ty.dev/docs/data-frontmatter/
- https://docs.astro.build/en/guides/content-collections/
- https://ghost.org/docs/content-api/
- https://docs.wagtail.org/en/stable/reference/pages/model_reference.html

### Essential for v1

- `title`.
- Stable `slug`. Hugo, Jekyll and Eleventy all derive URLs from filename or slug, so defaulting to the filename is common.
- `published_at` (date). It sets the sort order, shows on the page and feeds the feed and sitemap.
- `summary` / description. It serves as the index blurb, the meta description and the OG description.
- `author` (a plain name string is enough for v1).
- `draft` / published flag. Without it a git blog cannot hold work in progress.
- `tags`. These are cheap, and the idea's "no pagination" index benefits from some way to filter.

### Nice-to-have

- `updated_at`. It is useful for sitemap `lastmod` and Article schema `dateModified`. It can default to the file's git or mtime, but those are unreliable after a checkout or deploy, which is a known flat-file gotcha.
- Hero image and separate OG image, with fallback hero then site default.
- `canonical_url`, for cross-posted content.
- Author as a structured entity (bio, avatar, page). Astro's `reference()` and Wagtail's author FK are examples.
- Categories (separate from tags).
- `featured` / pinned flag.
- `redirect_from` / slug aliases (see section 5).
- `expiry` and `go_live` scheduling.
- Reading time. It is derivable, so it needs no field.
- Series / "part of" metadata.

## 3. Index, tag pages, feeds, sitemap

- No pagination is workable for small to medium blogs. Common practice for sites that show everything is a reverse-chronological list, often grouped by year (Astro blog starter, Eleventy base blog, Jekyll default `index`). It is usually plain titles plus dates and a summary, with no images, so the page stays light.
- Featured / pinned: one hero or featured post at the top, then the rest chronological. This is a nice-to-have.
- The cost of no pagination is page weight and a long scroll once a site passes a few hundred posts. Mitigations are a text-only list, lazy-loaded images, and tag filtering.
- Tag pages: Hugo generates them automatically through taxonomies. Eleventy and Jekyll need pagination or collection templates. They give crawlable topical hubs. Tag pages should be `noindex` or not duplicate full content if they are thin. This is nice-to-have, not essential.
- RSS/Atom is expected by blog readers. Hugo and Jekyll (jekyll-feed) ship it by default, and Django has `django.contrib.syndication`. It needs the title, link, date and summary (or full content) per item, plus a `<link rel="alternate" type="application/rss+xml">` in `<head>` for autodiscovery. It is cheap, so strong v1 candidate or first follow-up. In a multi-site setup the feed must be per site.
- Sitemap: Django's sitemap framework is already present (section 1). Add articles with `lastmod`. Drafts and unpublished articles must be excluded.
- Sources:
  - https://gohugo.io/templates/rss/
  - https://github.com/jekyll/jekyll-feed
  - https://github.com/jekyll/jekyll-sitemap
  - https://docs.djangoproject.com/en/stable/ref/contrib/syndication/
  - https://docs.djangoproject.com/en/stable/ref/contrib/sitemaps/

## 4. SEO and social sharing essentials

### Essential for v1

- Unique `<title>` and `<meta name="description">` per article. Description comes from the summary.
- Clean slug URLs, for example `/blog/<slug>/`, with no dates or IDs, so they survive reorganisation.
- `rel="canonical"` pointing at the self URL. This guards against query-string duplicates and multi-site host variants.
- Open Graph basics: `og:title`, `og:description`, `og:type=article`, `og:url`, `og:image`. Also `twitter:card=summary_large_image`. Without them shares render as bare links. This is the most visible payoff for sharing. Images should be an absolute URL, ideally 1200x630.
- Sitemap inclusion and a robots allow (section 1).

### Nice-to-have

- JSON-LD `Article` / `BlogPosting` structured data (`headline`, `datePublished`, `dateModified`, `author`, `image`). Google recommends it but does not require it.
- `article:published_time` and `article:tag` OG properties.
- Auto-generated OG images.
- `hreflang` (multilingual).

Sources:
- https://ogp.me/
- https://developers.google.com/search/docs/appearance/structured-data/article
- https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- https://developer.x.com/en/docs/x-for-websites/cards/overview/abouts-cards
- https://developers.google.com/search/docs/fundamentals/seo-starter-guide

## 5. Stable URLs when slugs change

- Changing a slug breaks inbound links and SEO. Flat-file systems handle this with front-matter aliases. Hugo has `aliases:`, which generates redirect stubs. Jekyll has the `jekyll-redirect-from` plugin with `redirect_from:`. Ghost and Wagtail keep a redirect table.
- Alternatives: never change the slug (a convention), or make the slug a frozen field after first publish.
- Whether to build it in v1 is a decision for the spec. A convention-only v1 is viable, but a content sync that silently renames a slug produces 404s. One question worth settling is how a rename is detected, given that the synced content is keyed by file path or slug.
- Sources:
  - https://gohugo.io/content-management/urls/#aliases
  - https://github.com/jekyll/jekyll-redirect-from
  - https://docs.wagtail.org/en/stable/reference/contrib/redirects.html

## 6. Internal links between articles, and related articles

- Hugo `ref` / `relref` resolve a path to a URL at build time. A missing target fails the build in Hugo by default (the `refLinksErrorLevel` setting). Source: https://gohugo.io/content-management/cross-references/
- Jekyll `{% link _posts/2020-01-01-foo.md %}` fails the build if the file does not exist. `{% post_url %}` behaves the same way. Source: https://jekyllrb.com/docs/liquid/tags/#links
- Astro `reference('posts')` in the collection schema validates that referenced ids exist when content is loaded or built. Source: https://docs.astro.build/en/guides/content-collections/#defining-collection-references
- Pattern: reference by stable id or slug, not by URL. Resolve at render or sync time. Fail loudly (or flag) on a missing target. This directly informs the "link to another article" widget. A broken link must be detected at content-sync or validation time rather than found by readers. Behaviour for an unpublished or draft target (render without a link, or error) must also be decided.
- Related / read next:
  - Cheapest: shared tags, then newest.
  - Next and previous by date.
  - Manual `related:` list in frontmatter.
  - Ghost does related by tag. Hugo has a built-in `.Site.RegularPages.Related` by keyword.
  - Nice-to-have for v1. The explicit "link to article" widget covers manual cross-links.

## 7. Drafts, scheduling and unpublishing in git workflows

- Drafts: a `draft: true` flag (Hugo) or `published: false` (Jekyll), or a `_drafts` folder. In all of them the build omits drafts unless a flag is passed (`hugo -D`, `jekyll serve --drafts`).
- Scheduling in a static build: Hugo and Jekyll skip future-dated posts (`buildFuture`, `future: false`), but visibility only changes when a rebuild runs. Static site hosts typically run a nightly cron rebuild to cover this. For a dynamic Django app, a publish-date check at query time (`published_at <= now`) avoids the problem. The sync then does not need re-running.
- Unpublishing: set `draft: true` again, or delete the file. Content that disappears from disk must disappear from the DB, sitemap and feed. This depends on how FLS content sync handles deletions, which was not checked here.
- Preview is the most commonly missed flat-file feature (see section 8). Authors want to see a draft rendered with widgets before publishing. Options: draft articles viewable by logged-in staff, or a local run.
- Essential for v1: a draft flag that hides articles from public index, feed and sitemap. Likely also a direct URL (404 for the public).
- Nice-to-have: scheduled publish through a future date, expiry.

## 8. Common complaints

### LMS-platform blogs (Thinkific, Teachable, Kajabi, LearnDash)

Based on commonly reported themes across review sites and forums, not on one verified source. Treat as indicative.
- Thin SEO controls. Kajabi and Thinkific blogs are reported to offer limited per-post meta, tag handling and URL structure. Teachable is often described as having a minimal or absent blog, and users commonly run WordPress separately.
- The blog is a separate, bolted-on subsystem with its own editor, and it does not share content tooling with courses. That produces two sites and two designs. It is exactly the gap this idea fills.
- Limited customisation of layout, templates and feeds, and weak or absent tagging, RSS and author pages.
- Cross-linking from the blog to courses and a clear call to action are hand-built every time. Course cards with price solve this and are the main selling point of the idea.
- LearnDash is WordPress-based, so blogging works through WordPress and its problems are the WordPress ones (plugins, speed) rather than blog-feature gaps.
- References: https://www.thinkific.com/ , https://kajabi.com/ , https://www.learndash.com/ . Review and forum sources were not fetched.

### Flat-file blog complaints

- Broken internal links, found late. Mitigated with `ref`-style resolution (section 6).
- Image handling: relative paths that break between the editor preview and the site, large unoptimised images, and no alt-text discipline. Hugo page bundles and Astro `image()` colocate images with the post and optimise them. FLS-specific question: how are images alongside the markdown served and resolved?
- No live preview, and no WYSIWYG for non-developer authors.
- Date and "updated" metadata lost on git checkouts (mtime reset).
- Slug renames silently breaking URLs.
- Taxonomy sprawl and inconsistent tags (`Python` vs `python`). A typo creates a new tag. This argues for normalising tag slugs.
- Timezones on `date` values: a naive date can publish a day early or late. Choose and document one convention.

## 9. Public and anonymous access implications

- Blogs are normally public and crawled, unlike most of FLS, which is learner-gated. Articles need an explicit public path and robots allow. Today's `robots.txt` allows `/courses/` only.
- Logged-out layout: the page must look right without a learner session. No progress UI, nav items that assume login, or per-user content. The course cards in the idea already avoid progress and enrollment state, which also makes them cacheable.
- Course cards show a price, and a card must show only courses visible to an anonymous user in that site. The sitemap already uses `filter_visible` as anonymous (section 1). Cards linking to a course that an anonymous visitor cannot see leak existence or give dead links.
- Caching: anonymous, user-independent pages can use `Cache-Control` / `Vary: Cookie` caching or a CDN. A card with price or other data that changes should have a bounded TTL. Pages containing a CSRF token or user-specific nav cannot be cached publicly without care.
- Multi-site: every query, feed, sitemap and canonical URL is per site. Absolute URLs (OG image, canonical) must use the request's site host.
- Crawlability: pages need server-rendered HTML (no HTMX-only content) so crawlers and social scrapers see the title, meta tags and body.
- No pagination means the index page is a single crawlable hub that links to every article. That helps crawl discovery but grows with the blog.

## 10. Summary split

### Essential for v1
- Frontmatter: title, slug, published_at, summary, author (string), tags, draft.
- Hidden drafts (index, feed, sitemap, direct URL).
- Public, logged-out, server-rendered article page and index (newest first, all articles).
- Meta description, canonical, OG and Twitter card tags.
- Sitemap entries and a robots allow for articles, per site.
- "Link to another article" widget that resolves by stable id or slug, with broken-link detection at sync or validation time.
- Course card widgets (price and attributes, link only, anonymous-visible courses only, long and compact variants).

### Nice-to-have
- RSS/Atom feed (cheap; the strongest candidate to promote into v1).
- Tag pages.
- updated_at and lastmod.
- Hero or OG image with fallback.
- JSON-LD Article schema.
- Slug aliases and redirects.
- Structured authors, categories, featured or pinned.
- Related and next or previous articles.
- Scheduled publish and expiry.
- Staff preview of drafts.
- Auto OG images, hreflang.

## Open questions for the spec (not decided here)
- Do slug renames need redirects in v1?
- Does the content sync remove articles deleted from disk?
- How are article images stored and served?
- Does a staff preview of drafts exist?

status: ok
