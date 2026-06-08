# Course-player image spotlight modal

## Problem

In the course player, a student can expand a content image. This opens the
lightbox in `c-picture` (`freedom_ls/content_engine/templates/cotton/picture.html`,
backed by the `contentLightbox` Alpine component). It currently looks ugly:

- the backdrop only blurs (`backdrop-blur-lg`) — there is **no dark scrim**, so
  the page bleeds through and the modal feels ungrounded;
- the close button is jammed into the corner with an `opacity-50` hack and an
  oversized `size-12` icon;
- the caption floats at the top as a `text-4xl` headline in dead space;
- there is no real "spotlight" card structure (just a plain `bg-surface rounded-sm` box).

## Goal

Make the expand-image modal a good-looking **spotlight**: a clean white image
card centred on a dimmed, blurred backdrop, with the figure label/title and a
description arranged as chrome around it. Follow the supplied design
(`image.png`, drawn in the `first_class` theme) and provide reasonable defaults
for the `default` theme.

This is a **redesign of existing functionality**, not a new feature. Keep the
inline thumbnail card + "Open image" trigger. Use the standard, already-established
ways of closing a modal.

**Build the spotlight as a native `<dialog>`, not an Alpine `x-show` div.** The
codebase already has a solid native-dialog precedent — the side panel in
`_base_interface.html` opens with `dialog.showModal()` (see the `sidePanel`
controller in `base/static/base/js/alpine-components.js`). `showModal()` gives us
the focus trap, inert background, Escape-to-close, and focus-restore-to-trigger
**for free**, which lets us delete most of the current `contentLightbox`
component (its `onTab` focus trap, `onEscape` handler, and manual `_trigger`
capture/restore all go away). The replacement controller mirrors `sidePanel` but
much smaller: an `open()` that calls `showModal()` and a backdrop-click handler
(`event.target === dialog → dialog.close()`). It also makes the spotlight the
natural consumer of the `.modal-backdrop-host::backdrop` utility (see below).

We are **not** converting `c-modal` to a `<dialog>` — it has many consumers plus
form-reset and HTMX-204 auto-close logic in its Alpine component. It stays the
`.modal-backdrop` (overlay-div) consumer. Only the lightbox — which is being
rewritten here anyway — becomes a dialog.

## Layout (follow the design)

Text sits **on the dark backdrop chrome** (light text on the dimmed scrim —
contrast is guaranteed), arranged around a centred white image card:

- **Top-left:** figure number + title (e.g. "Figure 3 — Propeller inspection points").
- **Top-right:** close (X) button.
- **Centre:** white spotlight card holding the image (rounded, soft shadow,
  image scaled to fit with `object-contain`).
- **Bottom-left:** title + description.

Yes, the title appears in both the top-left and the bottom — this is faithful to
the mockup and confirmed as intended.

## Component attributes

`c-picture` moves to this attribute set (decided with the user):

| Attribute     | Status                          | Use                                              |
|---------------|---------------------------------|--------------------------------------------------|
| `src`         | unchanged (required)            | file path, resolved via `get_file_by_path`       |
| `alt`         | unchanged                       | screen-reader alt text                           |
| `title`       | **renamed** from `caption`      | visible title (top-left + bottom, figcaption)    |
| `description` | **new**                         | longer description shown at the bottom of spotlight |
| `number`      | unchanged                       | figure number → "Figure N" prefix                |

Implications to handle (spec/plan phase):

- Update `MARKDOWN_ALLOWED_TAGS` in `config/settings_base.py` for `c-picture`
  (currently `{src, alt, caption}` → `{src, alt, title, description, number}`).
- Update any existing content that uses `caption=` (e.g. `demo_content/`,
  `image-grid` usages) to `title=`.

## Backdrop & close behaviour

- **Backdrop:** dark scrim + blur, via the new shared backdrop utility (see
  below). Because the spotlight is a native `<dialog>`, it uses the
  `.modal-backdrop-host::backdrop` hook (the dialog stays `bg-transparent` and
  fills the viewport; the `::backdrop` pseudo carries the dim+blur). The scrim
  sits outside the theme tokens so it stays consistent across themes.
- **Close:** keep all standard mechanisms already used in the codebase — close
  button, `Escape`, and click-outside. Guard the click-outside so clicking the
  white card or the image itself does **not** close the modal (only clicks on the
  surrounding scrim close it).

## Shared `.modal-backdrop` utility (cross-cutting refactor)

