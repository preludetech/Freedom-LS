---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/content_engine/templates/cotton/image-grid.html
requires_settings_change: true
changed_settings:
  - MARKDOWN_ALLOWED_TAGS  # hard: no boot check, but nh3 silently strips the four new widgets until they are listed
  - INSTALLED_APPS  # optional: add freedom_ls.blog to serve article pages
  - BLOG_URL_PREFIX  # optional: default "articles"; freedom_ls_blog.E001 rejects a malformed value
  - BLOG_NAME  # optional: default "Articles"
  - ARTICLE_SHOW_DATE  # optional: default True
  - ARTICLE_SHOW_AUTHOR  # optional: default True
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: new-content-type-articles

FLS gains articles: standalone public markdown pages loaded by `content_save` from any file with
`content_type: ARTICLE`. The model, admin and widgets live in `freedom_ls.content_engine`. The
public pages (an index and one page per article) live in a new optional app, `freedom_ls.blog`.

## Breaking changes

None that stop a project from booting or break existing content. Two changes alter what existing
content renders:

- **`c-image-grid` now renders through the new `c-grid`.** The grid also drops the outer margin of
  each direct child (`[&>*]:my-0!`), so a picture's wrapper no longer adds `my-6` inside the grid
  and rows close up to the grid's `gap-4`. A project that shadows
  `freedom_ls/content_engine/templates/cotton/image-grid.html` keeps its old markup and does not
  get this.
- **Files with `content_type: ARTICLE` are never collection children.** `content_save` loads them
  in their own pass and skips them when it auto-adopts children from a course or course-part
  directory.

## Manual steps

1. **Run the migration.** It adds the `Article` table
   (`freedom_ls_content_engine` `0006_article`):

   ```
   uv run manage.py migrate
   ```

2. **Add the four new widgets to your `MARKDOWN_ALLOWED_TAGS`.** Your settings file holds its own
   copy of this dict, and nh3 strips any tag not in it without an error. Add:

   ```python
   "c-article-link": {"path"},
   "c-article-card": {"path", "variant"},
   "c-course-card": {"path", "variant"},
   "c-grid": {"columns"},
   ```

   `c-course-card` and `c-grid` work without the blog app. `c-article-link` and `c-article-card`
   need it to link anywhere: without `freedom_ls.blog` installed, an article has no URL.

3. **Optional: turn on the blog.** Skip this if you don't want public article pages; articles
   still load and show in the admin. To serve them:

   - Add `"freedom_ls.blog"` to `INSTALLED_APPS`.
   - In your root URLconf, include the blog URLs **before** the `learner_interface` include at
     `""`, so the learner interface's catch-all never shadows an article slug:

     ```python
     from freedom_ls.blog.config import config as blog_config

     urlpatterns = [
         # ...
         path(f"{blog_config.BLOG_URL_PREFIX}/", include("freedom_ls.blog.urls")),
         path("", include("freedom_ls.learner_interface.urls")),
         # ...
     ]
     ```

     The namespace is `blog`, with URL names `index` and `article_detail` (kwarg `slug`). Once the
     app is installed, the `blog:article_detail` probe in
     `freedom_ls/contrib/conformance/test_urls.py` fails until this include is in place, and so
     does `blog:index` unless you declare it dropped.

   - Copy the sitemap and robots wiring by hand. FLS's own versions are in `config/sitemaps.py`
     (`BlogIndexSitemap` and `ArticleSitemap`), `config/urls.py` (registered in `_sitemaps` as
     `"blog_index"` and `"articles"`, guarded by `apps.is_installed("freedom_ls.blog")`) and
     `config/views.py` (`robots_txt` adds `Allow: {reverse('blog:index')}` beside
     `Allow: /courses/`).

4. **Optional: set the new settings.** All four have defaults:

   | Setting | Default | Owner | What it does |
   |---|---|---|---|
   | `BLOG_URL_PREFIX` | `"articles"` | `freedom_ls.blog` | The path the blog is served under. Lowercase letters, digits and hyphens, single slashes between segments, none at either end. The system check `freedom_ls_blog.E001` fails `manage.py check` on any other value. |
   | `BLOG_NAME` | `"Articles"` | `freedom_ls.blog` | The index page's heading and the label of the article page's link back to it. |
   | `ARTICLE_SHOW_DATE` | `True` | `freedom_ls.content_engine` | Whether bylines show the date when an article's frontmatter doesn't set `show_date`. |
   | `ARTICLE_SHOW_AUTHOR` | `True` | `freedom_ls.content_engine` | Whether bylines show the author when an article's frontmatter doesn't set `show_author`. An article with no author never shows one. |

5. **Rebuild Tailwind.** The new templates (the blog pages, `c-article-byline`, `c-article-card`,
   `c-course-card`, `c-grid`) use utility classes your CSS bundle may not include yet:

   ```
   npm run tailwind_build
   ```

6. **Review `image-grid.html` if you shadow it.** See "Breaking changes". To pick up the new
   behaviour, replace your copy's body with `<c-grid :columns="columns">{{ slot }}</c-grid>`, or
   carry `[&>*]:my-0!` into your own grid classes.
