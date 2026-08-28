# Idea: the docked side panel takes focus on load, so the browser paints a focus outline around the whole column

## The bug

Source: visual QA of the course player on the `first_class` theme.

On first load of any interface built on `_base_interface.html`, a heavy border wraps the entire
left-hand side panel. In the course player that traces the whole table-of-contents column.

It is the browser's own `:focus-visible` outline, painted on the `<dialog>` element itself. The
chain:

- `_base_interface.html:22` hardcodes `data-desktop-lock="true"`, so on desktop the panel is locked
  open for every consumer of the shell.
- `alpine-components.js:552` calls `this.dialog.show()` whenever the panel should be open, which on a
  locked panel means on every `init()`.
- Per the HTML standard, `show()` runs the dialog focusing steps. With no `autofocus` anywhere in the
  dialog subtree, the `<dialog>` element itself becomes the focused element. That is deliberate
  behaviour: whatwg/html#4184 changed it away from focusing the first focusable descendant.
- Nothing in `tailwind.base_interface.css`, `tailwind.components.css` or either shipped theme targets
  `.side-panel-dialog:focus` or `:focus-visible`, so the UA outline is what renders. Because
  `.side-panel-dialog` is sized to the full grid column, the outline traces the whole panel.

This is `:focus-visible` rather than bare `:focus`. Browsers paint it on purpose when focus moves
programmatically into a dialog (w3c/csswg-drafts#7214), so it is not a spurious ring to switch off.

One useful detail for whoever fixes this: `--color-focus-ring` is declared at
`themes/default/static/themes/default/theme.css:134` and already has four consumers, at
`partials/header_bar_user_menu.html:2`, `cotton/table.html:17`, `cotton/code-block.html:23` and
`cotton/equation.html:21`. There is an established way this codebase draws a focus ring; the side
panel should match it.

## Expected fix

Restyle the indicator rather than removing it. Give `.side-panel-dialog` a focus style of its own
drawn from `--color-focus-ring`, a slim inset ring instead of the UA outline around the full
column.

Whatever ships must still satisfy WCAG 2.2 SC 2.4.7 Focus Visible, and the 2px-perimeter area and 3:1
contrast bars of SC 2.4.13 Focus Appearance. Subtle here means a smaller footprint and an on-brand
colour, not a thinner or absent indicator.

Two rejected alternatives. `outline: none` removes a real focus indicator and fails SC 2.4.7
outright. `autofocus` on the first TOC link only relocates the ring, at the cost of throwing
screen-reader focus into the panel on every page load, which is the behaviour whatwg/html#4184
deliberately moved away from.

Worth deciding separately, and not blocking the restyle: whether a permanently docked,
non-dismissible desktop column should run the dialog focusing steps at all. `show()` is being used
for its top-layer and open/close semantics, but the focus-stealing side effect is unwanted on
desktop, and since `data-desktop-lock="true"` is hardcoded in the shared shell this reaches the
educator interface and panel framework as well. The mobile path is a different matter and
`showModal()` earns its keep there: focus trap, inert background and native Escape are all wanted for
a dismissible overlay.

## Sources

- `freedom_ls/base/templates/_base_interface.html:22`, the hardcoded desktop lock, and `:47`, the
  dialog element and its classes.
- `freedom_ls/base/static/base/js/alpine-components.js:552`, the `dialog.show()` call. `:575` is the
  mobile `showModal()` counterpart, and the reasoning for the split is in the comments at `:391-399`.
- `freedom_ls/themes/default/static/themes/default/theme.css:134`, the `--color-focus-ring` token,
  and its existing consumers in `freedom_ls/base/templates/partials/header_bar_user_menu.html:2`,
  `freedom_ls/content_engine/templates/cotton/table.html:17`, `.../cotton/code-block.html:23` and
  `.../cotton/equation.html:21`.
- WHATWG HTML Standard, the dialog element and its focusing steps. whatwg/html#4184 for why the
  dialog itself takes focus, w3c/csswg-drafts#7214 for why `:focus-visible` matches.
- W3C WAI, Understanding SC 2.4.7 Focus Visible and SC 2.4.13 Focus Appearance.
