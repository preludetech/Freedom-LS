# Research: how the content pipeline works and where an "article" content type would fit

Scope: findings only, no plan. Paths are relative to the repo root. Terms are this project's own
(`Topic`, `Course`, `ContentCollectionItem`, `File`, `registration`, `Site`).

## 1. Authoring on disk, loading, validating, rendering

### On-disk format
- Markdown content files (`.md`) carry YAML frontmatter, parsed by `python-frontmatter`; the body becomes the `content` key
  (`freedom_ls/content_engine/validate.py`, `parse_markdown_file`).
- Structural files are `.yaml`/`.yml`, multi-document split on `---` lines (`split_yaml_documents`). `part.yaml`, form page yaml and `course_categories.yaml` are examples.
- `content_type` in the frontmatter selects the pydantic schema. For `.md` it must always be written explicitly (`validate_yaml_section`, `validate.py:96-152`).
- `get_all_files` skips `README.md`, `CLAUDE.md`, names starting `_` or `.`, names ending `~`, and anything under `_`/`.` directories (`validate.py:22-75`). `_optimised/` image cache directories rely on this.
- `uuid` is optional in frontmatter; `content_save` writes it back into the source file on first load (`update_file_with_uuid`, `content_save.py:103`). Authors never hand-create it.
- Demo content: `demo_content/` holds courses (`course.md`, numbered `NN. slug/content.md` topic dirs, `form.md`, `part.yaml`) plus a root `course_categories.yaml`. Widget showcase: `demo_content/functionality_demo_content_widgets/` (topics `1. annotation-and-emphasis` ... `5. cards`). Every demo item is course-shaped; there is no standalone-page example.

