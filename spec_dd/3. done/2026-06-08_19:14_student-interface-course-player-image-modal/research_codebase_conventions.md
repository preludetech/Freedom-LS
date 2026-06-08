# Codebase Conventions: Course-Player Image Modal Redesign

Research artifact for the spec/plan phases of the `student-interface-course-player-image-modal` feature.
All file paths are relative to the repo root unless stated as absolute.

---

## 1. Current Image Lightbox

### File locations
- Template: `freedom_ls/content_engine/templates/cotton/picture.html`
- Alpine component: `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` (lines 52–78)

### `c-picture` component attributes (picture.html lines 1–16)

| Attribute | Default | Description |
|-----------|---------|-------------|
| `src`     | (required) | File path resolved via `get_file_by_path` template filter |
| `alt`     | (required) | Screen-reader alt text (should NOT duplicate the caption) |
| `caption` | `""` | Visible caption text; also used as `aria-label` fallback |
| `number`  | `""` | Figure number; rendered as "Figure N:" prefix in caption |

### Thumbnail card structure (lines 21–42)
- Wraps an `<img>` inside `<c-media-card class="max-w-xl mx-auto m-4">`
- Footer slot contains: muted `text-sm` caption span + an "Open image" button (`btn btn-secondary`) with `<c-icon name="fullscreen" class="size-4">`
- The open button carries `x-ref="trigger"` and `@click="show"`

### Lightbox overlay structure (lines 44–77)
```html
<div x-show="open" x-cloak x-transition.opacity role="dialog" aria-modal="true"
     aria-label="{{ caption|default:alt }}"
     @keydown.escape.window="onEscape"
     @keydown.tab.prevent="onTab"
     @click="close"
     class="fixed inset-0 flex justify-center items-center z-50 backdrop-blur-lg motion-reduce:transition-none">
```
- Close button (lines 55–61): `absolute top-0 right-0 bg-surface opacity-50 hover:opacity-70`, `<c-icon name="close" class="size-12 text-on-surface">` — `x-ref="closeBtn"`
- Caption block (lines 63–69): `absolute top-0` wrapper, `<p class="text-center text-4xl pt-6">` — only rendered if caption is truthy
- Image panel (lines 71–75): `relative w-7xl max-h-screen p-6 overflow-auto rounded-sm bg-surface`

### Alpine `contentLightbox` component (alpine-components.js lines 52–78)
- `open: false`, `_trigger: null`
- `show()`: captures `$refs.trigger` (or `document.activeElement`), sets `open = true`, focuses `$refs.closeBtn` on next tick
- `close()`: sets `open = false`, restores focus to `_trigger`
- `onEscape()`: calls `close()` if open
- `onTab()`: keeps focus on `$refs.closeBtn` (single-element focus trap)

### Why it currently looks bad

1. **Backdrop: blur only, no dimming scrim.** `backdrop-blur-lg` (line 53) produces a frosted-glass effect on the content underneath but there is no dark/tinted overlay layer. The background content bleeds through visibly, making the lightbox feel ungrounded and hard to read against.

2. **Close button: jammed in absolute corner with opacity hack.** The button sits at `top-0 right-0` with `opacity-50 hover:opacity-70` (line 58) — it has no padding, no visible affordance at rest, and uses a raw opacity fade rather than a proper interactive state. Its `size-12` icon is far larger than the standard `size-6` used by `c-modal`.

3. **Giant floating caption.** When a caption is set, it renders as `absolute top-0` with `text-4xl pt-6` (lines 64–65). This is visually intrusive (headline size for a caption), placed in dead space above the panel rather than anchored to the image card, and is invisible when there is no caption (no structural consistency).

4. **No spotlight card structure.** The image sits in a plain `bg-surface rounded-sm` div (line 71) with no header title row, no footer description area, no shadow, and no defined border. Compare with `c-modal` which has a structured header (title + close), content area, and optional footer.

5. **No dimming tint.** Without a semi-transparent black/dark scrim beneath the blur, images with light content appear to float with no visual separation from the page.

