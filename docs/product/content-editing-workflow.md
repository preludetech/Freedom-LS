# Content Editing Workflow

_Last updated: 2026-07-11_

## Summary

- All course content is authored as plain Markdown and YAML files under version control; the git repository provides a full history of every change with timestamps, diffs, and rollback.
- Content is loaded into the database via the `content_save` management command, which validates, then idempotently upserts each item by UUID — re-running the command is safe.
- Markdown is rendered through a pipeline: python-markdown → nh3 sanitiser (strict allowlist) → django-cotton component compilation → Django template render.
- Legal documents (terms, privacy policy) are read from the git repository at HEAD; the git blob hash is recorded on each user's consent record, giving a tamper-evident link between the document version and the consent event.
- There is no browser-based content editor; all authoring happens in files. AI tools may be used by authors to draft Markdown, but no AI integration exists in the application code.

## Authoring Model

Content lives as files on disk — Markdown (`.md`) for text-heavy items, YAML (`.yaml` / `.yml`) for structured data. All content files are committed to the git repository alongside application code.

**UUIDs in frontmatter.** On the first run of `content_save`, a UUID is written back into each file's frontmatter. This UUID is the stable identifier for that content item; it survives edits, renames, and re-saves.

**No GUI editor.** There is no admin-side or browser-based content authoring interface. Content editing requires direct file editing and running the CLI command. This is by design: the file system is the source of truth, and git provides the audit trail.

**AI authoring.** Authors may use AI tools (LLMs, etc.) to draft or revise Markdown. This is a workflow affordance only — there is no AI integration in the application code.

**Draft content.** Any file or directory whose name begins with `_` (or `.`) is skipped by the content scanner and never loaded into the database. This is how work-in-progress content is kept out of the running system: it lives in the repository, under version control, without ever appearing to learners, educators, or admins. The rule applies at any level — a whole `_drafts/` directory (and everything nested inside it) or a single `_topic.md` / `_lesson.yaml`. For completeness, the scanner also skips `README.md`, `CLAUDE.md`, and any file whose name ends with `~`. To publish a draft, rename it to remove the leading `_` and re-run `content_save`.

