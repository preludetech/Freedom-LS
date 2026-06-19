# FLS Course-Authoring File Format — Authoritative Reference

_Source of truth for the course-editing-plugin. All facts derived from code; file paths cited._

---

## 1. Content Types

Defined in `freedom_ls/content_engine/schema.py` via the `ContentType` StrEnum (lines 13–23).

The eight types and their Pydantic models:

| `ContentType` value | Pydantic class | File format |
|---|---|---|
| `COURSE` | `Course` | `.md` (frontmatter + optional body) |
| `COURSE_PART` | `CoursePart` | `.yaml` (named `part.yaml`) |
| `TOPIC` | `Topic` | `.md` (frontmatter + markdown body) |
| `ACTIVITY` | `Activity` | `.md` (frontmatter + markdown body) |
| `FORM` | `Form` | `.md` (named `form.md`; optional body) |
| `FORM_PAGE` | `FormPage` | `.yaml` (first `---` section of a page yaml) |
| `FORM_QUESTION` | `FormQuestion` | `.yaml` (subsequent sections of a page yaml) |
| `FORM_CONTENT` | `FormContent` | `.yaml` (subsequent sections of a page yaml) |

All Pydantic models use `ConfigDict(extra="forbid")` — any unknown frontmatter key causes validation to fail (`freedom_ls/content_engine/schema.py` line 52).

### 1.1 Base fields common to most types

Defined on `BaseBaseContentModel` (`schema.py` lines 51–68):

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `ContentType` | Yes | Must be one of the eight values above |
| `uuid` | `str \| None` | No | Written by `content_save` on first run; must never be hand-created |
| `file_path` | `Path` | Internal | Injected by the validator; not authored |
| `meta` | `dict[str, Any] \| None` | No | Arbitrary key-value metadata |
| `tags` | `list[str] \| None` | No | Optional tag list |

Most types also inherit `BaseContentModel` (`schema.py` lines 70–79):

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | `str` | Yes | Display title |
| `subtitle` | `str \| None` | No | Optional subtitle |
| `description` | `str \| None` | No | Optional description |
| `category` | `str \| None` | No | Optional category |
| `image` | `str \| None` | No | Optional image path |

Types that carry markdown body content also inherit `MarkdownContentModel`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `content` | `str \| None` | No | The markdown body text |

### 1.2 COURSE

File: `course.md` in the course root directory. Example: `demo_content/functionality_demo_standard_markdown/course.md`.

Inherits: `BaseContentModel` + optionally `content` (has its own `content` field).

Additional fields (`schema.py` lines 106–168):

| Field | Type | Required | Notes |
|---|---|---|---|
| `children` | `list[Child]` | No (default `[]`) | Explicit ordered list of child paths; if omitted, all items in the directory are auto-discovered alphabetically |
| `content` | `str \| None` | No | Optional markdown intro body |
| `icon` | `str \| None` | No | Semantic icon name (e.g. `"notes"`) or literal glyph; see icon validation |
| `icon_fallback` | `str \| None` | No | Explicit `"<iconset>:<glyph>"` (e.g. `"phosphor:drone"`); only valid when `icon` is also set |
| `learning_outcomes` | `list[str]` | No (default `[]`) | "What you'll learn" bullet list |
| `difficulty` | `DifficultyLevel \| None` | No | `beginner`, `intermediate`, `advanced`, or `all_levels` |
| `estimated_duration` | `timedelta \| None` | No | e.g. `"1:30:00"` (HH:MM:SS) |

The `Child` model (`schema.py` lines 95–103):

| Field | Type | Required |
|---|---|---|
| `path` | `Path` | Yes |
| `overrides` | `dict[str, Any] \| None` | No |

Icon validation rules (`freedom_ls/content_engine/icon_validation.py`):
- Both `icon` and `icon_fallback` empty: OK (defaults to `"course"` semantic icon).
- `icon_fallback` set without `icon`: error.
- `icon` must be a semantic name from `SEMANTIC_ICON_NAMES` or a literal glyph present in at least one registered icon set.
- `icon_fallback` must match `<set>:<glyph>` (lowercase letters, digits, underscores, hyphens).

Full example (`demo_content/functionality_demo_standard_markdown/course.md`):