6. **Single transition only.** `x-transition.opacity` (line 46) provides a bare opacity fade but no scale transform — contrast with `c-modal` which has `translate-y + scale` for the panel and separate opacity for the backdrop.

---

## 2. Standard Modal Conventions

### File locations
- Template: `freedom_ls/base/templates/cotton/modal.html`
- Alpine component: `freedom_ls/base/static/base/js/alpine-components.js` (lines 101–128)

### Backdrop element (modal.html lines 30–40)
```html
<div x-show="open"
     x-transition:enter="ease-out duration-300"
     x-transition:enter-start="opacity-0"
     x-transition:enter-end="opacity-100"
     x-transition:leave="ease-in duration-200"
     x-transition:leave-start="opacity-100"
     x-transition:leave-end="opacity-0"
     class="fixed inset-0 backdrop-blur-sm transition-opacity"
     x-on:click="close">
</div>
```

**The standard backdrop has `backdrop-blur-sm` only — no dimming/tint colour.** There is no `bg-black/50` or similar scrim. This is a design gap that the lightbox redesign should address (a spotlight/stage effect needs darkness, not just blur).

### Panel element (modal.html lines 44–52)
```html
<div x-show="open"
     x-transition:enter="ease-out duration-300"
     x-transition:enter-start="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
     x-transition:enter-end="opacity-100 translate-y-0 sm:scale-100"
     x-transition:leave="ease-in duration-200"
     x-transition:leave-start="opacity-100 translate-y-0 sm:scale-100"
     x-transition:leave-end="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
     class="relative transform overflow-hidden rounded-lg bg-surface shadow-xl transition-all"
     x-on:click.away="close">
```

Panel classes: `rounded-lg bg-surface shadow-xl` — uses semantic tokens (adapts per theme).

### Panel header (modal.html lines 54–67)
```html
<div class="bg-surface px-6 py-4 border-b border-border border">
    <div class="flex items-center justify-between">
        <h3 class="text-lg font-semibold" id="...">{{ title }}</h3>
        <button x-on:click="close" type="button"
                class="text-muted hover:text-on-surface focus:outline-none focus:ring-2 focus:ring-primary rounded-md">
            <span class="sr-only">Close</span>
            <c-icon name="close" class="size-6" />
        </button>
    </div>
</div>
```

Close button pattern: `text-muted hover:text-on-surface focus:ring-2 focus:ring-primary rounded-md` with `size-6` icon (not `size-12`).

### Close affordances summary

| Mechanism | Location | Notes |
|-----------|----------|-------|
| Escape key | `x-on:keydown.escape.window="onEscape"` on outer wrapper (line 9) | Handled in Alpine `modal` component |
| Click backdrop | `x-on:click="close"` on backdrop div (line 39) | Closes on any backdrop click |
| Click away from panel | `x-on:click.away="close"` on panel div (line 52) | Redundant with backdrop click but belt-and-suspenders |
| Close button | `x-on:click="close"` on header button (line 60) | Visual affordance |

### Alpine `modal` component (base/alpine-components.js lines 102–128)
- `show()`: resets any form inside, sets `open = true`
- `close()`: sets `open = false`
- `onEscape()`: sets `open = false` (no focus-restore logic — unlike `contentLightbox`)
- **No focus management** — the lightbox needs to retain its own focus-trap logic

---

## 3. Theme Tokens

### File locations
- Default theme: `freedom_ls/themes/default/static/themes/default/theme.css`
- First class theme: `freedom_ls/themes/first_class/static/themes/first_class/theme.css`

### Surface and text tokens

| Token | Default value | First class value | Tailwind utility |
|-------|--------------|-------------------|-----------------|
| `--color-surface` | `#FFFFFF` | `#F8F9FC` (Stratosphere) | `bg-surface` / `text-surface` |
| `--color-surface-2` | `#F3F4F6` | `#EDF2F7` | `bg-surface-2` |
| `--color-on-surface` | `#1A2332` | `#1A1A2E` (Cockpit Dark) | `text-on-surface` |
| `--color-border` | `#D1D5DB` | `#E2E8F0` | `border-border` |
| `--color-muted` | `#4A5568` | `#718096` | `text-muted` |

