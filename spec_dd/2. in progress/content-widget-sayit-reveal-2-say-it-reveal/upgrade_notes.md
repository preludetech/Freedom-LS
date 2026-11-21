---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/content_engine/templates/cotton/accordion.html
  - freedom_ls/content_engine/templates/cotton/admonition.html
  - freedom_ls/content_engine/templates/cotton/audio.html
  - freedom_ls/content_engine/templates/cotton/audio-reveal.html
  - freedom_ls/content_engine/templates/cotton/card.html
  - freedom_ls/content_engine/templates/cotton/flashcard.html
  - freedom_ls/content_engine/templates/cotton/grid.html
  - freedom_ls/content_engine/templates/cotton/pull-quote.html
  - freedom_ls/content_engine/templates/cotton/table.html
  - freedom_ls/content_engine/templates/content_engine/partials/audio_card_body.html
requires_settings_change: true
changed_settings:
  - MARKDOWN_ALLOWED_TAGS  # optional: not checked at boot; add "c-audio-reveal" to use the new widget
  - MARKDOWN_BODY_TAGS  # new, optional: add the tag of each custom widget whose body is markdown
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: content-widget-sayit-reveal-2-say-it-reveal

## Breaking changes

- Slot widgets no longer run their body through markdown in the template. `render_markdown`
  (`freedom_ls/markdown_rendering/markdown_utils.py`) now converts the body of `c-accordion`,
  `c-admonition`, `c-card`, `c-flashcard`, `c-pull-quote`, `c-table`, `c-slot`, `c-grid` and
  `c-image-grid` itself and sanitises it before Cotton renders the template. The list is the new
  `MARKDOWN_BODY_TAGS` setting. Under a parent it does not convert (raw HTML such as `<div>`) the
  body arrives unconverted and the widget keeps `markdown="1"`; the new
  `{% markdown_body slot markdown %}` tag converts it then and emits it as-is otherwise.
- A project that overrides one of the six slot widget templates must declare `markdown=""` in
  `c-vars` and replace `{% markdown slot %}` with `{% markdown_body slot markdown %}` (for
  `c-flashcard`, `front` and `back`; for `c-table`, `{% markdown_body slot markdown as body %}`
  then `{% if caption %}{{ body|inject_table_caption:caption }}{% else %}{{ body }}{% endif %}`).
  A template that keeps `{% markdown slot %}` re-sanitises already-rendered HTML: it strips nested
  widgets' markup and may wrap the body in extra paragraphs.
- A project's own custom widget whose body is markdown: add its tag to `MARKDOWN_BODY_TAGS`
  (keeping FLS's tags) and make the same template change.

## Manual steps

- A project with a custom widget whose body is markdown sets `MARKDOWN_BODY_TAGS` to FLS's default
  plus that tag: `(*MarkdownRenderingConfig.declared_settings["MARKDOWN_BODY_TAGS"].default, "c-my-widget")`
  (from `freedom_ls.markdown_rendering.config`).

- A project that sets its own `MARKDOWN_ALLOWED_TAGS` adds
  `"c-audio-reveal": {"src", "label", "respelling", "symbol"}` to use the new widget. Without it
  the tag is stripped from content. No system check enforces this.
- A project that overrides `cotton/audio.html` should compare it with FLS's: the text column and
  play button moved to `content_engine/partials/audio_card_body.html`, shared with
  `cotton/audio-reveal.html`.
- A new semantic icon name, `reveal_hidden`, is mapped in every built-in icon set. A project can
  restyle it through `FREEDOM_LS_ICON_OVERRIDES`; no action is needed otherwise.
- Rebuild Tailwind: the new `cotton/audio-reveal.html` and the changed widget templates use new
  utility classes.