```yaml
---
content_type: COURSE
description: This will show how all the Standard Markdown goodies show up.
difficulty: beginner
estimated_duration: "1:30:00"
icon: notes
learning_outcomes:
  - Understand how the markdown content system renders
  - Recognise every built-in content widget
  - Author a course with confidence
subtitle: A standard tour of the content system
title: Standard Markdown - Demo Finance
uuid: 7e724756-a349-4ef1-924b-ec9c26dcba45
---

Your competitive advantage is your ability to learn.
```

### 1.3 COURSE_PART

File: `part.yaml` in a numbered subdirectory of the course.

Inherits: `BaseContentModel`.

Additional fields (`schema.py` lines 171–183):

| Field | Type | Required | Notes |
|---|---|---|---|
| `children` | `list[Child]` | No (default `[]`) | Explicit ordering; if omitted, directory is auto-scanned |

No `content` field (the commented-out line 183 in `schema.py` confirms this was intentionally removed).

Example (`demo_content/functionality_demo_course_parts/01. Getting Started/part.yaml`):

```yaml
---
content_type: COURSE_PART
title: Getting Started
uuid: 66bb8510-ce90-426e-82fb-f02b7ca92fdc
```

Note: `part.yaml` uses no closing `---`; the file terminates after the last field.

### 1.4 TOPIC

File: any numbered `.md` file (e.g. `01. welcome.md`).

Inherits: `BaseContentModel` + `MarkdownContentModel`.

No additional fields beyond the base. `content` is the full markdown body (everything after the frontmatter `---`).

Example (`demo_content/functionality_demo_course_parts/01. Getting Started/01. welcome.md`):

```yaml
---
content_type: TOPIC
title: Welcome
uuid: ...
---

Markdown body here...
```

### 1.5 ACTIVITY

File: any `.md` file.

Inherits: `BaseContentModel` + `MarkdownContentModel`.

Additional fields (`schema.py` lines 89–93):

| Field | Type | Required | Notes |
|---|---|---|---|
| `level` | `int \| None` | No | Difficulty level; 1 = easiest |

### 1.6 FORM

File: `form.md` inside a numbered subdirectory (the form directory).

Inherits: `BaseContentModel` + `MarkdownContentModel`.

Additional fields (`schema.py` lines 186–231):

| Field | Type | Required | Notes |
|---|---|---|---|
| `strategy` | `FormStrategy` | Yes | `QUIZ` or `CATEGORY_VALUE_SUM` |
| `quiz_show_incorrect` | `bool \| None` | Conditional | Required when `strategy=QUIZ`; must be absent otherwise |
| `quiz_pass_percentage` | `int \| None` | Conditional | Required when `strategy=QUIZ` (0–100); must be absent otherwise |
| `submit_on_exit` | `bool` | No (default `False`) | If `True`, navigating away finalises a partial attempt |

The model validator enforces the `strategy`/`quiz_*` consistency rules at validation time.

Example — QUIZ form (`demo_content/functionality_demo_end_with_quiz/3. quiz/form.md`):

```yaml
---
content_type: FORM
strategy: QUIZ
title: Mid course Quiz
uuid: 9d27cbca-7111-4571-8389-3399645f73d5
quiz_show_incorrect: true
quiz_pass_percentage: 80
submit_on_exit: true
---
```

Example — survey form (`demo_content/functionality_demo_end_with_topic/4. survey/form.md`):

```yaml
---
content_type: FORM
strategy: CATEGORY_VALUE_SUM
title: Course Feedback Survey
uuid: 7ed91f7d-b55b-4246-99a4-11f42bdb3ace
---
```

### 1.7 FORM_PAGE

File: the **first** `---`-delimited YAML section of a page yaml file (e.g. `1. page.yaml`).

Inherits: `BaseContentModel`.

No additional fields beyond the base.

Example (first section of `demo_content/functionality_demo_end_with_topic/4. survey/1. page.yaml`):

```yaml
---
content_type: FORM_PAGE
description: Tell us what you thought of this course.
title: Feedback
uuid: 85f82ad9-67ff-4558-b3c6-d735e72207f2
```

### 1.8 FORM_QUESTION

The second and subsequent YAML sections in a page yaml file that contain a `question` field.

Inherits: `BaseBaseContentModel` (NOT `BaseContentModel` — has no `title`, `subtitle`, etc.).

Fields (`schema.py` lines 262–295):