The three modal backdrops in the codebase are inconsistent — only the side panel
actually dims; `c-modal` and the lightbox only blur:

| Place | Markup | Scrim | Blur |
|-------|--------|-------|------|
| `_base_interface.html` side panel | native `<dialog>` `::backdrop` | `bg-black/50` | `backdrop-blur-sm` |
| `cotton/modal.html` | Alpine overlay `<div>` | none | `backdrop-blur-sm` |
| `cotton/picture.html` lightbox | Alpine overlay `<div>` | none | `backdrop-blur-lg` |

Extract a single source of truth into `tailwind.components.css` (the documented
home for reusable primitives). It needs two hooks because a scrim is rendered two
different ways — a real overlay `<div>` (Alpine) vs the `::backdrop` pseudo of a
native `<dialog>` (whose own box must stay `bg-transparent`):

```css
/* @layer components */
.modal-backdrop,                 /* overlay <div>: Alpine modals + lightbox */
.modal-backdrop-host::backdrop { /* native <dialog>: styles its ::backdrop  */
    @apply bg-black/50 backdrop-blur-sm;
}
```

Apply it in all three places (decided with the user — standardise on dim+blur):

- side panel `<dialog>` → add `modal-backdrop-host`, drop the inline
  `backdrop:bg-black/50 backdrop:backdrop-blur-sm` (same look, now shared);
- `cotton/modal.html` → add `modal-backdrop` to its backdrop div. **This is a
  deliberate visible change**: standard modals (course preview, delete dialogs,
  etc.) gain the dark scrim they currently lack;
- the new spotlight lightbox (also a native `<dialog>`) → add
  `modal-backdrop-host` (the `::backdrop` hook), alongside the side panel.

So the two hooks split as: `.modal-backdrop` → `c-modal` (overlay div);
`.modal-backdrop-host::backdrop` → side panel + spotlight (native dialogs).

The class carries only the scrim look (colour + blur). Positioning, `z-index`,
and transitions stay as inline utilities on each element. Blur strength is
standardised at `backdrop-blur-sm`; if the spotlight wants a stronger blur it can
layer one inline rather than forking the utility.

This touches `base` templates + `content_engine`; it is in-scope for this task
and ships in the same PR.

## Theming

- Use semantic tokens so the card adapts automatically: `bg-surface`,
  `text-on-surface`, `text-muted`, `border-border`, `rounded-lg`, focus ring on
  `primary`, theme font stack.
- Hard-code only the theme-neutral bits: the dark scrim opacity, `shadow-xl`,
  transition timings. (No `z-index` needed — `<dialog>` renders in the top
  layer.) `first_class` is the source design; `default` gets sensible defaults
  for free via the tokens.

## Accessibility (mostly free from `<dialog>`)

- Focus trap, Escape-to-close, inert background, and focus-restore-to-trigger all
  come from `showModal()` — no manual `onTab`/`onEscape`/`_trigger` code.
- Label the dialog via the title heading (`aria-labelledby`). `role="dialog"` /
  modal semantics are implicit for a modal `<dialog>`.
- Close button: always visible (no opacity hack), accessible label
  ("Close image"), comfortable touch target (~44px), standard `size-6`-style icon
  in a properly padded button rather than a bare `size-12` icon.
- Transitions: native `<dialog>` enter/leave needs `@starting-style` +
  `transition-behavior: allow-discrete` — copy the side-panel pattern in
  `tailwind.base_interface.css`. Respect `prefers-reduced-motion`: fade only,
  drop the scale animation.
- Mobile: dialog fills the viewport and centres the card; card adapts to small
  screens (`max-height: ~90dvh`, scroll inside the card for long descriptions);
  image scales to fit. The full-viewport dialog also makes backdrop clicks land
  on the dialog element so click-outside-to-close works.

## Out of scope (explicitly NOT building)

The mockup includes a toolbar and arrows that we are **not** implementing:

- no zoom controls;
- no download button;
- no pagination / next-previous arrows;
- no thumbnail strip.

## Suggestions to raise (don't build without approval)

- **`fullscreen` icon name.** The "Open image" trigger uses
  `<c-icon name="fullscreen">`, but the icon-usage skill documents `expand`, not
  `fullscreen`. Verify the name during implementation; switch to `expand` if
  `fullscreen` isn't a real icon.

## References

- `research_lightbox_ux.md` — lightbox/spotlight UX & accessibility best practices.
- `research_codebase_conventions.md` — current lightbox, standard modal, theme
  tokens, brand guidelines, icons (with file paths + line numbers).
