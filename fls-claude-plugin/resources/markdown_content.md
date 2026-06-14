# Markdown Content System

## Models with Markdown Content

These models extend `MarkdownContent` and have a `content` TextField:

- **Topic, Activity, Course, Form, FormContent** - `freedom_ls/content_engine/models.py`

## Rendering

```python
# In Python
html = topic.rendered_content()

# In templates (already marked safe)
{{ topic.rendered_content }}
```

**What happens:**
1. Markdown → HTML (extensions: fenced_code, mdx_headdown, tables)
2. Sanitize with nh3 (only `MARKDOWN_ALLOWED_TAGS` allowed)
3. Render Cotton components
4. Return safe HTML

## Cotton Components in Markdown

**Location:** `freedom_ls/content_engine/templates/cotton/`

Available: `admonition.html`, `flashcard.html`, `accordion.html`, `youtube.html`, `picture.html`, `content-link.html`, and more.

**Usage:**
```markdown
<c-admonition type="note" title="Optional heading">Content here</c-admonition>
<c-admonition type="warning">Watch out!</c-admonition>
<c-flashcard>
  <c-slot name="front">What is the question?</c-slot>
  <c-slot name="back">This is the answer.</c-slot>
</c-flashcard>
<c-accordion title="Optional detail">Hidden until expanded.</c-accordion>
<c-accordion title="Open by default" open>Starts expanded.</c-accordion>
<c-youtube video_id="abc123"></c-youtube>
<c-picture src="images/file.svg" alt="Alt text"></c-picture>
<c-content-link path="other.md">link</c-content-link>
```

`c-admonition` `type` values: `note`, `tip`, `important`, `warning`, `danger`, `key_takeaways`, `checklist`. Unknown types fall back to `note`.

## Adding New Components

1. Create `freedom_ls/content_engine/templates/cotton/<name>.html`
2. Register in `config/settings_base.py`:
   ```python
   MARKDOWN_ALLOWED_TAGS = {
       "c-name": {"attr1", "attr2"},
   }
   ```
3. Use in markdown: `<c-name attr1="value"></c-name>`

The current allowlist (from `config/settings_base.py`) is:
```python
MARKDOWN_ALLOWED_TAGS = {
    "c-youtube": {"video_id", "video_title", "caption"},
    "c-picture": {"src", "alt", "title", "description", "number"},
    "c-content-link": {"path"},
    "c-pdf-embed": {"src", "caption", "height"},
    "c-file-download": {"src", "text"},
    "c-pull-quote": {"attribution", "cite", "source"},
    "c-equation": {"label"},
    "c-image-grid": {"columns"},
    "c-table": {"caption"},
    "c-code-block": {"title", "language", "wrap"},
    "c-admonition": {"type", "title"},
    "c-flashcard": set(),
    "c-accordion": {"title", "open"},
    "c-slot": {"name"},
}
```

## Notes

- **H1 becomes H2** (mdx_headdown prevents title conflicts)
- **Relative paths** resolved via `calculate_path_from_root()`
- **Template tag:** `{% markdown text %}` renders standalone markdown
