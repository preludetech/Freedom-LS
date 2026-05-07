# First-class Tier-1 token gap analysis

Scope: confirm that `freedom_ls/themes/first_class/static/themes/first_class/theme.css` faithfully encodes the Modern Altitude brand defined in `spec_dd/2. in progress/themable-implementations-master-decomposed-into-phases/first-class-theme.md`, and identify the minimum Tier-1 changes (in both first_class and default themes) to support the design-system mockups under `spec_dd/1. next/first-class-theme-implement-tier-1-and-2/design-system/`.

The user has already decided:

- Add `--fls-font-mono` (IBM Plex Mono) to first_class and default. Mono is a brand requirement and is exercised by `type-mono.html`, `colors-semantic.html`, `radii.html`, etc.
- Add explicit `*-light` semantic tints (`success-light`, `warning-light`, `error-light`, `info-light`) to first_class and default. This replaces today's `bg-success/15`-style opacity-modifier chip backgrounds with named tokens.
- Do **not** add a 50-900 neutral ramp (deferred by master spec §"Out-of-scope token surfaces").
- Do **not** widen any other token surface.

## Current first_class theme.css — drift check (per-token table)

Comparison vs. `first-class-theme.md` (Modern Altitude). All hex values match the brand doc; only the radii are ahead of where the design-system mockups land.

| Token | first_class theme.css | Brand reference | Status |
| --- | --- | --- | --- |
| `--color-primary` | `#283593` | Deep Indigo `#283593` | OK |
| `--color-on-primary` | `#FFFFFF` | white on deep indigo | OK |
| `--color-secondary` | `#00CEC9` | Electric Teal `#00CEC9` | OK |
| `--color-on-secondary` | `#1A1A2E` | dark text on bright teal (mockup chips use `#0b3a3a`; `#1A1A2E` is fine for solid teal) | OK |
| `--color-accent` | `#FF6B35` | Altitude Orange `#FF6B35` | OK |
| `--color-on-accent` | `#FFFFFF` | white on orange (matches `components-buttons.html` `.btn-accent`) | OK |
| `--color-success` | `#38A169` | Success `#38A169` | OK |
| `--color-on-success` | `#FFFFFF` | white on solid green (chip dark text only used on Light tint) | OK |
| `--color-warning` | `#D69E2E` | Warning `#D69E2E` | OK |
| `--color-on-warning` | `#1A1A2E` | dark text on yellow | OK |
| `--color-error` | `#E53E3E` | Error `#E53E3E` | OK |
| `--color-on-error` | `#FFFFFF` | white on red | OK |
| `--color-info` | `#3182CE` | Info `#3182CE` | OK |
| `--color-on-info` | `#FFFFFF` | white on blue | OK |
| `--color-surface` | `#F8F9FC` | Stratosphere `#F8F9FC` | OK |
| `--color-surface-2` | `#EDF2F7` | Neutral 100 `#EDF2F7` | OK |
| `--color-on-surface` | `#1A1A2E` | Cockpit Dark `#1A1A2E` | OK |
| `--color-border` | `#E2E8F0` | Neutral 200 `#E2E8F0` | OK |
| `--color-muted` | `#718096` | Neutral 500 `#718096` | OK |
| `--fls-radius-sm` | `0.5rem` (8px) | mockup spec: 6px (`chips, badges`) | **Drift** |
| `--fls-radius-md` | `0.75rem` (12px) | mockup spec: 8px (`buttons, inputs`) | **Drift** |
| `--fls-radius-lg` | `1rem` (16px) | mockup spec: 12px (`cards, modals`) | **Drift** |
| `--fls-radius-pill` | inherited from default (`9999px`) | mockup spec: `999px` | OK (functionally identical) |
| `--fls-font-sans` | `"DM Sans", system-ui, sans-serif` | DM Sans body | OK |
| `--fls-font-display` | `"Outfit", system-ui, sans-serif` | Outfit headings | OK |
| `--fls-font-mono` | **missing** | IBM Plex Mono | **Missing** |
| `--color-success-light` etc. | **missing** | Success Light `#F0FFF4` etc. | **Missing** |

The brand doc itself names headings as `font-heading` and the mockup CSS reads `var(--font-heading)`. FLS's role-contract token is `--fls-font-display`, which is what `tailwind.components.css` uses (`font-display`) for `h1`–`h4`. Keep the name `--fls-font-display`; the rename is purely terminology and is out of scope here.

## Required additions (mono font, status-light tokens)

### Mono font

Add to **default** theme (`freedom_ls/themes/default/static/themes/default/theme.css`):

```css
@theme {
    /* …existing… */
    --fls-font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas,
        "Liberation Mono", "Courier New", monospace;
}

@theme inline {
    /* …existing… */
    --font-mono: var(--fls-font-mono);
}
```

Add to **first_class** theme:

```css
@theme {
    /* …existing… */
    --fls-font-mono: "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
}
```

(No `@theme inline` aliasing in first_class — the alias is established once in default and remains in effect.)

### Status `-light` tints

Hex values from the brand doc are reflected verbatim by the mockups (`colors-semantic.html`, `components-chips.html`, `components-feedback.html`). They are also identical to Tailwind's `green-50` / `yellow-50` / `red-50` / `blue-50` (Tailwind v3 historical scale), so the same hex values are reasonable defaults for the default theme too — they're a neutral, semantically-correct light tint for the existing default-theme `success`/`warning`/`error`/`info` hues.

Add to **both** themes (same hex values):

```css
@theme {
    /* …existing semantic tokens… */
    --color-success-light: #F0FFF4;
    --color-warning-light: #FFFFF0;
    --color-error-light:   #FFF5F5;
    --color-info-light:    #EBF8FF;
}
```

### `on-*-light` companions — recommendation: **add them**

The mockups use a *darker* shade of each semantic hue as the foreground on its Light background, not the role's `on-*` value:

| Background | Foreground in mockup | Note |
| --- | --- | --- |
| Success Light `#F0FFF4` | `#22543D` | dark green (`green-900`-ish) |
| Warning Light `#FFFFF0` | `#744210` | dark amber (`yellow-900`-ish) |
| Error Light `#FFF5F5` | `#742A2A` | dark red (`red-900`-ish) |
| Info Light `#EBF8FF` | `#2A4365` | dark blue (`blue-900`-ish) |

These appear in `components-chips.html`, `components-feedback.html`, and `colors-semantic.html`. The existing `--color-on-success: #FFFFFF` etc. would be illegible on a near-white tint, so new `on-*-light` tokens are needed to render the chip / alert text properly.

Add to **first_class**:

```css
@theme {
    --color-on-success-light: #22543D;
    --color-on-warning-light: #744210;
    --color-on-error-light:   #742A2A;
    --color-on-info-light:    #2A4365;
}
```

