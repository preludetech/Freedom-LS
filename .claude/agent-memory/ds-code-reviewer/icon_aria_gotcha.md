# Icon aria_label (decorative by default)

`<c-icon name="X" />` with no `aria_label` renders `aria-hidden="true"` and no
role: it is decorative. `aria_label="Completed"` renders `role="img"
aria-label="Completed"`. The svg also carries `data-icon="X"`.

In `freedom_ls/icons/backend.py`, `build_svg` chooses between the two; the
default backend passes the label through unchanged (no fallback to the slug).

What to watch for in review:

- An icon that is the only thing conveying its meaning (a boolean mark, a
  status icon with no text beside it) and has no `aria_label`: it is silent.
- An icon-only button or link: the `aria-label` (or sr-only text) belongs on
  the control, not the icon.
- `aria-hidden="true"` wrapper spans around icons are now redundant but
  harmless; an icon next to visible text needs neither.
