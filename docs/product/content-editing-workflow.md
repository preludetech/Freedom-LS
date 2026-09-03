# Content Editing Workflow

_Last updated: 2026-09-03_

## Summary

- All course content is authored as plain Markdown and YAML under version control; git provides the full history — timestamps, diffs, and rollback.
- Content is loaded into the database by the `content_save` command, which validates first and then idempotently upserts each item by UUID. Re-running it is safe.
- Markdown renders through a four-stage pipeline: Markdown → sanitiser → content-widget compilation → template render.
- Course images are re-encoded to WebP at ingest, so authors can commit camera and screenshot output as-is; filenames and `c-picture` references keep working unchanged.
- Legal documents are versioned alongside content, and the exact version a user accepted is recorded on their consent record.
- There is **no browser-based content editor**. All authoring happens in files, and content cannot be deleted from the admin either.

## Authoring Model

Content lives as files on disk — Markdown for text-heavy items, YAML for structured data — committed to git alongside application code.

**UUIDs in frontmatter.** On the first run of `content_save`, a UUID is written back into each file's frontmatter. That UUID is the stable identifier for the item and survives edits, renames, and re-saves.

**No GUI editor.** There is no admin-side or browser-based authoring interface. This is by design: the file system is the source of truth and git is the audit trail. Content records cannot be deleted from the admin either — see [admin interface](./admin-interface.md#content-cannot-be-deleted).

**AI authoring.** Authors may use AI tools to draft or revise Markdown. This is a workflow affordance only — there is no AI integration in the application code.

**Draft content.** Any file or directory whose name begins with `_` or `.` is skipped by the content scanner and never loaded, at any nesting level — a whole `_drafts/` directory or a single `_topic.md`. The scanner also skips `README.md`, `CLAUDE.md`, and any file whose name ends with `~`. To publish a draft, rename it to remove the leading underscore and re-run `content_save`.

Because draft content is never loaded, it cannot be previewed in the running application. To load a course but keep it away from learners — to review it in the app before launch — set its visibility to `hidden` instead.

## Content Types

Eight content types are available:

| Type | Description |
|---|---|
| `COURSE` | Top-level course container; metadata and a list of items |
| `COURSE_PART` | Optional chapter/section grouping within a course |
| `TOPIC` | A page of Markdown content |
| `ACTIVITY` | A structured activity item |
| `FORM` | A multi-page form or quiz |
| `FORM_PAGE` | A single page within a form |
| `FORM_QUESTION` | A question within a form page |
| `FORM_CONTENT` | A non-question content block within a form page |

## Course Frontmatter Options

These are set in a course's YAML frontmatter and take effect when content is loaded. There is no admin or educator toggle for any of them — changing one means editing the file and re-running `content_save`.

**Access type.** A course is free unless it declares otherwise:

```yaml
access_config:
  access_type: application_gated
```

Which access types a deployment supports is determined by its access backend — see [configuration and extension](./configuration-and-extension.md). The learner-facing flow is in [learner experience](./learner-experience.md).

**Visibility.** `published` (the default when absent), `coming_soon`, or `hidden`:

```yaml
visibility: coming_soon
```

Visibility is a separate top-level field from `access_config`; the two are validated independently and compose freely, so an application-gated course can also be coming soon. See [learner experience](./learner-experience.md) for what each state means to a learner.

**In-development table of contents.** While a course is still being written, its detail page would otherwise show empty table-of-contents elements — a lesson count of zero, a heading with nothing under it. Setting `table_of_contents_in_development: true` suppresses those elements on that course's detail page, so the course can stay listed and demoable without looking broken. It changes nothing about listing, enrolment, or access.

Because a published course should always show its contents, `published` combined with `table_of_contents_in_development: true` is rejected at load time.

Other course metadata — learning outcomes, difficulty (`beginner`, `intermediate`, `advanced`, `all_levels`), estimated duration, description — is authored the same way.

## Validation and Loading

```
uv run python manage.py content_validate <path>
uv run python manage.py content_save <path> <site_name>
```

Validation parses every YAML and Markdown file against strict schemas before any database write. Schemas are strict-mode: any field not defined causes a clear, file-located error rather than being silently ignored, which prevents data corruption from typos or schema drift. Invalid access configuration, an unrecognised visibility value, and the invalid frontmatter combinations above are all caught here.

`content_save` runs validation internally on every run and writes only if it passes. It scans the path, then upserts every item in a single atomic transaction, keyed on the frontmatter UUID — so re-running against unchanged files has no visible effect.

A companion command, `danger_content_delete`, removes content. It is deliberately named to require considered invocation, and is the only route by which loaded content is deleted.

## Markdown Rendering Pipeline

Stored Markdown is rendered through four stages when a learner views a topic:

1. **Markdown → HTML**, with fenced code blocks, tables, task lists, and heading-level offsetting enabled. Indented code blocks are deliberately disabled.
2. **Sanitisation** against a strict allowlist, using a Rust-based, memory-safe sanitiser. Only permitted content-widget tags and their declared attributes survive.
3. **Content-widget compilation** — widget tags in the HTML are compiled to template syntax.
4. **Template render** in the request context.

## Content Widgets

These widgets are available inside Markdown content:

| Tag | Purpose |
|---|---|
| `c-youtube` | Embed a YouTube video by ID |
| `c-picture` | Responsive image with optional lightbox |
| `c-admonition` | Typed callout box (`type`, optional `title`) |
| `c-flashcard` | Two-sided flip card; front and back are supplied as named slots |
| `c-accordion` | Collapsible disclosure widget (`title`, optional `open`) |
| `c-card` | Content panel with optional header image, `title`, and `size` |
| `c-content-link` | Internal link to another content item |
| `c-pdf-embed` | Inline PDF viewer |
| `c-file-download` | Downloadable file link |
| `c-pull-quote` | Pull quote with optional attribution |
| `c-equation` | Rendered equation block |
| `c-image-grid` | Multi-column image grid |
| `c-table` | Accessible table wrapper |
| `c-code-block` | Syntax-highlighted code block |
| `c-slot` | Fills a named slot inside a widget that declares one (`name`) — this is how `c-flashcard`'s front and back are supplied |

Admonition types default to note, tip, important, warning, danger, key takeaways, and checklist, and are configurable per deployment — as is the widget list itself. See [configuration and extension](./configuration-and-extension.md).

## File Assets

Binary assets — images, PDFs, audio, video — are uploaded and stored by `content_save` alongside text content, and tracked against the content items that reference them.

**Obsidian image syntax.** `content_save` translates `![[image.jpg]]` and `![[image.jpg | title]]` into image widgets at save time, so authors can use standard Obsidian-compatible notation.

**Image optimisation.** Raster images — photographs, screenshots — are re-encoded to WebP when `content_save` loads them, and scaled down to 1600 px on the longest edge if they exceed it. Authors can commit camera and screenshot output as-is rather than pre-optimising or resizing it first. The file an author references keeps working unchanged, name and all, including any `<c-picture src="...">` in content; only the stored bytes and format change. SVGs and already-small images pass through untouched, and a corrupt or undecodable image is stored as-is with a warning naming it rather than failing the run.

## `fls-content` Authoring Plugin

`fls-content` is a Claude Code plugin for course authors working in a content repository without access to the FLS source. It provides:

- **Offline reference** — the content types and their frontmatter, the available widgets and their permitted attributes, file layout and numbering conventions, and UUID and escaping rules.
- **Markdown conversion** (`/fls-content:format-content`) — reformats messy Markdown into valid FLS structure in place. Conservative by design: lossless transforms are applied automatically, while anything semantic is collected for author review rather than applied silently. Git is the safety net; there is no separate backup or dry-run mode.
- **Offline validation** (`/fls-content:validate-content`) — runs a bundled Django-free copy of the schema validator, reporting the same errors as `content_validate` without needing a running FLS host. This is a structural pre-flight only; `content_save` on a host remains authoritative, since UUID assignment, icon resolution, cross-reference resolution, and asset upload happen there.
- **Repo scaffolding** (`/fls-content:init`) — creates a configuration file declaring the deployment's valid admonition types, so the plugin knows which are valid for that project. It never overwrites an existing config.

The plugin is kept in sync with FLS automatically whenever authoring-relevant FLS code changes.

## Compliance: Version Control and Legal Documents

**Audit trail.** Because all content lives in git, every change carries a commit timestamp, author, and diff, and rolling back is a standard git operation. There is no application-level versioning layer beyond what git provides.

**Legal documents.** Terms of service and privacy policy files are read from the git repository at HEAD, and their git blob hash identifies the exact version. For containerised deployments where a `.git` directory may not be present, a manifest recording each document's blob hash is generated at image-build time by the `build_legal_docs_manifest` command; where a deployment configures a manifest, that manifest — not git — is the source of truth.

When a user consents, the accepted document's hash is stored on their consent record, creating a durable, tamper-evident link between the version and the consent event. See [authentication](./authentication.md) for the full audit trail.
