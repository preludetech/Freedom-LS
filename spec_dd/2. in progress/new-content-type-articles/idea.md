# Articles: a public blog built from content markdown

## What and why

A site needs to host a blog, made of public pages that anyone can read without logging in, written the same
way as course content. That means markdown files with frontmatter in the content repo, loaded by
`content_save`, checked by the validator and written with the same widgets. Course authors shouldn't
need a second tool or a separate CMS to write marketing and editorial pages. Those pages should
point readers at courses with cards that show the price.

**Article** is a new word (it is not in the domain glossary and no model uses it). It means a
standalone markdown content item, `ContentType.ARTICLE`, that belongs to no course and is publicly
readable. It sits next to `Topic`, `Course` and `Form`. **Blog** is the public index that lists a
site's articles.

## Where it lives

- The `Article` model, its pydantic schema, its loading in `content_save`, its validation and the
  new widgets go in `content_engine`. That's where the loader, validator, `SCHEMAS` registry and
  `templates/cotton/` widgets already live, and the offline validator's sync already watches
  `content_engine/schema.py`.
- The public blog index and article pages go in a **new leaf app** that depends on `content_engine`.
  An installing project that doesn't want a blog leaves the app out. A model in a new app would
  create an import cycle with the loader, which is why the model doesn't go there.

## Authoring an article

- An article is a markdown file with `content_type: ARTICLE`. It uses the existing base fields
  (`title`, `subtitle`, `description`, `tags`, `meta`) and the markdown body. `description` doubles
  as the index blurb and the meta description.
- **The slug is authored.** A `slug` frontmatter field sets it, and when that is absent the slug
  defaults to the file or directory name. Unlike topics and courses, editing an article's title
  doesn't change its URL. `CourseCategory` already uses an authored slug (`derive_slug=False`).
- **Publish date.** It orders the index and shows in the byline.
- **Author.** A plain name string.
- **Byline display.** Settings decide whether the date and the author show, with a site-wide
  default. An article can override that per field in frontmatter (`show_date` / `show_author` or
  similar). Finer-grained control can come later.
- **Visibility** follows the `Course.visibility` pattern: `published` (the default) or `hidden`. A
  hidden article is left out of the index and the sitemap, and its URL returns 404 for the public.
  `coming_soon` has no meaning for an article. There's no scheduled publishing, because no other
  content type has it.
- Title and headings follow the topic rule. The title renders as the H1, and a `#` in the body
  shifts down to H2.

## Public pages

- **Blog index.** Every published article, newest first, with title, date (if shown) and
  `description`. No pagination.
- **Article page.** Server-rendered and readable logged out. It has no learner UI, and no progress
  or registration state.
- **SEO.** Per-article `<title>`, meta description, `rel="canonical"`, Open Graph and Twitter card
  tags, sitemap entries, and a `robots.txt` allow for the blog path. All of them are per site. The
  `_base.html` head-metadata blocks described in `docs/how tos/landing-pages.md` and the sitemap in
  `config/sitemaps.py` already exist to build on. Today `robots.txt` allows only `/courses/`.

## Widgets

Both widgets identify their target by a **path relative to the file that uses them**. That's how
`c-content-link` and `c-picture` already work. A path stays stable when a title changes, and the
validator can resolve it.

### Link to another article

An inline link to another article, which renders the target's title or the author's own text. It's
a new widget, not a reuse of `c-content-link`, which is broken today. `Topic.preview_url` reverses a
URL that doesn't exist, and `Form` has no `preview_url`. Repairing `c-content-link` is out of scope.
A link to a hidden article renders as plain text rather than a link the public would hit as a 404.

### Course cards

A card that links to a course's public `course_detail` page and shows its attributes, with no
progress and no registration state.

- **Two variants.** A long horizontal card, and a compact card for grids. The status-free
  `course-card-shell` and `course-row-shell` and `c-course-price` in `learner_interface` are the
  pieces to reuse. The dashboard `course_card.html` and `course_row.html` bake in status and
  progress, so they can't be reused as they are.
- **What a card shows.** Title, subtitle or description, price via `c-course-price`, difficulty,
  estimated duration, and the access badge ("Free", "By application"). The badge comes from the
  backend's `get_access_badge`, never from `access_config`. A free course shows the badge rather
  than "$0". The tax note stays off cards, as it already does in listings. Courses have no image
  field, so the accent-and-icon hero is the visual.
- **One link per card.** A stretched title link (`card_title_link.html`) with neutral wording,
  because the course's own call to action depends on its access type.
- **A card pointing at a hidden course isn't shown**, because the public would get a 404.
  `coming_soon` courses show and link to their detail page.
- Grid cards need a non-paginated grid to sit in. The only existing grid lives inside the paginated
  dashboard partial.

Widgets render with `request=None`, so neither widget can depend on the request or the user. That
suits cards that show no per-user state. `MARKDOWN_ALLOWED_TAGS` is a closed allowlist in each
installing project, and nh3 silently strips any tag that isn't listed. That means the new tags need
upgrade notes, or installers will see nothing.

## Validation and the content editing plugin

- The validator resolves the paths in the new widgets and reports a broken article link or course
  card. Today nothing inspects markdown bodies, so this is a new body-scanning pass that runs after
  everything has been parsed (`validate_category_references` is the precedent). The host validator
  and the bundled offline copy in `claude_plugins/fls-content/validate/` both get it.
- The `fls-content` plugin documents the article content type and both widgets. That covers the
  content-types and widget-reference skills, the content-formatter agent's file-type table, the
  bundled schema, and the trigger words "article" and "blog post". `docs/product/content-editing-workflow.md`
  and `fls-dev`'s `markdown_content.md` list the same types and widgets and get updated alongside.
  `research_content_editing_plugin.md` lists every hand-maintained copy that would otherwise drift.
- `demo_content/` gains demo articles that exercise both widgets against the existing
  `functionality_demo_price_*` and `functionality_demo_application_gated` courses.

## Open for the spec

- Whether `content_save` removes articles that were deleted from disk. Nobody has checked how it
  handles deletions for other types.
- Where articles sit in a content repo (they belong to no course, and the `NN.` numbering
  conventions are course-shaped).
- `og:image`: there's no article image field, so the spec has to choose between a site default and
  an optional image field.
- How an author lays out a group of grid cards, with a wrapping grid widget or one widget that takes
  several paths.
- The heading level of a card title inside an article.
- Whether the horizontal card collapses to the vertical layout on narrow screens.
- URL path for the blog (for example `/blog/` and `/blog/<slug>/`).

## Later specs

Tags and tag pages, an RSS/Atom feed, JSON-LD `Article` data, slug redirects, related articles, a
staff preview of hidden articles, and per-article author pages.

## Research

- `research_content_pipeline_fit.md`: how content is loaded, validated and rendered; the
  `content_engine` versus new-app trade-offs; the broken `c-content-link`; "article" as a free word.
- `research_course_card_widgets.md`: the existing card pieces, course attributes, and card UX and
  accessibility practice.
- `research_blog_features_and_ux.md`: frontmatter, index, SEO and drafts in other flat-file blogs,
  and what FLS already has for sitemaps and robots.
- `research_content_editing_plugin.md`: what the `fls-content` plugin covers and every place that
  would need updating.
