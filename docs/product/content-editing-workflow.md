# Content Editing Workflow

_Last updated: 2026-06-18_

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

## Content Widgets (Cotton Components)

The following cotton components are available inside Markdown content:

| Tag | Purpose |
|---|---|
| `c-youtube` | Embed a YouTube video by ID |
| `c-picture` | Responsive image with optional lightbox |
| `c-admonition` | Typed callout box (`type`: note/tip/important/warning/danger/key_takeaways/checklist; optional `title`) |
| `c-flashcard` | Two-sided flip card with `front` and `back` named slots |
| `c-accordion` | Collapsible disclosure widget (`title`; optional `open` to start expanded) |
| `c-content-link` | Internal link to another content item |
| `c-pdf-embed` | Inline PDF viewer |
| `c-file-download` | Downloadable file link |
| `c-pull-quote` | Pull quote with optional attribution |
| `c-equation` | Rendered equation block |
| `c-image-grid` | Multi-column image grid |
| `c-table` | Accessible table wrapper |
| `c-code-block` | Syntax-highlighted code block |

Downstream projects can register additional cotton component tags by adding them to `MARKDOWN_ALLOWED_TAGS` in settings, making them available as markdown widgets in that project's content.

The available `type` values for `c-admonition` (built-in: `note`, `tip`, `important`, `warning`, `danger`, `key_takeaways`, `checklist`) are driven by the deploy-time `ADMONITION_TYPES` settings registry, which downstream projects can extend with domain-specific types; see [Configuration and Extension](./configuration-and-extension.md) for details.

## File Assets

Binary assets (images, PDFs, audio, video) are uploaded and stored via `content_save` alongside text content. The `File` model (`freedom_ls/content_engine/models.py`) tracks the association between files and content items.

**Obsidian image syntax.** `content_save` automatically translates `![[image.jpg]]` and `![[image.jpg | title]]` (Obsidian wiki-image syntax) to `<c-picture>` tags at save time, so content authors can use standard Obsidian-compatible notation.

## Compliance: Version Control and Legal Documents

**Version control audit trail.** Because all content lives in git, every change carries a commit timestamp, author, and diff. Rolling back to any previous state is a standard git operation. There is no application-level versioning layer beyond what git provides.

**Legal documents.** The terms of service and privacy policy files are read from the git repository at HEAD using git blob access. In containerised production environments where a `.git` directory may be absent, a pre-built manifest is generated at image-build time by `manage.py build_legal_docs_manifest`. The manifest records the git blob hash for each legal document.

When a user consents to a legal document, the `LegalConsent` record (see [authentication](./authentication.md)) stores the git hash of the document version the user accepted. This creates a durable, tamper-evident link between the accepted document version and the consent event. The full legal consent audit trail is described in [authentication](./authentication.md).
