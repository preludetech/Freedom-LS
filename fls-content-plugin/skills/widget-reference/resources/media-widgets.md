<!-- Source: config/settings_base.py (MARKDOWN_ALLOWED_TAGS), freedom_ls/content_engine/templates/cotton/youtube.html, picture.html, image-grid.html, pdf-embed.html, file-download.html, research_authoring_format.md §3 -->

# Media Widgets

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

---

## `c-youtube`

Embeds a YouTube video iframe.

**Allowed attributes:** `video_id`, `video_title`, `caption`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `video_id` | Yes | — | The `v=...` part of the YouTube URL |
| `video_title` | No | `"YouTube video player"` | Accessible title for the iframe |
| `caption` | No | `""` | Text caption shown beneath the player |

```markdown
<c-youtube video_id="01MXBvMeFCw" caption="A short description."></c-youtube>
```

To get the `video_id` from a YouTube URL:
- `https://www.youtube.com/watch?v=01MXBvMeFCw` → `video_id="01MXBvMeFCw"`
- `https://youtu.be/01MXBvMeFCw` → `video_id="01MXBvMeFCw"`

---

## `c-picture`

Responsive image with keyboard-accessible lightbox modal.

**Allowed attributes:** `src`, `alt`, `title`, `description`, `number`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | File path (resolved from DB via `get_file_by_path`) |
| `alt` | Yes | — | Alt text for screen readers; use `alt=""` for decorative images |
| `title` | No | `""` | Visible caption under thumbnail and lightbox heading |
| `description` | No | `""` | Longer description shown only in the lightbox |
| `number` | No | `""` | Figure number; prefixes `title` with "Figure N" |

```markdown
<c-picture src="images/landscape.svg" alt="Blue sky over mountains" title="A scenic landscape" number="1"></c-picture>
```

**Do not duplicate `alt` and `title`.** `alt` is for screen readers; `title` is visible text for all users.

Image paths are relative to the content file (resolved to the course root by `content_save`).

---

## `c-image-grid`

Layout wrapper for multiple `c-picture` children. Tiles into columns.

**Allowed attributes:** `columns`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `columns` | No | `"3"` | `"2"`, `"3"`, or `"4"`; other values fall back to 3 |

**Critical authoring quirks:**
1. Always use the **closed form** `<c-picture ...></c-picture>` — never self-closing `/>`.
2. Leave a **blank line between each child** so the markdown parser treats them as separate block elements.

```markdown
<c-image-grid columns="2">

<c-picture src="images/a.svg" alt="Image A" title="First image"></c-picture>

<c-picture src="images/b.svg" alt="Image B" title="Second image"></c-picture>

</c-image-grid>
```

---

## `c-pdf-embed`

Inline PDF viewer via `<iframe>`.

**Allowed attributes:** `src`, `caption`, `height`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | File path (resolved from DB) |
| `caption` | No | `""` | Caption text beneath the viewer |
| `height` | No | `"600px"` | CSS height of the iframe |

```markdown
<c-pdf-embed src="sample.pdf" caption="Sample Document" height="800px"></c-pdf-embed>
```

---

## `c-file-download`

Download button (does not display the file inline).

**Allowed attributes:** `src`, `text`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | File path (resolved from DB) |
| `text` | No | `"Download file"` | Button label |

```markdown
<c-file-download src="sample.pdf" text="Get the PDF"></c-file-download>
```
