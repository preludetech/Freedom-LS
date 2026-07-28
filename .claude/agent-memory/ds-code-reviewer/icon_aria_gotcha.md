# Icon aria_label gotcha (decorative icons)

`<c-icon name="X" aria_label="" />` does NOT make an icon decorative.

In `freedom_ls/icons/backend.py` (DefaultIconBackend.render, ~line 101):
`aria_label=aria_label if aria_label else semantic_name`

So an empty `aria_label` falls back to the **semantic slug** and the SVG is
rendered with `role="img" aria-label="<slug>"` (always announced). There is no
`aria-hidden` code path in `build_svg`.

To make an icon decorative in this codebase, wrap it in an
`aria-hidden="true"` span (the established pattern — see
`course_list.html` line ~106, `cotton/pull-quote.html`). The accent icon
boxes in `course-card-shell.html` / `course-row-shell.html` already do this on
the wrapper `<div aria-hidden="true">`.

Watch for status/eyebrow icons that pass `aria_label=""` intending "decorative"
— they will announce the raw machine slug (e.g. "in_progress", "not_started",
"complete") and duplicate the adjacent visible label text.