Both themes use white/near-white surfaces. **For a lightbox backdrop, neither theme token provides a dark scrim out of the box — a semi-transparent black overlay (`bg-black/60` or similar) must be added explicitly.** It will look consistent across themes because it sits outside the theme token space.

### Shape (radius) tokens

| Token | Default value | First class value | Tailwind alias |
|-------|--------------|-------------------|---------------|
| `--fls-radius-sm` | `0.25rem` (4px) | `0.375rem` (6px) | `rounded-sm` |
| `--fls-radius-md` | `0.375rem` (6px) | `0.5rem` (8px) | `rounded-md` |
| `--fls-radius-lg` | `0.5rem` (8px) | `0.75rem` (12px) | `rounded-lg` |
| `--fls-radius-pill` | `9999px` | inherited (9999px) | `rounded-pill` |

(default theme: lines 118–121; first_class: lines 76–79)

The lightbox spotlight card should use `rounded-lg` so it automatically adapts (8 px in default, 12 px in first_class).

### Shadow
No `--fls-shadow-*` tokens are defined. The standard modal panel uses `shadow-xl` (a Tailwind built-in, not a theme token). Shadow is therefore NOT theme-adaptive; `shadow-xl` is the established convention for elevated panels. The brand guidelines say "use `shadow-sm` only if cards overlap or float" for regular cards; modals use `shadow-xl`.

### Font tokens

| Token | Default value | First class value |
|-------|--------------|-------------------|
| `--fls-font-sans` | System UI stack | `"DM Sans", system-ui, sans-serif` |
| `--fls-font-display` | Same as `--fls-font-sans` | `"Outfit", system-ui, sans-serif` |
| `--fls-font-mono` | System mono stack | `"IBM Plex Mono", ui-monospace, ...` |

These are theme-token-driven and automatically adapt. Any text in the spotlight card using `font-sans` or `font-display` will switch automatically.

### Card component tokens (default theme lines 113–115)
```css
--fls-card-radius: 1rem;      /* was rounded-2xl */
--fls-card-hero-height: 7rem; /* was h-28 */
--fls-card-padding: 1rem;     /* was p-4 */
```
These are for course cards specifically — not appropriate for a modal spotlight card.

### What is theme-token-driven vs hard-coded in the redesign
- **Auto-adapts via tokens:** surface colour (`bg-surface`), text colours (`text-on-surface`, `text-muted`), border (`border-border`), radius (`rounded-lg`/`rounded-md`), font stack, primary colour for focus ring
- **Must be hard-coded:** dark scrim opacity (e.g. `bg-black/60`), `shadow-xl`, transition durations/easings, `z-50`, `fixed inset-0`

---

## 4. Brand Guidelines (Relevant Excerpts)

Source: `.claude/skills/brand-guidelines/SKILL.md`

### On overlays and modals
The guidelines do not have a dedicated modal/overlay section, but the following principles apply directly:

