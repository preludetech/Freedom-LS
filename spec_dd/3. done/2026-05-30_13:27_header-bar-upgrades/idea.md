# Header bar upgrades

Three related upgrades to `freedom_ls/base/templates/partials/header_bar.html`:

1. Initials avatar (replaces the email/name shown in the user-menu trigger).
2. Header-scoped theme tokens so themes can recolour the header independently of the brand role colours.
3. Sticky behaviour, with the on-scroll treatment differing per theme.

Background research lives alongside this file:

- `research_avatar.md`
- `research_header_tokens.md`
- `research_scroll_header.md`

Decisions captured below override the research where they differ.

---

## 1. Avatar instead of name/email in the header

Replace the current `{{ user.display_name }}` text (and the small-screen user icon) with a circular avatar that shows the user's initials. The avatar is the trigger for the existing dropdown menu, so dropdown contents and behaviour do not change.

### Initials derivation

Cascade, first match wins:

1. `first_name` + `last_name` → first letter of each.
2. `first_name` only (no last name) → if it splits on whitespace into multiple tokens, take first letter of the first two; otherwise first two letters of `first_name`.
3. No name at all → first two alphabetic characters of the email local-part (the part before `@`), skipping non-alphabetic prefixes (digits, punctuation, emoji).
4. Nothing usable (e.g. `123@x.com`) → fall back to a generic user icon (`c-icon name="user"`).

Rules:

- Always uppercased for Latin scripts.
- Do not ASCII-fold diacritics — `Élise Önen` → `ÉÖ`.
- For non-Latin scripts (CJK, Arabic, Devanagari, etc.) use a single grapheme rather than trying to extract two.

The derivation belongs on the `User` model as a property (e.g. `User.initials`) so it's reusable beyond the header. If the cascade returns nothing, the property returns `None` and the template renders the fallback icon.

### Visual

- Circle, ~36–40 px, always `rounded-full`.
- Background colour: a single themable colour (no per-user hashing). Defaults to `--color-primary` with `--color-on-primary` text via the new header-action tokens (see §2). This means in the default theme the avatar is invisible against the `bg-primary` header — that is fine because the avatar visually merges with the action region; in `first_class` (white header) the avatar reads as the indigo profile pill the brand wants.
- Font weight ~semibold, font-size ~40 % of diameter.
- Hover/focus states inherit from the existing button/dropdown trigger conventions.

### Accessibility

- The dropdown trigger is a `<button>` with an `aria-label` like `"Open user menu for {{ user.display_name }}"`.
- The visual initials are wrapped in `<span aria-hidden="true">` so screen readers announce the accessible name once, not twice.
- Focus ring uses `--color-focus-ring` (already established).

---

## 2. Header-scoped theme tokens

Add a small set of tokens so a theme can recolour the header without touching the brand role colours. Four tokens, no more:

- `--color-header` — header bar background.
- `--color-on-header` — foreground on the header (site title, generic header text).
- `--color-header-action` — background of the avatar/profile button on the right.
- `--color-on-header-action` — foreground on the action button (initials text).

### Defaulting

Defaults are declared via `@theme inline` aliases so themes that override `--color-primary` propagate automatically, and themes that explicitly set the new tokens win:

- `--color-header` defaults to `var(--color-primary)`.
- `--color-on-header` defaults to `var(--color-on-primary)`.
- `--color-header-action` defaults to `var(--color-primary)`.
- `--color-on-header-action` defaults to `var(--color-on-primary)`.

The header template uses `bg-header`, `text-on-header`, `bg-header-action`, `text-on-header-action` — generated automatically by Tailwind v4 from the `--color-*` namespace.

### `first_class` overrides

`first_class` redeclares:

- `--color-header: var(--color-surface);` (white)
- `--color-on-header: var(--color-on-surface);` (dark text)
- `--color-header-action: var(--color-primary);` (indigo pill)
- `--color-on-header-action: var(--color-on-primary);` (white initials)

No new hover, border, focus-ring, or scrolled-state tokens. Existing `color-mix` hover machinery and `--color-focus-ring` already cover the header.

---

## 3. Sticky behaviour, theme-divergent on-scroll treatment

The header becomes a `position: sticky; top: 0` element in both themes, with `z-30`. Auto-hide on scroll-down is out of scope for v1 — LMS users want predictable nav and HTMX swaps complicate scroll-direction tracking.

### On-scroll treatment

Per-theme implementations of "what happens visually when you've scrolled":

- **Default theme (coloured header):** stays opaque. A subtle shadow / border-bottom appears once `scrollY > 0`. No backdrop-blur — research confirmed it has no visual effect on an opaque background and just costs GPU.
- **`first_class` theme (white header):** when `scrolled`, header becomes `bg-header/85` (or similar alpha) with `backdrop-blur-md saturate-150`. At `scrollY == 0` the header is fully opaque and flush with the page so the blur transition only kicks in once content is actually moving beneath.

The "scrolled" state is exposed via a class (e.g. `data-scrolled` or an Alpine-managed `scrolled` class). Modern CSS `@container scroll-state(stuck: top)` is a candidate but not a hard requirement — implementation plan can decide between Alpine + scroll listener and the CSS-only approach.

### Layout / a11y guardrails

- Set `scroll-padding-top` (or `scroll-margin-top` on anchor targets) so deep links and keyboard focus aren't hidden behind the header.
- Audit ancestors of the header for `overflow: hidden` / `transform` / `filter` — these silently break `position: sticky`.
- Wrap the colour/blur transition in `motion-reduce:transition-none` so users with `prefers-reduced-motion` get an instant change rather than a fade.
- Verify text contrast at the translucent setting in the `first_class` theme during QA (translucent over arbitrary content can break WCAG AA).

---

## Out of scope (deliberately)

- Per-user hash-coloured avatars — single themable colour for now; revisit if we need to distinguish users in shared lists (e.g. educator views).
- Avatar uploads / profile pictures — initials only.
- Auto-hide-on-scroll-down — defer until there is a concrete mobile-real-estate complaint.
- A `--color-header-scrolled` token — opacity is best applied via a utility (`bg-header/85`) rather than a second hue token.
- Generalising the avatar component beyond the header — derivation lives on `User` so any future caller (educator lists, comments, etc.) can use it, but no other callers are migrated as part of this work.
