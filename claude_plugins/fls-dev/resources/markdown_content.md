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
1. Markdown → HTML (extensions: fenced_code, md_in_html, mdx_headdown, tables, pymdownx.tasklist)
2. Sanitize with nh3 (only `MARKDOWN_ALLOWED_TAGS` allowed)
3. Render Cotton components
4. Return safe HTML

## Cotton Components in Markdown

**Location:** `freedom_ls/content_engine/templates/cotton/`

Includes `admonition.html`, `flashcard.html`, `accordion.html`, `youtube.html`, `picture.html`, `content-link.html`, `audio.html`, `audio-reveal.html`, `audio-clip.html`.

These widgets are for authored markdown only. App templates (pages, panels, dialogs) use `<c-callout tone="info|success|warning|error" title="...">` from `freedom_ls/base/templates/cotton/callout.html` instead of `<c-admonition>`, and never hand-build the admonition look (a thick coloured start border with a tint). `test_app_templates_hand_build_no_admonition_look` fails on one.

**Usage:**
```markdown
<c-admonition type="note" title="Optional heading">Content here</c-admonition>
<c-admonition type="warning">Watch out!</c-admonition>
<c-flashcard>
  <c-slot name="front">What is the question?</c-slot>
  <c-slot name="back">This is the answer.</c-slot>
</c-flashcard>
<c-flashcard size="wide">
  <c-slot name="front">A question whose answer is a table.</c-slot>
  <c-slot name="back">A wider card, left-aligned faces.</c-slot>
</c-flashcard>
<c-accordion title="Optional detail">Hidden until expanded.</c-accordion>
<c-accordion title="Open by default" open>Starts expanded.</c-accordion>
<c-youtube video_id="abc123"></c-youtube>
<c-picture src="images/file.svg" alt="Alt text"></c-picture>
<c-content-link path="other.md">link</c-content-link>
<c-audio src="audio/file.mp3" label="Listen" respelling="ow-dee-oh" symbol="aw"></c-audio>
<c-audio-reveal src="audio/file.mp3" label="Listen" respelling="ow-dee-oh" symbol="aw"></c-audio-reveal>
<c-audio-clip src="audio/lecture.mp3" title="Lecture excerpt" kind="Listening exercise">

Transcript paragraph.

Another paragraph.

</c-audio-clip>
```

`c-audio-clip` plays one longer recording. `title` is required; `kind` is an optional label beside it; the slot is an optional transcript (markdown, blank lines between paragraphs) behind a Show transcript toggle. The total time comes from `File.duration_seconds`, which `content_save` fills for audio files.

`c-admonition` `type` values: `note`, `tip`, `important`, `warning`, `danger`, `key_takeaways`, `checklist`. Unknown types fall back to `note`.

`c-audio-reveal` is a say-it-then-reveal card: the `symbol` tile is the prompt, and clicking the space where the answer will appear shows it and plays the audio. `symbol` is required on it.

**Slot widgets** (`c-accordion`, `c-admonition`, `c-audio-clip`, `c-card`, `c-flashcard`, `c-pull-quote`, `c-table`) have a body that is author markdown. `render_markdown` converts that body once for every tag in the `MARKDOWN_BODY_TAGS` setting (`freedom_ls/markdown_rendering/config.py`). The widget template declares `markdown=""` in `c-vars` and emits its slot with `{% markdown_body slot markdown %}`: as-is normally, converted when the widget sits under a parent `render_markdown` does not mark (raw HTML such as `<div>`), which leaves `markdown="1"` on it. A new slot widget goes into `MARKDOWN_BODY_TAGS`. Do not run `{% markdown slot %}` in a widget template: a second pass re-converts rendered widget markup. Any widget can nest inside a slot widget.

## Adding New Components

1. Create `freedom_ls/content_engine/templates/cotton/<name>.html`
2. Register in `config/settings_base.py`:
   ```python
   MARKDOWN_ALLOWED_TAGS = {
       "c-name": {"attr1", "attr2"},
   }
   ```
3. Use in markdown: `<c-name attr1="value"></c-name>`
4. A widget that needs its own endpoint puts it in the `content_engine` URLconf (`freedom_ls/content_engine/urls.py`, namespace `content_engine`, mounted under `content/`). `audio_file` is the example: `c-audio` points its button at `content_engine:audio_file`, which redirects to a freshly signed URL.

The current allowlist (from `config/settings_base.py`) is:
```python
MARKDOWN_ALLOWED_TAGS = {
    "c-youtube": {"video_id", "video_title", "caption"},
    "c-picture": {"src", "alt", "title", "description", "number"},
    "c-content-link": {"path"},
    "c-article-link": {"path"},
    "c-article-card": {"path", "variant"},
    "c-course-card": {"path", "variant"},
    "c-pdf-embed": {"src", "caption", "height"},
    "c-file-download": {"src", "text"},
    "c-pull-quote": {"attribution", "cite", "source"},
    "c-equation": {"label"},
    "c-grid": {"columns"},
    "c-audio": {"src", "label", "respelling", "symbol"},
    "c-audio-reveal": {"src", "label", "respelling", "symbol"},
    "c-audio-clip": {"src", "title", "kind"},
    "c-image-grid": {"columns"},
    "c-table": {"caption"},
    "c-code-block": {"title", "language", "wrap"},
    "c-admonition": {"type", "title"},
    "c-flashcard": {"size"},
    "c-accordion": {"title", "open"},
    "c-card": {"src", "alt", "title", "size"},
    "c-slot": {"name"},
}
```

## Retiring Removed Content

`content_save` treats its source paths as the site's whole source. A row of a retirable model that the run does not find gets `retired_at` set; it is never deleted. A later run that finds the row's uuid (a `File` by its path) clears `retired_at`, so returning content un-retires it.

- A run that would retire a course is refused unless it is passed `--allow-course-retire`.
- Default managers do not filter. A learner-facing read opts in with `.not_retired()` (`RetirableQuerySet` in `freedom_ls/content_base/models.py`); `is_retired` is the per-row check.
- `save_content_to_db` stays additive unless the caller passes `retire_missing=True` (and `allow_course_retire=True` to let it retire a course).

## Notes

- **H1 becomes H2** (mdx_headdown prevents title conflicts)
- **Relative paths** resolved via `calculate_path_from_root()`
- **Template tag:** `{% markdown text %}` renders standalone markdown