Because draft content is never loaded, it cannot be previewed in the running application. To load a course but keep it invisible to learners — for example, to review it in the app before launch — set its visibility to `hidden` instead (see [Course Visibility](#course-visibility) below).

## Content Types

The schema (`freedom_ls/content_engine/schema.py`) defines eight content types:

| Type | Description |
|---|---|
| `COURSE` | Top-level course container; holds metadata and a list of items |
| `COURSE_PART` | Optional chapter/section grouping within a course |
| `TOPIC` | A page of Markdown content |
| `ACTIVITY` | A structured activity item |
| `FORM` | A multi-page form or quiz |
| `FORM_PAGE` | A single page within a form |
| `FORM_QUESTION` | A question within a form page |
| `FORM_CONTENT` | Non-question content block within a form page |

## Course Access Type

A course's access type is configured through the content-loading pipeline, using the same frontmatter-and-`content_save` workflow as all other course properties. There is no admin or educator toggle in the current release.

To mark a course as application-gated, add an `access_config` block to its YAML frontmatter:

```yaml
access_config:
  access_type: application_gated
```

When `access_config` is absent the course behaves as a free course — the default. Invalid configuration (an unrecognised `access_type` value or an unknown key) is rejected at content-load time with a file-located error message, consistent with the rest of content validation.

Which access types a deployment supports, and how the active backend is selected, are described in [configuration and extension](./configuration-and-extension.md). The learner-facing experience for application-gated courses is described in [learner experience](./learner-experience.md).

## Course Visibility

A course's visibility — published, coming soon, or hidden — is configured through the same frontmatter-and-`content_save` workflow as every other course property. There is no admin or educator toggle; changing a course's visibility (e.g. flipping it from coming-soon to published at launch) means editing the frontmatter and re-running `content_save`.

To mark a course as coming soon or hidden, add a `visibility` key to its YAML frontmatter:

```yaml
visibility: coming_soon
```

Supported values are `published`, `coming_soon`, and `hidden`. When `visibility` is absent the course behaves as `published` — the default. Invalid configuration (an unrecognised `visibility` value) is rejected at content-load time with a file-located error message, consistent with the rest of content validation.

`visibility` is a separate, top-level course field from `access_config` — it is not part of the access-type mechanism described above, and the two are validated independently. A course's visibility (published / coming-soon / hidden) and its access type (free / application-gated) compose freely: for example, an application-gated course can be coming soon.

The learner-facing effect of each visibility state is described in [learner experience](./learner-experience.md). How visibility is enforced uniformly across access backends is described in [configuration and extension](./configuration-and-extension.md).

## Course Table of Contents (In-Development Courses)

While a course is still being built, its detail page can otherwise show empty, unfinished-looking table-of-contents elements — a lesson count of zero, a heading with nothing under it. To avoid this, an author can add a `table_of_contents_in_development` key to a course's YAML frontmatter and set it to `true`; this suppresses the table-of-contents elements on that course's detail page (the lesson-count stat, the lesson-count line in the "This course includes" summary, and the course-content listing) so the course can be kept listed and demoable while its lessons are still being written, without showing broken-looking placeholders. When `table_of_contents_in_development` is absent, the course behaves as `false` — the default, and today's behaviour.

This flag is independent of both course visibility and access type: it changes nothing about whether a course is listed, who can enrol, or what they can access — it only affects whether the table of contents renders. It is typically paired with a `coming_soon` visibility while a course is being authored (see [Course Visibility](#course-visibility) above), but the two are set and validated separately.

Because a published course should always show its contents, a course cannot be both `published` and marked `table_of_contents_in_development: true`; this combination is rejected at content-load time with a file-located error message, consistent with the rest of content validation.

The learner-facing effect of an in-development course's table of contents being hidden is described in [learner experience](./learner-experience.md).

## Validation

`content_validate` parses all YAML and Markdown files through Pydantic models before any database write. The Pydantic config is `extra="forbid"` (strict mode): any field not defined in the schema causes the validation to fail with a clear error message. This prevents silent data corruption from typos or schema drift.

`content_save` calls validation internally as part of every run; the database is only written if validation passes.

## Loading Content

```
uv run python manage.py content_save <path> <site_name>
```

The command scans the given path, validates all files, and upserts each item to the database in a single atomic transaction. The upsert key is the UUID in frontmatter. Re-running the command against unchanged files has no visible effect.

A companion command `danger_content_delete` removes content; it is intentionally named to require deliberate invocation.

## Markdown Rendering Pipeline

When a learner views a topic, the stored Markdown text is rendered through a four-stage pipeline:

1. **python-markdown** — converts Markdown to HTML; extensions: `fenced_code`, `mdx_headdown` (heading offset), `tables`.
2. **nh3 sanitiser** — cleans the HTML against a strict allowlist. nh3 is Rust-based and memory-safe. The allowlist is defined in `MARKDOWN_ALLOWED_TAGS` in settings and extended by the cotton component tags listed below.
3. **django-cotton compilation** — `<c-tag>` component invocations in the HTML are compiled to Django template syntax.
4. **Django template render** — the compiled template is rendered in the request context.

## `fls-content` Authoring-Assistant Plugin

The `fls-content` Claude Code plugin is an authoring tool for course content authors working in a content repository without access to the FLS source code. It is installed as a Claude Code plugin and provides four capabilities:

- **Offline reference** via built-in skills covering the eight content types and their frontmatter, the full set of available cotton widgets (`c-*`) with their permitted attributes, file-layout and numbering conventions, UUID rules, and HTML-escaping rules.
- **Markdown-to-FLS conversion** via `/fls-content:format-content <file-or-directory>`, which reformats messy Markdown (and existing YAML role files) into valid FLS content structure in place. Conservative by design: lossless transforms (e.g. local image syntax and YouTube URLs → the corresponding widget tags) are applied automatically; everything semantic (admonition proposals, flashcard candidates, etc.) is collected for author review in a `_conversion_review.md` file rather than applied silently. Git is the safety net — no separate backup or dry-run mode is provided.
- **Offline structural validation** via `/fls-content:validate-content [target]`, which runs a bundled Django-free copy of the FLS schema validator and reports the same required-field, unknown-field, and type errors that `content_validate` produces — without requiring a running FLS host. This is a structural pre-flight only; `content_save` on an FLS host remains the authoritative pass (UUID assignment, icon resolution, cross-reference resolution, and asset upload still happen there).
- **Repo scaffolding** via `/fls-content:init [target]`, which creates a `.fls-content.yaml` configuration file in the content repository when none exists. This file declares the deployment's valid admonition types so the plugin knows which `c-admonition type` values are valid for that project. The command is non-destructive: it never overwrites an existing config file. For admonition-type configuration details, see [Configuration and Extension](./configuration-and-extension.md).

The plugin is kept in sync with FLS automatically via an SDD workflow step that runs whenever authoring-relevant FLS code changes (widget allowlist, content schemas, conventions).

## Content Widgets (Cotton Components)

The following cotton components are available inside Markdown content:

| Tag | Purpose |
|---|---|
| `c-youtube` | Embed a YouTube video by ID |
| `c-picture` | Responsive image with optional lightbox |
| `c-admonition` | Typed callout box (`type`: note/tip/important/warning/danger/key_takeaways/checklist; optional `title`) |
| `c-flashcard` | Two-sided flip card with `front` and `back` named slots |
| `c-accordion` | Collapsible disclosure widget (`title`; optional `open` to start expanded) |
| `c-card` | Self-contained content panel with an optional header image (`src`, `alt`), optional `title`, and a Markdown body. `size`: `small` \| `medium` \| `large` (default `medium`). Registered in `MARKDOWN_ALLOWED_TAGS`. |
| `c-content-link` | Internal link to another content item |
| `c-pdf-embed` | Inline PDF viewer |
| `c-file-download` | Downloadable file link |
| `c-pull-quote` | Pull quote with optional attribution |
| `c-equation` | Rendered equation block |
| `c-image-grid` | Multi-column image grid |
| `c-table` | Accessible table wrapper |
| `c-code-block` | Syntax-highlighted code block |

Downstream projects can register additional cotton component tags by adding them to `MARKDOWN_ALLOWED_TAGS` in settings, making them available as markdown widgets in that project's content.

The admonition box types available to authors are configurable per deployment and can be extended by downstream projects; see [Configuration and Extension](./configuration-and-extension.md).

## File Assets

Binary assets (images, PDFs, audio, video) are uploaded and stored via `content_save` alongside text content. The `File` model (`freedom_ls/content_engine/models.py`) tracks the association between files and content items.

**Obsidian image syntax.** `content_save` automatically translates `![[image.jpg]]` and `![[image.jpg | title]]` (Obsidian wiki-image syntax) to `<c-picture>` tags at save time, so content authors can use standard Obsidian-compatible notation.

## Compliance: Version Control and Legal Documents

**Version control audit trail.** Because all content lives in git, every change carries a commit timestamp, author, and diff. Rolling back to any previous state is a standard git operation. There is no application-level versioning layer beyond what git provides.

**Legal documents.** The terms of service and privacy policy files are read from the git repository at HEAD using git blob access. In containerised production environments where a `.git` directory may be absent, a pre-built manifest is generated at image-build time by `manage.py build_legal_docs_manifest`. The manifest records the git blob hash for each legal document.

When a user consents to a legal document, the `LegalConsent` record (see [authentication](./authentication.md)) stores the git hash of the document version the user accepted. This creates a durable, tamper-evident link between the accepted document version and the consent event. The full legal consent audit trail is described in [authentication](./authentication.md).
