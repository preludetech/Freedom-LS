---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/blog/templates/blog/article_detail.html
  - freedom_ls/blog/templates/blog/article_list.html
  - freedom_ls/content_engine/templates/cotton/article-card.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: article-images

Articles can now carry an optional image, set with `image` and `image_alt` in their frontmatter.
The article page shows it as a header image and uses it for `og:image` and a
`summary_large_image` Twitter card. Article cards show it as a thumbnail. The blog index is now a
grid of compact article cards.

## Breaking changes

- **Overrides of `cotton/article-card.html`.** The blog index now renders each article as
  `<c-article-card :article="article" variant="compact" />`, passing the `Article` row rather
  than a `path`. An override that only reads `path` renders nothing for these cards, so the
  index shows a heading and no articles. Make your override accept an `article` attribute
  alongside `path`, as the stock component now does.
- **Overrides of `blog/article_list.html`.** The `articles` context variable is now a `list`
  (from `Article.objects.published().with_image_files()`), not a `QuerySet`. Template code that
  calls queryset methods on it, such as `articles.count` or `articles.exists`, now renders
  empty with no error. Use `articles|length` or `{% if articles %}`.

Article frontmatter that worked before still validates. `image` used to be rejected on an
article, so no existing article file sets it.

## Manual steps

1. Run `uv run manage.py migrate`. Migration `freedom_ls_content_engine.0007_article_image` adds
   the `image` and `image_alt` columns to `Article`.
2. Rebuild Tailwind (`npm run tailwind_build`). The changed templates use new arbitrary
   utilities (`aspect-[16/10]`, `aspect-[2/1]`).
3. If you override any of these templates, compare your copy with the new FLS version and port
   the changes you want:
   - `freedom_ls/blog/templates/blog/article_detail.html`: new `og_image` and `twitter_card`
     block overrides, and the header `<img>` between the content header and the body. The view
     now passes `image_file` and `og_image_url` in the context.
   - `freedom_ls/blog/templates/blog/article_list.html`: the row list becomes a
     `<c-grid columns="3">` of compact article cards.
   - `freedom_ls/content_engine/templates/cotton/article-card.html`: takes `article` as well as
     `path`, shows the thumbnail, and puts `p-0` on the card. The markup now lives in an inline
     `{% partialdef article-card %}`.
4. Optional, for content authors: an article can now set `image` (a path relative to the article
   file) and `image_alt`. If `image` is set, `image_alt` is required; write `image_alt: ""` for
   a decorative image. `content_validate` on a directory now fails when an article's `image`
   points at no file the loader would save, or at a file without an image extension.