| Field | Type | Required | Notes |
|---|---|---|---|
| `content_type` | `ContentType` | Auto-inferred | `FORM_QUESTION` (derived by `derive_content_type` if not explicit) |
| `question` | `str` | Yes | The question text |
| `type` | `QuestionType` | Yes | `multiple_choice`, `checkboxes`, `short_text`, `long_text` |
| `required` | `bool` | No (default `True`) | Whether the question must be answered |
| `category` | `str \| None` | No | Category (used by `CATEGORY_VALUE_SUM` scoring) |
| `options` | `list[QuestionOption] \| None` | Conditional | Required for `multiple_choice` and `checkboxes` |
| `uuid` | `str \| None` | No | Written by `content_save` |
| `meta` | `dict[str, Any] \| None` | No | Optional metadata |
| `tags` | `list[str] \| None` | No | Optional tags |

`QuestionOption` fields (`schema.py` lines 244–256):

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | `str` | Yes | Display text |
| `value` | `int \| str` | Yes | The stored value (converted to string on save) |
| `uuid` | `str \| None` | No | Written by `content_save` |
| `correct` | `bool \| None` | No | For QUIZ strategy — marks the correct option |

### 1.9 FORM_CONTENT

The second and subsequent YAML sections in a page yaml file that contain a `content` field instead of a `question` field.

Inherits: `BaseBaseContentModel` (no `title` etc.).

Fields (`schema.py` lines 258–260):

| Field | Type | Required |
|---|---|---|
| `content` | `str` | Yes |
| `uuid` | `str \| None` | No |

**How the parser determines FORM_QUESTION vs FORM_CONTENT:** The first section's model (`FormPage`) implements `derive_content_type(data)`: if the section has a `content` key → `FORM_CONTENT`; if it has a `question` key → `FORM_QUESTION` (`schema.py` lines 237–242, `validate.py` lines 187–190).

---

## 2. File and Folder Layout

### 2.1 Numbering convention

All items (topics, parts, form pages, forms) that need ordering use a `NN. name` prefix where `NN` is a zero-padded or unpadded integer. The ordering is alphabetical on the full filename. Examples:

```
01. Getting Started/
02. Core Concepts/
03. Wrapping Up/

01. welcome.md
02. what-to-expect.md

1. page.yaml
2. another page.yaml
```

The sort is strict alphabetical (Python `sorted()` / filesystem iteration), so `1. page.yaml` < `2. another page.yaml` < `10. last page.yaml` only if zero-padded consistently. Demo content uses both `01.` and `1.` styles — use zero-padded for correctness with more than 9 items.

### 2.2 Course root directory

A course lives in a directory containing a `course.md` file. Everything else in the directory (and its subdirectories) is auto-discovered as course content unless excluded.

```
my-course/
  course.md              ← COURSE frontmatter + optional intro body
  images/                ← image files (uploaded to DB by content_save)
  01. intro.md           ← TOPIC
  02. concepts.md        ← TOPIC
  03. quiz/              ← FORM directory (numbered subdirectory)
      form.md            ← FORM frontmatter
      1. page.yaml       ← FORM_PAGE (section 1) + questions/content (sections 2+)
      2. results.yaml    ← FORM_PAGE + questions
  sample.pdf             ← file asset (uploaded to DB)
```

Files and directories whose names start with `_` or `.` are skipped by the scanner (`validate.py` lines 43–59). `README.md` and `CLAUDE.md` are always skipped.

### 2.3 Course with COURSE_PARTs

```
my-course/
  course.md
  01. Getting Started/      ← COURSE_PART directory (numbered)
      part.yaml             ← COURSE_PART frontmatter (no closing ---)
      01. welcome.md        ← TOPIC
      02. what-to-expect.md ← TOPIC
  02. Core Concepts/
      part.yaml
      01. key-ideas.md
      02. going-deeper.md
      03. knowledge-check/  ← FORM directory nested inside a PART
          form.md
          1. page.yaml
```

A `part.yaml` file is what identifies a directory as a COURSE_PART.

### 2.4 Form directory

A form is a directory containing exactly one `form.md` and one or more `NN. page.yaml` files.

```
03. quiz/
  form.md       ← FORM (has strategy, quiz_* fields)
  1. page.yaml  ← FORM_PAGE (first section) + questions/content (subsequent sections)
  2. another page.yaml
```

**Page ordering:** Pages are sorted alphabetically by filename at save time (`content_save.py` lines 576–578). Name them with leading numbers to control order.

**Within a page YAML file:** The first `---`-delimited section is the `FORM_PAGE`. Subsequent sections alternate freely between `FORM_QUESTION` and `FORM_CONTENT` blocks in the order they appear — this ordering is preserved in the DB.

