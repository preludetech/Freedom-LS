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

Available: `callout.html`, `youtube.html`, `picture.html`, `content-link.html`

**Usage:**
```markdown
<c-callout level="info" title="Note">Content here</c-callout>
<c-youtube video_id="abc123"></c-youtube>
<c-picture src="images/file.svg" alt="Alt text"></c-picture>
<c-content-link path="other.md">link</c-content-link>
```

## Adding New Components

1. Create `freedom_ls/content_engine/templates/cotton/<name>.html`
2. Register in `config/settings_base.py`:
   ```python
   MARKDOWN_ALLOWED_TAGS = {
       "c-name": {"attr1", "attr2"},
   }
   ```
3. Use in markdown: `<c-name attr1="value"></c-name>`

## Notes

- **H1 becomes H2** (mdx_headdown prevents title conflicts)
- **Relative paths** resolved via `calculate_path_from_root()`
- **Template tag:** `{% markdown text %}` renders standalone markdown
