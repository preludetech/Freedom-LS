---
name: Markdown content-widget render pipeline
description: render_markdown order (markdown->nh3->cotton compile->Django render), why cotton output is trusted, the {{ slot }} vs {% markdown slot %} re-sanitise gotcha, and the SafeString-constructor rule
metadata:
  type: project
---

`freedom_ls/markdown_rendering/markdown_utils.py::render_markdown` pipeline:
markdown.convert -> nh3.clean(allowlist) -> cotton compile -> Django template render.

Key facts for reviewing content widgets (cotton/*.html under content_engine):
- nh3.clean runs on the WHOLE document BEFORE cotton compile. So a widget's slot text
  is sanitised at the outer level. Authors must pre-escape `< > &` in raw slots
  (equation LaTeX, code-block). This is a documented authoring constraint, not a bug.
- Cotton template OUTPUT is NOT re-sanitised — so attributes the template emits
  (x-data, @click, tabindex, role, aria-label, classes) are trusted and survive.
- A nested cotton component placed inside `{% markdown slot %}` gets RE-sanitised
  (strips <button>, x-data, classes). That's WHY `c-image-grid` deliberately emits
  `{{ slot }}` (raw) instead of `{% markdown slot %}` — to preserve nested c-picture's
  rendered lightbox markup. Confirmed design decision.
- `MARKDOWN_ALLOWED_TAGS` (config/settings_base.py ~line 288) is the allowlist of
  `c-*` tags + their permitted attributes. Unknown attrs are stripped by nh3.
- The pre-commit security hook BLOCKS the literal token for the legacy safe-marking
  helper. New filters that must return safe markup use the `SafeString(...)` constructor
  instead (functionally identical). Only legitimate where untrusted input is escaped and
  the rest is already render_markdown output — e.g. `inject_table_caption` in
  content_engine/templatetags/content_tags.py.

**Why:** These are the load-bearing security invariants for every content widget.
**How to apply:** When reviewing a new/changed cotton content widget, check: (1) is raw
slot text given an authoring escape note? (2) does it correctly choose {{ slot }} vs
{% markdown slot %}? (3) any SafeString use escapes the untrusted parts?