### 2.5 images/ directory

Images and other binary assets (PDFs, etc.) sit alongside content files, conventionally in an `images/` subdirectory. `content_save` uploads all non-yaml/md files to the `File` model in the DB.

Paths in `c-picture`, `c-pdf-embed`, and `c-file-download` are relative to the content file that references them. However, `content_save` resolves them via the `get_file_by_path` template filter using the DB path. The path stored in the DB is relative to the course root passed to `content_save`.

Images in form page content can reference parent directories: `src="../images/graph1.drawio.svg"` (seen in `demo_content/functionality_demo_end_with_quiz/3. quiz/1. page.yaml` line 26).

### 2.6 Files excluded from scanning

`validate.py` `get_all_files()` (lines 21–74) skips:
- Files/directories starting with `_` or `.`
- Files named `README.md` or `CLAUDE.md`
- Files whose name ends with `~`

### 2.7 Child auto-discovery logic

When a COURSE or COURSE_PART has no explicit `children` list, `content_save` auto-discovers children by iterating the directory alphabetically (`content_save.py` lines 618–651):
- `.md`/`.yaml`/`.yml` files (excluding the collection's own file) become direct children.
- Subdirectories are scanned for a primary content file (first file that parses as FORM, COURSE, or COURSE_PART); that file becomes the child reference.

---

## 3. Widget (Cotton Component) Catalog

Cotton components are available inside markdown content bodies. All `c-*` tags must be registered in `MARKDOWN_ALLOWED_TAGS` (see §5) or they are stripped by the nh3 sanitiser before django-cotton ever sees them.

Templates live in `freedom_ls/content_engine/templates/cotton/`.

### 3.1 `c-youtube`

**Template:** `freedom_ls/content_engine/templates/cotton/youtube.html`

Embeds a YouTube video iframe.

| Attribute | Required | Notes |
|---|---|---|
| `video_id` | Yes | The `v=...` part of the YouTube URL |
| `video_title` | No (default: `"YouTube video player"`) | Accessible title for the iframe |
| `caption` | No (default: `""`) | Text caption shown beneath the player |

```markdown
<c-youtube video_id="01MXBvMeFCw" caption="A short description."></c-youtube>
```

### 3.2 `c-picture`

**Template:** `freedom_ls/content_engine/templates/cotton/picture.html`

Responsive image with keyboard-accessible lightbox (spotlight modal).

| Attribute | Required | Notes |
|---|---|---|
| `src` | Yes | File path (looked up via `get_file_by_path` from the DB) |
| `alt` | Yes | Alt text for screen readers; use `alt=""` for decorative images |
| `title` | No (default: `""`) | Visible caption under thumbnail and lightbox heading |
| `description` | No (default: `""`) | Longer description shown only in lightbox; not shown on page |
| `number` | No (default: `""`) | Figure number; prefixes title with "Figure N" |

```markdown
<c-picture src="images/landscape.svg" alt="Blue sky" title="A titled figure" number="1"></c-picture>
```

**Do not duplicate `alt` and `title`.** `alt` is for screen-reader users who cannot see the image; `title` is visible text for all users.

### 3.3 `c-admonition`

**Template:** `freedom_ls/content_engine/templates/cotton/admonition.html`

Typed callout box. Body is markdown-rendered.

| Attribute | Required | Notes |
|---|---|---|
| `type` | No (default: `"default"`) | One of the `ADMONITION_TYPES` keys; unknown types fall back to `"default"` silently |
| `title` | No (default: `""`) | Overrides the default label for the type |

```markdown
<c-admonition type="warning" title="Custom label">
Watch out for this.
</c-admonition>
```

**`ADMONITION_TYPES`** is defined in `config/settings_base.py` lines 305–314:

```python
ADMONITION_TYPES = {
    "note":          {"label": "Note",          "icon": "info",    "color": "info"},
    "tip":           {"label": "Tip",           "icon": "star",    "color": "success"},
    "important":     {"label": "Important",     "icon": "warning", "color": "warning"},
    "warning":       {"label": "Warning",       "icon": "warning", "color": "warning"},
    "danger":        {"label": "Danger",        "icon": "error",   "color": "error"},
    "key_takeaways": {"label": "Key Takeaways", "icon": "notes",   "color": "info"},
    "checklist":     {"label": "Checklist",     "icon": "check",   "color": "success"},
    "default":       {"label": "Note",          "icon": "info",    "color": "info"},
}
```

The `checklist` type body uses `- [ ]` markdown task list syntax — rendered as read-only disabled checkboxes.

Downstream projects can extend `ADMONITION_TYPES` in their own settings by merging the dict (pattern shown in `config/settings_dev.py` lines 8–16 which adds a `"regulation"` type).

### 3.4 `c-flashcard`

**Template:** `freedom_ls/content_engine/templates/cotton/flashcard.html`

Two-sided flip card. Both slots are markdown-rendered.

| Attribute | Required | Notes |
|---|---|---|
| _(none)_ | — | No attributes; content is entirely in named slots |

Named slots:

| Slot | Purpose |
|---|---|
| `front` | Prompt / question face |
| `back` | Answer / reveal face |

```markdown
<c-flashcard>
<c-slot name="front">

**What is the question?**

</c-slot>
<c-slot name="back">

This is the answer.

</c-slot>
</c-flashcard>
```

Blank lines inside slot tags are important — they allow the markdown parser to treat the content as block-level elements (paragraphs, lists, etc.).

### 3.5 `c-accordion`

**Template:** `freedom_ls/content_engine/templates/cotton/accordion.html`

Native `<details>`/`<summary>` collapsible disclosure widget. Body is markdown-rendered.

| Attribute | Required | Notes |
|---|---|---|
| `title` | No (default: `""`) | Visible summary bar text (required in practice) |
| `open` | No | When present (any value, including empty), accordion starts expanded |

```markdown
<c-accordion title="Why does Python use indentation?">
Body content here.
</c-accordion>

<c-accordion title="Open by default" open>
Starts expanded.
</c-accordion>
```

The nh3 sanitiser collapses a bare `open` attribute to `open=""`. The template distinguishes "present" from "absent" using a sentinel value `"__unset__"` (`accordion.html` line 1).

### 3.6 `c-image-grid`

**Template:** `freedom_ls/content_engine/templates/cotton/image-grid.html`

Layout wrapper for multiple `c-picture` children. Tiles into columns; collapses to single column on narrow screens.

| Attribute | Required | Notes |
|---|---|---|
| `columns` | No (default: `"3"`) | `"2"`, `"3"`, or `"4"`; any other value falls back to 3 |

**Critical authoring quirks** (documented in `demo_content/functionality_demo_content_widgets/2. media.md` line 44, and in `image-grid.html` comments):
1. Always use the **closed form** `<c-picture ...></c-picture>` inside a grid — never the self-closing `/>` form.
2. Leave a **blank line between each child** so the markdown parser treats them as separate block elements.
3. The grid uses `{{ slot }}` (not `{% markdown slot %}`) to avoid re-sanitising the already-compiled picture markup.

```markdown
<c-image-grid columns="2">

<c-picture src="images/a.svg" alt="Image A" title="A"></c-picture>

<c-picture src="images/b.svg" alt="Image B" title="B"></c-picture>

</c-image-grid>
```

### 3.7 `c-pull-quote`

**Template:** `freedom_ls/content_engine/templates/cotton/pull-quote.html`

Pull quote with optional attribution. Body is markdown-rendered.

| Attribute | Required | Notes |
|---|---|---|
| `attribution` | No (default: `""`) | Who said it (plain text) |
| `source` | No (default: `""`) | Work title (rendered in `<cite>`) |
| `cite` | No (default: `""`) | URL linking back to the source; unsafe schemes stripped by `safe_url` filter |

```markdown
<c-pull-quote attribution="Ada Lovelace" source="Notes on the Analytical Engine" cite="https://example.com">
The quote body here.
</c-pull-quote>
```

### 3.8 `c-equation`

**Template:** `freedom_ls/content_engine/templates/cotton/equation.html`

Client-side KaTeX typesetting. Slot content is delivered as plain text to the Alpine component.

| Attribute | Required | Notes |
|---|---|---|
| `label` | No (default: `""`) | Reference number/label (e.g. `"1"`); shown to the side as `(1)` |

**Important authoring note:** Because the slot content passes through nh3 before KaTeX, authors must HTML-escape `<`, `>`, and `&` as `&lt;`, `&gt;`, and `&amp;`. On malformed LaTeX, KaTeX falls back to showing the raw source.

```markdown
<c-equation label="1">E = mc^2</c-equation>

<c-equation>\sum_{i=1}^{n} i = \frac{n(n+1)}{2} \quad \text{for all } n \in \mathbb{N}</c-equation>
```

### 3.9 `c-table`

**Template:** `freedom_ls/content_engine/templates/cotton/table.html`

Accessible, horizontally scrollable table wrapper.

| Attribute | Required | Notes |
|---|---|---|
| `caption` | No (default: `""`) | Accessible caption; also names the scroll region for screen readers |

The slot content is markdown-rendered (GFM table syntax supported). Leave a blank line above and below the table inside the tag.

```markdown
<c-table caption="Plan comparison">

| Plan | Price |
|------|-------|
| Free | 0     |

</c-table>
```

Raw HTML tables with explicit `scope` attributes are also supported inside the slot.

### 3.10 `c-code-block`

**Template:** `freedom_ls/content_engine/templates/cotton/code-block.html`

Preformatted code/log block. No syntax highlighting, no copy button.

| Attribute | Required | Notes |
|---|---|---|
| `title` | No (default: `""`) | Chrome label (e.g. filename) |
| `language` | No (default: `""`) | Display-only language tag (e.g. `"bash"`) |
| `wrap` | No (default: `""`) | Any value enables line-wrapping instead of horizontal scroll |

**Important:** The slot content is raw preformatted text — not markdown-processed. Authors must escape `<`, `>`, `&`, and `"` as `&lt;`, `&gt;`, `&amp;`, `&quot;` so the sanitiser leaves them intact.

```markdown
<c-code-block title="deploy.sh" language="bash">echo "Deploying..."
if [ &quot;$count&quot; -gt 5 ]; then
    echo "More than five"
fi</c-code-block>
```

### 3.11 `c-pdf-embed`

**Template:** `freedom_ls/content_engine/templates/cotton/pdf-embed.html`

Inline PDF viewer via `<iframe>`.

| Attribute | Required | Notes |
|---|---|---|
| `src` | Yes | File path (looked up in DB via `get_file_by_path`) |
| `caption` | No (default: `""`) | Caption text beneath the viewer |
| `height` | No (default: `"600px"`) | CSS height of the iframe |

```markdown
<c-pdf-embed src="sample.pdf" caption="Sample Document" height="800px"></c-pdf-embed>
```

### 3.12 `c-file-download`

**Template:** `freedom_ls/content_engine/templates/cotton/file-download.html`

Download button (does not display the file inline).

| Attribute | Required | Notes |
|---|---|---|
| `src` | Yes | File path (looked up in DB) |
| `text` | No (default: `"Download file"`) | Button label |

```markdown
<c-file-download src="sample.pdf" text="Get the PDF"></c-file-download>
```

### 3.13 `c-content-link`

**Template:** `freedom_ls/content_engine/templates/cotton/content-link.html`

Internal link to another content item (Topic or Form). The link text is the slot content.

| Attribute | Required | Notes |
|---|---|---|
| `path` | Yes | Relative file path to the target content item |

```markdown
<c-content-link path="01-what-is-git-for.md">last chapter</c-content-link>
```

If the content is not found in the DB, renders as a `<span class="text-error">` with the path in the title.

Note: `content-link.html` has a TODO comment about leading/trailing whitespace and non-preview links. The `path` attribute uses the content's file path as stored in the DB.

### 3.14 `c-card`

**Template:** `freedom_ls/content_engine/templates/cotton/card.html`

Static content card with optional header image, title, and markdown body. No lightbox; for zoomable images use `c-picture`.

| Attribute | Required | Notes |
|---|---|---|
| `src` | No (default: `""`) | Header image path (same resolution as `c-picture`) |
| `alt` | No (default: `""`) | Alt text for header image |
| `title` | No (default: `""`) | Visible heading above body |
| `size` | No (default: `"medium"`) | `"small"`, `"medium"`, or `"large"`; unknown falls back to `"medium"` |

Size widths: `small` → `max-w-xs`, `medium` → `max-w-md`, `large` → `max-w-2xl`. Header image heights: `small` → `h-32`, `medium` → `h-44`, `large` → `h-64`.

```markdown
<c-card src="images/landscape.svg" alt="Landscape" title="Planning" size="large">
Card body markdown here.
</c-card>
```

### 3.15 `c-slot`

Not a standalone widget — used inside `c-flashcard` to define named content faces.

| Attribute | Required | Notes |
|---|---|---|
| `name` | Yes | `"front"` or `"back"` for flashcard; `"footer"` used internally by system components |

### 3.16 Authoritative `MARKDOWN_ALLOWED_TAGS`

Defined in `config/settings_base.py` lines 287–303:

```python
MARKDOWN_ALLOWED_TAGS = {
    "c-youtube":      {"video_id", "video_title", "caption"},
    "c-picture":      {"src", "alt", "title", "description", "number"},
    "c-content-link": {"path"},
    "c-pdf-embed":    {"src", "caption", "height"},
    "c-file-download":{"src", "text"},
    "c-pull-quote":   {"attribution", "cite", "source"},
    "c-equation":     {"label"},
    "c-image-grid":   {"columns"},
    "c-table":        {"caption"},
    "c-code-block":   {"title", "language", "wrap"},
    "c-admonition":   {"type", "title"},
    "c-flashcard":    set(),
    "c-accordion":    {"title", "open"},
    "c-card":         {"src", "alt", "title", "size"},
    "c-slot":         {"name"},
}
```

**Any attribute not in this set is stripped by nh3 before the cotton template ever renders.** A new component must be added to this dict.

**Discrepancy between docs and code:** The product doc `docs/product/content-editing-workflow.md` (lines 66–80) lists 13 components but omits `c-card` from the table. The settings file is the source of truth: `c-card` is registered and available.

The `fls-claude-plugin/resources/markdown_content.md` resource also omits `c-card` from its `MARKDOWN_ALLOWED_TAGS` listing. **Code wins.**

### 3.17 Rendering pipeline

`freedom_ls/markdown_rendering/markdown_utils.py` lines 14–72:

1. **python-markdown** with extensions: `fenced_code`, `mdx_headdown`, `tables`, `pymdownx.tasklist`.
   - `mdx_headdown`: H1 in content becomes H2 (prevents conflict with page title).
   - `pymdownx.tasklist`: `- [ ]` / `- [x]` become disabled checkbox inputs.
   - Indented code blocks are deregistered (line 27).
2. **nh3 sanitiser**: strips everything not in `MARKDOWN_ALLOWED_TAGS` union `nh3.ALLOWED_TAGS`. Also permits `input[type,checked,disabled,class]`, `li[class]`, `ul[class]` for task lists.
3. **django-cotton compiler**: `<c-*>` tags compiled to Django template syntax via `CottonCompiler`.
4. **Django template render**: final HTML returned as safe string.

---

## 4. UUID Rules

**Source:** `docs/product/content-editing-workflow.md` lines 17–18; `freedom_ls/content_engine/management/commands/content_save.py` lines 88–138; demo content comments in `demo_content/functionality_demo_end_with_topic/1. topic.md`.

1. **UUIDs are the stable upsert key.** `content_save` uses `update_or_create(id=uuid.UUID(item.uuid), site=site, defaults=fields)` (`content_save.py` line 288). The same file can be renamed or moved — as long as the UUID matches, it updates the existing DB row.

2. **First-run write-back.** On the first `content_save`, if a file has no UUID in frontmatter, a new UUID is generated, the DB row is created, and the UUID is **written back into the source file** (`update_file_with_uuid`, `content_save.py` lines 88–138). This modifies the authored files in place.

3. **Option UUIDs.** `QuestionOption` objects also get UUIDs written back into the page YAML files (`update_file_with_option_uuids`, `content_save.py` lines 142–188).

4. **Never hand-create UUIDs.** The demo content explicitly warns: "don't create them by hand / if one exists, don't edit it / don't duplicate uuids in different places" (`demo_content/functionality_demo_end_with_topic/1. topic.md` lines 12–15).

5. **Never duplicate UUIDs.** Duplicating a UUID across two files would cause one to silently overwrite the other on the next `content_save`.

6. **UUID format.** Standard UUID4 strings (e.g. `8bc127c1-edf1-4997-b7fc-35fdf8604f30`).

7. **Multi-document YAML.** `update_file_with_uuid` finds the **first section without a UUID** and writes to it (`content_save.py` lines 110–122). Sections that already have UUIDs are left untouched.

---

## 5. content_save / content_validate Pipeline

### 5.1 `content_validate`

`freedom_ls/content_engine/management/commands/content_validate.py`:

```
uv run python manage.py content_validate <path>
```

- Scans the path for all `.md` and `.yaml`/`.yml` files.
- Parses each through Pydantic with `extra="forbid"`.
- Reports all failures at once rather than stopping at the first error.
- Does **not** write to the database.

### 5.2 `content_save`

`freedom_ls/content_engine/management/commands/content_save.py`:

```
uv run python manage.py content_save <path> <site_name>
```

- Runs `validate()` first; aborts if validation fails.
- Wraps all DB writes in a single `@transaction.atomic` block.
- Upserts content by UUID (creates if no UUID; updates if UUID matches).
- Writes UUIDs back to source files for new items.
- Uploads binary assets (images, PDFs, etc.) to the `File` model.
- Resolves and saves `ContentCollectionItem` ordering for COURSE/COURSE_PART children.
- Safe to re-run on unchanged files (idempotent).

Save order within `content_save`:
1. Topics
2. Activities
3. Courses and CourseParts
4. Forms
5. FormPages, then FormQuestions/FormContent within each page
6. ContentCollectionItem (course/part children) linking

### 5.3 Strict Pydantic validation

`ConfigDict(extra="forbid")` on `BaseBaseContentModel` means **any field not defined in the Pydantic schema causes validation to fail**. Typos in frontmatter keys (e.g. `desciption` instead of `description`) produce a clear error message with the field path and the given value.

### 5.4 `danger_content_delete`

`freedom_ls/content_engine/management/commands/danger_content_delete.py`:

```
uv run python manage.py danger_content_delete [--yes]
```

Deletes **all** content from the database for all sites. Requires confirmation unless `--yes` is passed. Irreversible. Cascade order: Topics, Activities, Courses, ContentCollectionItems, Forms, FormPages, FormContent, FormQuestions, QuestionOptions, Files.

---

## 6. Obsidian Image Syntax

**Code:** `freedom_ls/content_engine/management/commands/content_save.py` lines 305–328, function `markdown_translate`.

At save time, before storing content, `content_save` rewrites Obsidian wiki-image syntax to `<c-picture>` tags:

| Obsidian syntax | Becomes |
|---|---|
| `![[image.jpg]]` | `<c-picture src="image.jpg"></c-picture>` |
| `![[image.jpg \| My Title]]` | `<c-picture src="image.jpg" title="My Title"></c-picture>` |

The regex patterns:
- With title: `r"!\[\[([^|\]]+)\s*\|\s*([^\]]+)\]\]"` → `src="{group1}" title="{group2}"`
- Without title: `r"!\[\[([^\]]+)\]\]"` → `src="{group1}"`

Note: `alt` is **not** set by the translation. The resulting `<c-picture>` will have no `alt` attribute, which means an empty alt is used — acceptable for decorative images but not for meaningful ones. Authors using Obsidian syntax should be aware that they cannot set meaningful alt text this way.

This translation also applies inside `FORM_CONTENT` blocks (same `markdown_translate` call path).

The `image-grid.html` comment (line 4) also notes that `![[file|title]]` inside a grid is handled by this same rewrite.

---

## Gaps, Contradictions, and Notes for Plugin Authors

1. **`c-card` missing from product docs and skill resource.** `docs/product/content-editing-workflow.md` and `fls-claude-plugin/resources/markdown_content.md` both omit `c-card` from their component listings, but it is registered in `MARKDOWN_ALLOWED_TAGS` and has a template. The code is the source of truth; `c-card` is available.

2. **`part.yaml` has no closing `---`.** Demo files show `part.yaml` without a terminating `---`. This is valid YAML (single document) but unusual for authors used to frontmatter-style files.

3. **`FORM_QUESTION` and `FORM_CONTENT` inherit `BaseBaseContentModel`, not `BaseContentModel`.** They have no `title`, `subtitle`, `description`, `category`, or `image` fields. The `category` field on `FormQuestion` is a different thing from `BaseContentModel.category` — it is used by the `CATEGORY_VALUE_SUM` scoring strategy.

4. **Obsidian image translation loses `alt` text.** This is a known limitation with no current workaround within the Obsidian syntax.

5. **Children auto-discovery vs explicit `children` list.** The `children` field on COURSE and COURSE_PART is optional; when absent, the directory is auto-scanned. The explicit `children` form is not used in any current demo content — all five demo courses rely on auto-discovery. Authors who need custom ordering or want to exclude certain files should use explicit `children`.

6. **`content_save` modifies source files.** This is expected behaviour, but a plugin that processes files before `content_save` has run should anticipate that UUIDs will be absent and will be added after the first save.

7. **The `meta` field accepts arbitrary dicts.** It is available on all types but never displayed by the standard UI — it is for author-defined metadata that downstream projects or custom templates might consume.

status: ok