### Schema layer (pydantic)
- `freedom_ls/content_base/schema.py`:
  - `ContentType` StrEnum: `TOPIC, ACTIVITY, FORM, COURSE, COURSE_PART, COURSE_CATEGORIES, FORM_PAGE, FORM_QUESTION, FORM_CONTENT`.
  - `BaseBaseContentModel` (`extra="forbid"`; `meta`, `tags`, `content_type`, `file_path`, `uuid`) with a registry populated by `__init_subclass__(content_type=...)`; `SCHEMAS = BaseContentModel._registry`.
  - `BaseContentModel` adds `title`, `subtitle`, `description`, `category`, `image` (note the `image` Field's description text says "category", a copy-paste leftover; `image` is a `str` but is not a model column on Topic or Course, so a frontmatter `image:` would fail the `save_with_uuid` model-field check; see below).
  - `MarkdownContentModel` adds `content`.
- `freedom_ls/content_engine/schema.py`: `Topic`, `Activity`, `Course`, `CoursePart`, `CourseCategories` declared as `class X(BaseContentModel, MarkdownContentModel, content_type=ContentType.X)`. `Course` carries `price` (a discriminated union `FixedPrice | RangePrice | DiscountedPrice | OnRequestPrice`), `difficulty`, `estimated_duration`, `learning_outcomes`, `icon`, `visibility`, `categories`, etc.
- `freedom_ls/content_base/tests/test_schema_registry.py:13` asserts `set(ContentType) == set(SCHEMAS)`: adding a `ContentType` member without registering a schema fails that test.
- The schema modules must import with no Django installed (offline validator copies them; see `SLUG_PATTERN` comment in `content_engine/schema.py:40`), though `Course._validate_icon_fields` and `_default_currency` do deferred Django imports that the plugin patches out.

### Django model layer
- `freedom_ls/content_base/models.py`: abstract `BaseContent(SiteAwareModel, TimestampedModel)` with `file_path`, `meta`, `tags` (ArrayField); `TitledContent` adds `title`, `subtitle`, `description`, `slug`; `MarkdownContent` adds `content` and `rendered_content()`; `CONTENT_TYPE` class attribute per concrete model.
- `rendered_content()` calls `render_markdown(self.content, None, context={"content_instance": self})`: widgets render with **no request**, and the only context variable is `content_instance`.
- Concrete models: `freedom_ls/content_engine/models/topics.py` (`Topic`, `Activity`, each with `UniqueConstraint(site, slug)`), `courses.py` (`Course`, `CoursePart`, `CourseCategory`, `ContentCollectionItem`), `files.py` (`File`). Form types live in `freedom_ls/form_engine/models.py` and also use `content_base`.
- Admin: `freedom_ls/content_engine/admin.py` registers each model with `SiteAwareModelAdmin`.

### Loading (`content_save`)
- `freedom_ls/content_engine/management/commands/content_save.py`: `content_save PATH SITE_NAME`; it runs `validate(path)` then one `@transaction.atomic` `save_content_to_db`.
- Flow: scan all files; non-content files go to `save_file_to_db` (images optimised via `image_cache.ImageCache` / `images.py` into WebP with committed `_optimised/manifest.yaml`); content files parsed into pydantic items, grouped by `content_type`, then saved in a hard-coded order (categories, topics, activities, courses/parts, forms, form pages/content/questions), then course-to-form binding, then `ContentCollectionItem` creation from `children` (or directory scan).
- Dispatch on content type is explicit per-type code in `save_content_to_db`; a new `ContentType` needs its own `save_*` function and its own block in this function (nothing is looked up from the registry).
- `save_with_uuid` (`content_save.py:236`) is the generic saver: dumps the pydantic item (excluding `content_type`, `file_path`, `uuid`), refuses any field not present on the Django model, **overwrites `slug` with `slugify(title)` made unique per site via `get_unique_slug`** (`derive_slug=True` default), upserts by `(id=uuid, site)` or creates and writes the uuid back. It also runs `markdown_translate` (turns Obsidian `![[img.jpg | Title]]` into `<c-picture>`) on `content`.
- `tags` handling: absent `tags:` key leaves stored tags alone.
- Consequence for slugs: a content item's slug is **not authored**; it is derived from the title (and changes if the title changes, with `-2`, `-3` suffixes on collision). `CourseCategory` is the one exception (`derive_slug=False`, authored slug).
- Images: `c-picture src=` resolves through `File.objects.get(file_path=content_instance.calculate_path_from_root(src))` (`content_tags.get_file_by_path`), so images are addressed relative to the declaring file and stored as `File` rows keyed by `(site, file_path)`.

### Validation
- `freedom_ls/content_engine/management/commands/content_validate.py` and `validate.py::validate`: per-file pydantic parse, collect-all-errors report, plus a cross-file pass (`validate_category_references`) that resolves references across the whole repo regardless of walk order. This cross-file pass is the existing precedent for validating references between content files.
- Offline copy: `claude_plugins/fls-content/validate/{schema.py,validate.py}` (Django-free, "Bundled from ..." with a numbered `# Patches applied:` list). It mirrors four sources: `content_base/schema.py`, `content_engine/schema.py`, `form_engine/schema.py`, `form_engine/typed_answers.py`. It has its own `ContentType` enum, so a new content type must be added there too. `claude_plugins/fls-dev/commands/update_claude_plugin_fls_content.md` is the sync procedure; its Step 1 grep names the paths whose change triggers a sync (schemas, `validate.py`, `templates/cotton/`, `config/settings_base.py`, `content_save|validate.py`, `demo_content/`).
- Django system checks: `freedom_ls/content_engine/checks.py` only checks settings (E001 required `ADMONITION_TYPES`, E002 `DEFAULT_CURRENCY`, E003 `PRICE_LOCALE`). There is no check that widgets or templates agree with the allowlist.
- Note: nothing validates widget usage inside a markdown body today (see 2). The offline validator has no widget awareness either (a grep of its `validate.py` shows only access-type injection).

### Rendering
- `freedom_ls/markdown_rendering/markdown_utils.py::render_markdown`: Python-Markdown (`fenced_code`, `mdx_headdown`, `tables`, `pymdownx.tasklist`; indented code blocks disabled) -> `nh3.clean` with an allowlist built from `nh3.ALLOWED_TAGS` plus `config.MARKDOWN_ALLOWED_TAGS` (tag -> attribute set) -> `CottonCompiler().process()` -> Django template render with the supplied context. `MARKDOWN_TEMPLATE_RENDER_ON` can disable the cotton step.
- Learner-facing consumers of `rendered_content`: `learner_interface/templates/learner_interface/course_topic.html:12` (Topic), `course_detail.html:207` (Course body, shown to anonymous visitors), `course_form.html`, `form_engine/.../page_children.html`.
- Template tag `{% markdown text %}` (`content_tags.py:135`) renders markdown with the real request but without `content_instance`.

## 2. Widgets (cotton components in markdown)

### Registration and allow-listing
- Template: `freedom_ls/content_engine/templates/cotton/<name>.html` (cotton namespace is global, so any app's `templates/cotton/` is callable).
- Allow-list: `MARKDOWN_ALLOWED_TAGS` in `config/settings_base.py:374-390`: `c-youtube, c-picture, c-content-link, c-pdf-embed, c-file-download, c-pull-quote, c-equation, c-image-grid, c-table, c-code-block, c-admonition, c-flashcard, c-accordion, c-card, c-slot`. Each maps to the exact attribute set; nh3 strips any other tag or attribute **silently**, so an unlisted widget produces no error and no output.
- The setting is read through `freedom_ls/markdown_rendering/config.py` (`MARKDOWN_ALLOWED_TAGS` default `{}`), so it is a per-project (installer-owned) setting: a project that installs FLS and copies the allowlist would not get new widgets automatically. `claude_plugins/fls-dev/resources/markdown_content.md` documents the add-a-widget recipe (create template, register in settings) and its copy of the allowlist is already stale (missing `c-card`).
- Other places that list widgets (all would need an entry): `claude_plugins/fls-content/skills/widget-reference/SKILL.md` (table plus "Authorised attribute sets") and one `resources/c-<name>.md` per widget; `claude_plugins/fls-dev/skills/markdown-content/SKILL.md`; `freedom_ls/markdown_rendering/tests/test_markdown_utils.py` and `test_config.py` reference the setting.
- Widgets get `content_instance` in context (the owning `Topic`/`Course`), declared with `<c-vars>`; they run with `request=None`. `MarkdownContent.rendered_content` comment: "none of them may depend on [the request]". `reverse()` still works; `request.user` does not.
- Widgets belong to `content_engine` templates today but some call across apps by template name (e.g. `c-icon` from `icons`, `c-media-card`/`c-button` from `base`).

### Existing "link to another content item" mechanism: `c-content-link`
- `freedom_ls/content_engine/templates/cotton/content-link.html`: `path` attribute, relative to the declaring file; resolved by filter `get_content_by_path` (`content_tags.py:146`) which does `calculate_path_from_root` then looks up **Topic first, then Form** by `file_path`. Renders `<a href="{{ content_obj.preview_url }}">{{ slot }}</a>`, else a red `<span>` with the missing path.
- State of the mechanism (relevant to reuse):
  - `Topic.preview_url()` reverses `content_engine:topic_detail` (`topics.py:22`), but `freedom_ls/content_engine/` has **no `urls.py`** and the root URLconf has no `content_engine` include (`config/urls.py`); the learner_interface `topic_detail` URL is commented out (`learner_interface/urls.py:52`). So the reverse would fail for a Topic. `Form` has no `preview_url`, so the href renders empty. The template itself carries `TODO: non-preview link; leading and trailing whitespace issue`.
  - It only knows `Topic` and `Form`, uses non-site-qualified `Topic.objects.get(file_path=...)` (site filtering depends on the thread-local request set by middleware), and does a query per link.
  - The widget docs (`claude_plugins/fls-content/skills/widget-reference/resources/c-content-link.md`) present it as working.
- Address schemes available for linking: `file_path` (relative, author-visible, used by `c-content-link`, `c-picture`, `Course.children[].path`, `application_form`), `uuid` (stable id written into frontmatter; `ContentCollectionItem.child_id` is a UUID with a generic FK), and `slug` (derived from title, unique per site and model, not stable across title edits). Cross-file references between content files elsewhere use relative paths resolved with `resolve_author_path`/`content_key` (`content_save.py:423-435`), validated at load time ("names a child that was not loaded" raises).
- No load-time check of widget `path=` targets exists; a dangling `c-content-link` only fails at render.

### Existing course-presentation pieces relevant to a course-card widget (in learner_interface)
- Course price: `Course.current_price()` returns a `CoursePrice` (`content_engine/prices.py`); the single price renderer is cotton `c-course-price` (`freedom_ls/learner_interface/templates/cotton/course-price.html`, `variant` compact/full).
- Card shells: cotton `course-card-shell.html` (grid card) and `course-row-shell.html` (horizontal row) in `learner_interface/templates/cotton/`; the dashboard leaf `learner_interface/templates/learner_interface/partials/course_card.html` branches on `course.listing_status`, progress and registration status (so it is not directly reusable for a no-progress card, but the shells and `c-course-price` are status-free). `course_row.html`, `course_listing_price.html`, `course_details_link.html` partials exist.
- Course attributes available: `title`, `subtitle`, `description`, `icon`/`icon_fallback`, `accent_slot_key`, `difficulty`, `estimated_duration` (`display_estimated_duration()`), `learning_outcomes`, `price_*`, `visibility`, categories, and the access badge (stamped by `learner_interface.utils` via the access backend, not a model field).
- Detail URL: `learner_interface:course_detail` (`courses/<slug>/detail/`).
- Course visibility rule (hidden 404s for anyone not registered, coming_soon stays visible, `filter_visible` on the access backend) is enforced in `course_access/backends.py`/`visibility.py`, which depends on `content_engine`; `content_engine` already uses a dotted-path setting seam (`COURSE_ACCESS_CONFIG_VALIDATOR`, `import_string`) to avoid importing `course_access` (`content_save.py:493-501`).

## 3. Site-awareness and addressing

- `freedom_ls/site_aware_models/models.py`: `SiteAwareModelBase` (FK `site`, `objects = SiteAwareManager()`), `SiteAwareModel` (UUID `id` primary key), `TimestampedModel`. `SiteAwareManager.get_queryset` filters by the site of the thread-local request (set by `site_aware_models/middleware.py`); with no request (management commands, shells) it does **not** filter. `save()` fills `site` from the request when unset.
- Consequence for rendering: `Course.objects` / `Topic.objects` inside a widget is request-scoped through the thread-local, not through `content_instance.site`; `_base_manager` plus an explicit `site=` is the pattern when a site is passed in (`get_unique_slug`, `content_save`).
- `Site` is the tenant and isolation boundary (`Site.name` is what `content_save` takes as `SITE_NAME`). The domain per tenant drives sitemaps (`config/sitemaps.py`, "Sites framework supplies the right domain per request").
- Slugs: `slug` is unique per `(site, model)` constraint, not across models (Topic and Activity each have their own constraint). Routing for learner content is by course slug plus integer index (`courses/<slug>/<int:index>/`), not by item slug; topics have no stand-alone URL today.
- Item identity: UUID primary keys on all content models; file_path stored relative to the content root; `meta` JSON and `tags` ArrayField exist on every `BaseContent`.

## 4. Access control and where learner-facing content is served

- Learner content is served by `freedom_ls/learner_interface/` (URLs mounted at the site root: `config/urls.py:65`). Routes in `learner_interface/urls.py`: dashboard `""`, `courses/` (public listing), `courses/<slug>/detail/` (public), `courses/<slug>/` (resume redirect, `@login_required`), `courses/<slug>/<int:index>/` (`view_course_item`, `@login_required`; renders `Topic` via `course_topic.html` / `{{ topic.rendered_content }}`), form routes (login required).
- Anonymously viewable today: the course catalogue (`all_courses`, "public, no login required") and `course_detail` (renders `course.rendered_content` at `course_detail.html:207` for anonymous visitors, so **markdown/widget rendering already runs for anonymous visitors, but only for `Course.content`**, and only with `request=None`). Topic bodies are not publicly viewable: `view_course_item` needs login and a registration (`course_access` backends decide `can_access_content`).
- `course_access` (`backends.py`, `loader.py`, `visibility.py`, `overrides.py`): pluggable `COURSE_ACCESS_BACKEND` returning `CourseAccessDecision`; every backend delegates to `learner_management.utils.is_registered_for_course`. Access is wholly **course-keyed**: it asks "can this user see this `Course`" and has no concept of a content item outside a course.
- Public/marketing pages precedent: `docs/how tos/landing-pages.md` says public pages are developer-authored, live in the installing project, with no page model/CMS; it provides head-metadata blocks in `_base.html` (including `og_type` where "`article` for something dated and authored"), `meta_robots`, canonical link, `extra_head` for JSON-LD. Sitemap classes live in `config/sitemaps.py` (`StaticViewSitemap`, `CourseSitemap`, composition root, allowed to depend on any app). This is the existing way anonymous, indexable, site-scoped pages are done, but it is explicitly not content-repo driven.
- Anonymous-safe course helpers: `all_courses` / `get_all_courses()` / `get_course_listing` / `backend.filter_visible(user=AnonymousUser(), ...)` in `learner_interface/utils.py` and `course_access/backends.py` (sitemap already uses `AnonymousUser()` with `filter_visible`).
- URL conventions (CLAUDE.md): every app defines `app_name`; snake_case URL names; kebab-case paths. `content_engine` currently has no URL module.

## 5. `docs/app_structure.md` dependency rules (authoritative, generated by `/app_map`)

Relevant edges (runtime):
- `content_base -> markdown_rendering, site_aware_models`
- `content_engine -> base, content_base, form_engine, icons, markdown_rendering, site_aware_models`
- `course_access -> accounts, base, content_engine, learner_management`
- `learner_interface -> accounts, content_engine, course_access, course_interest, course_recommendations, form_engine, icons, learner_management, learner_progress, organisations, site_aware_models, webhooks`
- `markdown_rendering -> base`
- Nothing depends on a hypothetical new app; any new cross-app edge "should be called out and approved before code is written".
- What this means for the idea's pieces (facts, not a decision):
  - A course-card widget living in `content_engine` that applied course visibility via `course_access` would add `content_engine -> course_access`, which closes a cycle with `course_access -> content_engine` (the code already guards against exactly this with an `import_string` seam). Reading `Course` directly (no visibility filter) adds no edge.
  - Reusing `c-course-price` / the card shells (templates in `learner_interface`) from a `content_engine` widget is a template-level, not an import, dependency; the app map is import-based, but `docs/app_structure.md` tracks only imports.
  - A new `articles`-style app depending on `content_base` + `content_engine` (+ `site_aware_models`) would be a leaf, same shape as `learner_interface`; its public URLs would depend on nothing in `learner_interface`.
  - `learner_interface` would need no new edge to serve articles if the article pages live there (it already depends on `content_engine`, `site_aware_models`, `icons`, `course_access`).
  - `config/` (composition root) may depend on any app (sitemaps).

## 6. In `content_engine` vs a new app: trade-offs seen in this codebase (not deciding)

Keeping articles in `content_engine`:
- All the loader, validator and schema plumbing is already there and is hard-wired by content type: `content_save.save_content_to_db`, `validate.py`, `content_engine/schema.py`, the shared `SCHEMAS` registry (`content_base`), admin, factories, and the offline mirror (`claude_plugins/fls-content/validate/schema.py` bundles `content_engine/schema.py` directly; a new app's schema would be a fifth source to bundle and re-sync, and the sync detection grep in `update_claude_plugin_fls_content.md` names only specific paths).
- `content_engine` already owns the widget templates (`templates/cotton/`), `content_tags.py`, `MARKDOWN_ALLOWED_TAGS` consumers, `File`/images and `c-content-link`.
- App label prefix is `freedom_ls_content_engine` (e.g. `"freedom_ls_content_engine.CourseCategory"`); migrations live in one app, which is currently small (0001 to 0005).
- It is already the home of every model the course card would read (`Course`, prices, `CourseCategory`).
- Against: `content_engine`'s docs-level identity is "course content models (topics, activities)"; `docs/app_structure.md` shows it depends on `form_engine` already; a blog is a different consumer (public, no registration) and any educator/learner coupling in `content_engine` models (`ContentCollectionItem` generic FK for course children) does not apply to articles.

New app:
- Clean separation from course/registration semantics (no `ContentCollectionItem`, no access backend); can own its own URLs, templates, sitemap and public views, and be omitted by installers who do not want a blog (FLS "is designed to be installed into other Django projects", CLAUDE.md).
- `content_base` was designed as the shared abstract layer: `form_engine` is an existing precedent for a separate app building concrete models on `content_base` (`form_engine -> content_base, markdown_rendering, site_aware_models`) with its own `schema.py` registered into `SCHEMAS`, and its own loading hooks called from `content_save` (`content_engine -> form_engine`).
- Against: `content_save.py` and `validate.py` live in `content_engine`, so the loader would import the new app's models (`content_engine -> new app`), and the new app's widgets (course card) would read `content_engine.Course` (`new app -> content_engine`): that is a cycle unless the loader hook or the card widget goes through a seam. `form_engine` avoids this because it sits below `content_engine` in the graph.
- Widgets: `MARKDOWN_ALLOWED_TAGS` is a single global allowlist, so any new app's widgets are still allowed on Topics/Courses unless the render path is changed; the cotton namespace is also global.
- Settings/installer burden: each app adds `INSTALLED_APPS`, URL include, migrations, a Tailwind `@source` glob consideration (`tailwind.input.css` scans `./freedom_ls/**/templates/**/*.html`, which covers apps inside `freedom_ls/`), and `docs/app_structure.md` regeneration.

Neutral facts: `Topic` and `Activity` are near-identical concrete models (Activity: "Not currently used by FLS courses", `domain-glossary`), showing the project has already accepted parallel concrete content types differing by a couple of fields.

## 7. Vocabulary: is "article" taken?

- Read: `.claude/skills/domain-glossary/SKILL.md` (the project's domain-glossary skill; `claude_plugins/` has no copy, the SDD config `.claude/sdd/config.md` "Vocabulary Sources" points to it, then `freedom_ls/*/models.py`, `docs/product/`, `docs/app_structure.md`) and `claude_plugins/sdd/resources/domain_vocabulary.md` (process rules: look up the concept both ways, never reuse a taken word, say so at first use when coining, a spec only needs a Terminology section for coined or narrowed terms).
- **"article" is not listed in the glossary**, appears in no model/class/field/URL name under `freedom_ls/`, and appears nowhere in the code as a domain noun. Greps for `article|blog` over `freedom_ls`, `docs`, `config`, `demo_content` hit only: (a) HTML `<article>` elements in `learner_interface/templates/cotton/course-card-shell.html` and `course-row-shell.html` (card markup, not a concept), (b) `docs/how tos/landing-pages.md:38` (`og_type`: "`article` for something dated and authored", an Open Graph value), (c) a GDPR "Article 5(3)" reference in `docs/product/signup-attribution.md`, (d) the URLconf docstring example `blog.urls` in `config/urls.py`. Generic plugin docs (`claude_plugins/django-stack/...`) use `Article` as example model names only.
- No canonical term exists for "blog post", "blog" or "page". Relevant taken or nearby words from the glossary, to avoid colliding with:
  - `Topic` ("a page of markdown content a learner reads"), `Activity`, `Course`, `Form`: existing content-type nouns; a new content type is named alongside them (`ContentType` enum value in caps, e.g. `TOPIC`).
  - **item** (already ambiguous: `Course.items` rows vs `viewable_items()` children vs `content_item`), **collection** (only `ContentCollectionItem.collection`), **link** (taken as a noun for `<a href>`; fine as a verb), **slot** (cotton slots, accent slots), **course item** (taken).
- Implications from the glossary's own rule: "article" is available as a new word. The idea file also uses "article" for the widget ("link to another article") and "blog" for the feature; the glossary has no entry for either, so the spec would need to say it is coining them (the SDD rule: define once in terms of existing nouns; a `coined` term must have zero hits in the codebase, and `article` currently has none as a concept).
- Existing widget naming pattern: `c-<noun>` and `c-content-link` already exists for linking to a content item; the idea's "link to another article" widget would sit beside it.

## 8. Other observations worth carrying into the spec

- `Course.CONTENT_TYPE` for `CourseCategory` is the literal `"COURSE_CATEGORIES"` string (from before the enum member existed), and `CourseCategory` has no `content` markdown. A reminder that the registry/enum parity is only enforced by the one test above.
- `Topic.preview_url` and `c-content-link` are currently dangling (no `content_engine` URLs), so "link to another article" cannot be a straight reuse of `c-content-link` without fixing or replacing how it resolves a target to a URL.
- `BaseContentModel.image` exists in the pydantic schema but is not a column on `Topic`/`Course`, so frontmatter `image:` on those types fails at `save_with_uuid` ("Fields present in frontmatter but don't exist in Django model"). A blog normally wants a hero/cover image; there is no existing field or widget path for it besides `c-picture` in the body and `File` rows.
- No frontmatter fields exist for publish date, author, or draft state on any content model; `TimestampedModel` gives `created_at`/`updated_at` (load-time, not authored). `Course.visibility` (published/coming_soon/hidden) is the only publication-state vocabulary in the content models and is course-only.
- The "course cards, no pagination" widget needs a way to select courses from markdown attributes. Existing selectors for Course: `slug` (derived, site-unique), `file_path`, `uuid`, `categories` (slugs authored in `course_categories.yaml`, validated cross-file), tags. Allowed-attribute values are plain strings (nh3 only filters attribute names, not values).
- Anonymous rendering already happens for `course_detail` with `request=None`, so a public page that renders widgets without a user has a working precedent; there is no existing public (anonymous) surface rendering a standalone content item.

## Files read (principal)
`freedom_ls/content_base/{models,schema}.py`, `content_base/tests/test_schema_registry.py`; `freedom_ls/content_engine/{schema,validate,checks,config,admin}.py`, `models/{topics,courses,__init__}.py`, `management/commands/content_save.py`, `templatetags/content_tags.py`, `templates/cotton/{content-link,picture}.html`; `freedom_ls/markdown_rendering/{markdown_utils,config}.py`; `freedom_ls/site_aware_models/{models,slugs}.py`; `freedom_ls/course_access/visibility.py`; `freedom_ls/learner_interface/{urls,views}.py`, `templates/cotton/course-price.html`, `partials/course_card.html`; `config/{urls,sitemaps,settings_base}.py`; `docs/app_structure.md`, `docs/how tos/landing-pages.md`; `claude_plugins/fls-content/` (widget-reference, content-types skills, bundled validate/schema.py), `claude_plugins/fls-dev/{resources/markdown_content.md,commands/update_claude_plugin_fls_content.md}`; `.claude/skills/domain-glossary/SKILL.md`, `claude_plugins/sdd/resources/domain_vocabulary.md`, `.claude/sdd/config.md`.

status: ok