For **default**, the same dark shades read as a sensible neutral fallback (they harmonise with any solid hue close to the default's `success`/`warning`/`error`/`info`). Recommend matching values in default. Downstream themes that want a different palette can override.

```css
@theme {
    --color-on-success-light: #22543D;
    --color-on-warning-light: #744210;
    --color-on-error-light:   #742A2A;
    --color-on-info-light:    #2A4365;
}
```

The Tier-2 chip / alert classes (built later) then reduce to e.g. `bg-success-light text-on-success-light` and the `bg-success/15` opacity hack is retired.

## Radii alignment recommendation

The mockup spec is explicit: `6 / 8 / 12 / 999`. The current first_class file is `8 / 12 / 16 / 9999`, i.e. one step too round across the board.

Recommendation: **align first_class to the mockup**. The brand-doc text doesn't pin radii — only the design-system mockups do — but the mockups *are* the visual contract for Tier 2, so the tokens must drive the same numbers.

Apply in `freedom_ls/themes/first_class/static/themes/first_class/theme.css`:

```css
/* Shape — match design-system/radii.html */
--fls-radius-sm: 0.375rem;  /* 6px  — chips, badges */
--fls-radius-md: 0.5rem;    /* 8px  — buttons, inputs (default) */
--fls-radius-lg: 0.75rem;   /* 12px — cards, modals */
/* --fls-radius-pill inherited from default (9999px) — visually identical to 999px */
```

Drop the existing "bumped one step for the brand's rounder card treatment" comment — the design system explicitly walks that back.

`--fls-radius-pill` does not need redeclaring; default's `9999px` is functionally identical to the mockup's `999px`.

## Type scale — Tier-1 vs Tier-2 recommendation

Brand scale (Display / H1-H4) vs current `tailwind.components.css` `@layer base`:

| Brand | Brand size | Current FLS @layer base |
| --- | --- | --- |
| Display | `text-5xl` (48px) `font-bold` | not styled (no `display` element-level rule) |
| H1 | `text-4xl` (40px-ish) `font-bold` | `text-xl sm:text-2xl lg:text-4xl` `font-bold` |
| H2 | `text-3xl` (32px) `font-semibold` | `text-lg sm:text-xl lg:text-3xl` `font-bold` |
| H3 | `text-2xl` (24px) `font-semibold` | `text-base sm:text-lg lg:text-2xl` `font-bold` |
| H4 | `text-xl` (20px) `font-semibold` | `text-sm sm:text-base lg:text-xl` `font-bold` |

At `lg` breakpoint the current FLS rules **already match** the brand's heading sizes 1-for-1. The differences are:

1. Below `lg` the FLS scale steps down two notches; the brand doc explicitly endorses this for mobile ("Headings reduce by one step"). The FLS reduction is a step bigger than the brand notes call for, but it is *style-consistent* with the doc's intent.
2. FLS uses `font-bold` for every level; brand calls `font-semibold` for H2-H4.
3. There is no `Display` element rule (and no `Body Lg` / `Body Sm` / `Caption` / `Overline` element rules) — those are utility-class concerns rather than tag-level concerns.

Recommendation: **type-scale changes are out of scope for Tier-1, and best handled in Tier-2**. Reasons:

- Tier-1 is *tokens-only* per the master spec (§"Tier 2 — Semantic component classes"). Adjusting `font-weight` per heading level is a component-class concern, not a token concern.
- Default-theme `h1`-`h4` rules are already a sensible cross-brand baseline. Forcing `font-semibold` globally would regress the default theme's intent.
- The first_class brand needs its specific weight ladder. That fits Tier-2: the first_class theme can extend `tailwind.components.css` with weight overrides scoped to `font-display` (e.g. re-open `h2 { @apply font-semibold; }` inside `first_class/theme.css` once the Tier-2 mechanism is wired).
- Display, Body Lg/Sm, Caption, Overline are not element types — they're utility recipes (`text-5xl font-display font-bold tracking-tight` etc.) and belong in Tier-2 components or in template usage, not in Tier-1 tokens.

The **only Tier-1 typography change** is adding `--fls-font-mono` (above). Everything else lives in Tier-2.

## Hover variants — review note

Default theme derives hover variants via `color-mix` with `--fls-hover-mix-color: white` and `--fls-hover-mix-amount: 12%`, i.e. each hover token is the base role mixed 12% with white in OKLCH.

For first_class:

- `primary` `#283593` (Deep Indigo, very dark) → mixing with 12% white nudges it slightly lighter. This is the standard "lighten on hover for dark base" direction and reads correctly. **OK as-is.**
- `secondary` `#00CEC9` (Electric Teal, already bright) → mixing with 12% white desaturates and pushes it nearly to mint, which is **likely too washed-out** for a hover affordance on an already-light colour. Worth a Tier-2 visual review; an explicit darker `--color-secondary-hover` may read better.
- `accent` `#FF6B35` (Altitude Orange, mid-bright) → 12% white gives a soft peach; arguably OK but could feel under-energetic for a CTA. Worth eyeballing in Tier-2.
- `success`/`warning`/`error`/`info` → all reasonably dark or mid; the 12% white mix gives a workable hover. **OK as-is** unless QA disagrees.

Recommendation: **don't redeclare hover tokens in first_class for Tier-1**. Flag `secondary-hover` and `accent-hover` for review during Tier-2 component-class implementation, and override individually only if QA finds them flat. The hover tokens are a single-line override per role, so this is cheap to do later.

## Summary checklist of Tier-1 changes for both default and first_class

### `freedom_ls/themes/default/static/themes/default/theme.css`

- [ ] Add `--fls-font-mono` to `@theme` block (with platform-mono fallback stack).
- [ ] Add `--font-mono: var(--fls-font-mono);` alias in the `@theme inline` block.
- [ ] Add `--color-success-light: #F0FFF4;`
- [ ] Add `--color-warning-light: #FFFFF0;`
- [ ] Add `--color-error-light:   #FFF5F5;`
- [ ] Add `--color-info-light:    #EBF8FF;`
- [ ] Add `--color-on-success-light: #22543D;`
- [ ] Add `--color-on-warning-light: #744210;`
- [ ] Add `--color-on-error-light:   #742A2A;`
- [ ] Add `--color-on-info-light:    #2A4365;`

### `freedom_ls/themes/first_class/static/themes/first_class/theme.css`

- [ ] Add `--fls-font-mono: "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;`
- [ ] Add the same four `--color-*-light` tokens (identical hexes to default).
- [ ] Add the same four `--color-on-*-light` tokens (identical hexes to default).
- [ ] Re-set radii to match `radii.html`:
  - `--fls-radius-sm: 0.375rem;` (6px)
  - `--fls-radius-md: 0.5rem;`   (8px)
  - `--fls-radius-lg: 0.75rem;`  (12px)
  - `--fls-radius-pill` — leave inherited (9999px ≈ 999px).
- [ ] Drop the "bumped one step for the brand's rounder card treatment" comment; replace with a brief note that radii match `design-system/radii.html`.

### Master spec / Tier-1 contract

- [ ] Add `*-light` and `on-*-light` rows to the role-contract table in `1. spec.md` §"Colour roles — the public token contract".
- [ ] Add `--fls-font-mono` to the type-tokens section.

### Out of scope (deferred to Tier-2 or later)

- 50-900 neutral ramp — defer per master spec.
- Per-heading `font-weight` override (brand uses `font-semibold` for H2-H4) — Tier-2 first_class component override.
- Display / Body Lg / Body Sm / Caption / Overline utility recipes — template usage / Tier-2 docs.
- Hover-token overrides for `secondary` and `accent` in first_class — review during Tier-2 QA, override per-role only if needed.