- **No gradients, drop shadows, or decorative visual elements** (Guardrails > Don't, line 243). Exception: `shadow-xl` for elevated modal panels is already established in `c-modal` — this is functional elevation, not decoration. A pure decorative glow or coloured shadow would violate this.
- **Cards: `bg-white rounded-lg` with generous padding (`p-6`). No shadows by default; use `shadow-sm` only if cards overlap or float.** The spotlight card floats over the page, so a shadow is warranted — but use the same `shadow-xl` as `c-modal`, not a custom value.
- **Consistent whitespace, not decoration — use generous, consistent spacing for hierarchy.** The redesign should use standard padding (`p-6`) inherited from the modal convention.
- **Content first, chrome second.** The spotlight card must not visually compete with the image. Header and description should be minimal.
- **Progressive disclosure.** The description/caption should be present but visually subordinate; the image is primary.
- **Obvious over clever.** The close button must be immediately legible — not hidden behind opacity, not jammed in a corner.

### On colour usage for overlays
- No named brand colour maps directly to a dark scrim. Use `bg-black/60` (or similar opacity) which is not a theme token but is a neutral, non-branded utility.
- The backdrop blur on `c-modal` (`backdrop-blur-sm`) is already established as an FLS UI pattern for the default theme. For the lightbox (a more dramatic context), a stronger blur (`backdrop-blur-md`) with an added dark scrim is justified.

### On icons
- "Never use filled icons, multi-colour icons, or skeuomorphic styles" — confirms that outline-style Heroicons (the default icon set) are correct.
- Use `<c-icon name="close" />` for the close button (established by `c-modal`).

### Voice: button labels
- "Open image" (current) follows the "direct over diplomatic" principle — keep it.
- A close button aria-label of `"Close image"` (current) is correct per FLS naming.

---

## 5. Icons

### Icon system
All icons use `<c-icon name="semantic_name" />`. The component is at:
`freedom_ls/icons/templates/cotton/icon.html`

Skill reference: `fls-claude-plugin/skills/icon-usage/SKILL.md`

### Icons used by the current lightbox

| Icon name | Usage | Current size |
|-----------|-------|-------------|
| `fullscreen` | "Open image" button in thumbnail card | `size-4` |
| `close` | Close button in overlay | `size-12` (too large per conventions) |

Note: `fullscreen` is NOT in the documented semantic name list in the icon-usage skill. The listed names include `expand` / `collapse` but not `fullscreen`. This should be verified — either `fullscreen` is a valid but undocumented name, or it should be replaced with `expand`. The current template uses `name="fullscreen"` at picture.html line 37.

### Recommended sizes per icon-usage skill (SKILL.md lines 84–93)

| Size | Convention |
|------|------------|
| `size-4` | Compact (inside lists, small UI) |
| `size-5` | Standard (buttons, most UI) — default |
| `size-6` | Emphasis — **modal close buttons** (the standard) |
| `size-12` | Extra large (lightbox close) — listed as a convention |

The skill explicitly lists `size-12` as "lightbox close" (line 92), which means the current `size-12` for the close icon is intentional per the skill. However, pairing `size-12` with the `opacity-50` corner-anchor styling still produces a poor result visually. The redesign should decide whether to retain `size-12` or normalise to `size-6` inside a properly styled close button.

### How to use `c-icon`
```html
<c-icon name="close" class="size-6 text-muted" />
<c-icon name="fullscreen" class="size-4" />
```
- Use `class` for size and colour
- For icon-only buttons: put `aria-label` on the `<button>`, not on the icon
- Never use raw SVG or Font Awesome classes

---

## Summary: Key Gaps to Address in the Redesign

| Gap | Current state | Standard / desired |
|-----|--------------|-------------------|
| Backdrop dimming | `backdrop-blur-lg` only — no dark scrim | Add `bg-black/60` (or similar) + reduce blur to `backdrop-blur-md` |
| Backdrop transitions | `x-transition.opacity` on overlay wrapper only | Separate backdrop fade (like `c-modal`) + panel scale+fade |
| Close button styling | `absolute top-0 right-0 opacity-50` | Styled like `c-modal`: `text-muted hover:text-on-surface focus:ring-2 focus:ring-primary rounded-md` |
| Close button size | `size-12` (very large, uncontained) | `size-6` inside a properly padded button in a header row |
| Caption placement | Floating `absolute top-0 text-4xl` | In a structured header (title) or footer (description) section of the spotlight card |
| Spotlight card structure | Plain `bg-surface rounded-sm` div | Header row (title + close), image area, optional footer (caption/description) |
| Panel radius | `rounded-sm` (2px) | `rounded-lg` (theme-adaptive, 8–12px) |
| Shadow | None | `shadow-xl` (matches `c-modal`) |
| Focus trap | Single-element trap (close only) | Retain current `onTab` logic — it is correct for a single-focus-target dialog |
| Focus restore | Present (returns to trigger) | Retain — it is correct |

---

status: ok
