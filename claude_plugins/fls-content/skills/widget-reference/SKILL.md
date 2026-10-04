---
name: widget-reference
description: FLS c-* widgets, built-in and any custom widgets the content repo declares — purpose, attributes, and examples. Use when asking about a widget, custom widget, component, admonition, flashcard, accordion, youtube, picture, table, code block, card, article link, article card, course card, grid, pull quote, or equation.
allowed-tools: Read, Grep, Glob
---

# FLS Widget Reference

Widgets are `c-*` cotton components embedded in markdown content bodies. They must be registered in `MARKDOWN_ALLOWED_TAGS` or the nh3 sanitiser strips them wholesale before the template ever renders. Authors cannot invent `c-*` names. The valid set is the built-ins below plus the custom widgets the content repo declares (see [`resources/custom-widgets.md`](resources/custom-widgets.md)). Any unknown `c-*` tag is stripped silently, so it produces no error and no output.

## All widgets at a glance

| Widget | Use when… |
|---|---|
| `c-youtube` | Embedding a YouTube video |
| `c-picture` | Showing an image with accessible alt text and optional caption/lightbox |
| `c-grid` | Laying out any children (pictures, article cards, course cards) in columns |
| `c-image-grid` | Older name for `c-grid`, kept for existing content; use `c-grid` in new content |
| `c-pdf-embed` | Displaying a PDF inline |
| `c-file-download` | Providing a file download button |
| `c-admonition` | Callout boxes — notes, tips, warnings, checklists, etc. |
| `c-flashcard` | Two-sided recall card (question/answer flip) |
| `c-accordion` | Collapsible disclosure section |
| `c-card` | Static content card with optional header image |
| `c-table` | Accessible scrollable table wrapper |
| `c-code-block` | Preformatted code or log output with optional title/language label |
| `c-pull-quote` | Pull quote with optional attribution |
| `c-equation` | Client-side KaTeX equation |
| `c-content-link` | Internal link to another content item |
| `c-article-link` | Inline link to a published ARTICLE |
| `c-article-card` | Clickable card for a published ARTICLE |
| `c-course-card` | Clickable card for a COURSE |
| `c-slot` | Named slot inside `c-flashcard` (not a standalone widget) |

## Authorised attribute sets (built-in widgets)

This block lists the built-in widgets only. A declared custom widget's attribute set is the `**Allowed attributes:**` line of its declaration. For each widget, the documented attribute set equals the `MARKDOWN_ALLOWED_TAGS` allowlist exactly. Any attribute outside the set is **silently stripped** by the sanitiser before the template renders.

```
c-youtube:        video_id, video_title, caption
c-picture:        src, alt, title, description, number
c-content-link:   path
c-article-link:   path
c-article-card:   path, variant
c-course-card:    path, variant
c-pdf-embed:      src, caption, height
c-file-download:  src, text
c-pull-quote:     attribution, cite, source
c-equation:       label
c-grid:           columns
c-image-grid:     columns
c-table:          caption
c-code-block:     title, language, wrap
c-admonition:     type, title
c-flashcard:      size
c-accordion:      title, open
c-card:           src, alt, title, size
c-slot:           name
```

## Admonition types are deployment-configurable

`c-admonition`'s `type` attribute is **not a fixed list** in the plugin. The valid set for your project is declared in `.fls-content.yaml` at the repo root, which always exists (created by `/fls-content:init`). The base set shipped with FLS is:

`note`, `tip`, `important`, `warning`, `danger`, `key_takeaways`, `checklist`, `default`

But this base set is fully overridable — a deployment may add, remove, or rename these types. **Do not treat the base set as exhaustive.** An unknown type falls back **silently** to the `default` style at render time with no error, so you must rely on the types declared in your project's `.fls-content.yaml`, not guess.

## Custom widgets are declared per content repo

A concrete project may declare widgets of its own in `.claude/fls-content/widgets/`. Follow the read step in [`resources/custom-widgets.md`](resources/custom-widgets.md) before answering about or writing any widget, and treat declared widgets as valid alongside the built-ins.

## HTML-escaping rule (critical for two widgets)

`c-code-block` and `c-equation` bodies are **not** markdown-processed — the content passes as raw text through the sanitiser. You must escape:

- `<` → `&lt;`
- `>` → `&gt;`
- `&` → `&amp;`
- `"` → `&quot;` (code-block only)

All other widget bodies use standard markdown; escaping is automatic.

## Authoring quirks (one-liners)

- **`c-image-grid` children must use the closed form** `<c-picture ...></c-picture>` — never self-closing `/>`. Leave a blank line between each child for block parsing.
- **`c-grid` takes any children** — put a blank line between each child, and use the closed form for `c-picture` children, as for `c-image-grid`.
- **`c-article-link`, `c-article-card`, `c-course-card` `path`** — a path relative to the file holding the widget, ending in the target file name (e.g. `path="undated-notes.md"`, `path="../other_course/course.md"`). `content_validate` fails the run if no content file is at that path, or if the target is the wrong type (ARTICLE for the article widgets, COURSE for `c-course-card`). Write `path="..."` in double quotes.
- **`c-flashcard` slots need blank lines** inside `<c-slot>` tags so the markdown parser produces block elements (paragraphs, lists).
- **`c-accordion` bare `open` attribute** — write `open` with no value; the sanitiser normalises it to `open=""` and the template handles it.

See `resources/` for full syntax, all attributes, and copy-pasteable examples —
one file per widget:

- [`resources/c-youtube.md`](resources/c-youtube.md)
- [`resources/c-picture.md`](resources/c-picture.md)
- [`resources/c-grid.md`](resources/c-grid.md)
- [`resources/c-image-grid.md`](resources/c-image-grid.md)
- [`resources/c-pdf-embed.md`](resources/c-pdf-embed.md)
- [`resources/c-file-download.md`](resources/c-file-download.md)
- [`resources/c-admonition.md`](resources/c-admonition.md)
- [`resources/c-flashcard.md`](resources/c-flashcard.md)
- [`resources/c-slot.md`](resources/c-slot.md)
- [`resources/c-accordion.md`](resources/c-accordion.md)
- [`resources/c-card.md`](resources/c-card.md)
- [`resources/c-table.md`](resources/c-table.md)
- [`resources/c-code-block.md`](resources/c-code-block.md)
- [`resources/c-pull-quote.md`](resources/c-pull-quote.md)
- [`resources/c-equation.md`](resources/c-equation.md)
- [`resources/c-content-link.md`](resources/c-content-link.md)
- [`resources/c-article-link.md`](resources/c-article-link.md)
- [`resources/c-article-card.md`](resources/c-article-card.md)
- [`resources/c-course-card.md`](resources/c-course-card.md)
- [`resources/custom-widgets.md`](resources/custom-widgets.md)

HTML-escaping rule detail: see the `fls-content:conventions` skill.
