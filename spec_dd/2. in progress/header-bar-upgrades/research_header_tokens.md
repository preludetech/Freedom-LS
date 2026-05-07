# Research: Theming the header bar via design tokens

Scope: decide how to expose the FLS header bar (`<header>` + user-menu trigger) to themes so that `default` keeps the current `bg-primary / text-on-primary` look while `first_class` can render a white header with a black foreground and a primary-coloured profile pill — without polluting the global token namespace or breaking the existing `--color-*` contract.

---

## TL;DR recommendation

1. **Add a small set of component-scoped tokens** under the existing `--color-*` namespace so Tailwind v4 utility classes are auto-generated. Concretely:
   - `--color-header` (background)
   - `--color-on-header` (foreground / title / nav text)
   - `--color-header-action` (profile-pill / action-button background)
   - `--color-on-header-action` (profile-pill foreground)
   - `--color-header-border` *(only if the design needs a hairline; skip for now)*
2. **Default values alias the role tokens.** In `default/theme.css` set `--color-header: var(--color-primary)` and `--color-on-header: var(--color-on-primary)` via `@theme inline` — existing visual behaviour is preserved, sparse themes that only override brand roles continue to work, and `first_class` overrides only the four component tokens to flip the design.
3. **Skip dedicated hover / focus tokens for now.** The existing `color-mix` hover machinery and `--color-focus-ring` already cover what the header needs. Only introduce `--color-header-hover` if the brand requires a hover that is *not* a 12% mix of the header bg.
4. **Defer the scrolled/translucent token.** Per `research_scroll_header.md` we are not committing to a translucent state in this phase. If/when we do, add `--color-header-scrolled` *only* if opacity-on-the-base-token isn't sufficient (e.g. you want a different base hue when stuck). Otherwise prefer `bg-header/85` + a `backdrop-blur-*` utility, gated by a `[data-stuck]` selector.
5. **Naming convention: short, role-shaped, no `-bg` suffix.** Tailwind v4 already maps `--color-header` to `bg-header`, `text-header`, `border-header`, etc. Adding `-bg` produces redundant `bg-header-bg`. Stick with the role/`on-role` pattern that the rest of the system uses.

The opinionated short version: four tokens, aliased to brand roles by default, overridden in `first_class` — no new naming convention.

---

## 1. Component-scoped vs role-based tokens

### Two valid token tiers

Mature design systems generally separate tokens into at least two tiers:

| Tier | Other names | Role in the system | Examples |
| --- | --- | --- | --- |
| **Semantic / role** | "alias", "system", "color role" | Cross-cutting meaning (brand, surface, status). Rarely reach into a single component. | `--color-primary`, `--color-surface`, `--color-on-primary` |
| **Component** | "component-specific", "scoped" | Scoped to one UI part. Their *default value* is an alias of a semantic token. | `--color-header`, `--color-on-header`, `--color-button-primary-bg` |

The point of a component tier is that **the component can be re-skinned without disturbing the brand-wide role**. Re-pointing `--color-primary` would also recolour buttons, links, focus rings, chip tints, etc. A component-tier token gives us a single, narrow override surface.

### What the major systems do

- **Material 3** uses three formal layers — *reference* (raw palette) → *system* (`md.sys.color.primary`, `md.sys.color.on-primary`) → *component* (`md.comp.top-app-bar.container-color`, `md.comp.top-app-bar.on-scroll.container-color`, `md.comp.top-app-bar.headline-color`). The TopAppBar spec defines roughly a dozen component tokens, and *every one of them resolves to a system token by default* (`container-color → surface`, `headline-color → on-surface`, etc.). Theming overrides happen at any layer.
- **Adobe Spectrum** uses `--spectrum-component-*` tokens that alias `--spectrum-alias-*` which alias `--spectrum-global-*`. The naming is verbose but the layering is the same: components own their slot and pull a default from the alias tier.
- **Atlassian Design Tokens** distinguish "foundational" (`color.background.brand.bold`) from component (`color.background.button.primary`). Header / top-nav components define their own tokens (e.g. `elevation.surface.sunken` for the page header strip) that map into foundational tokens.
- **Radix Themes / Radix Colors** is the outlier: it leans on a 12-step semantic scale (`accent.9`, `gray.2`, etc.) rather than per-component tokens. Components consume the scale directly. This works for Radix because every step has a documented use ("9 = solid backgrounds"), but it puts more design decisions into component CSS rather than tokens.
- **IBM Carbon** publishes explicit component tokens under categories like `header-background`, `header-text`, `header-icon` for the UI shell — and they alias the global theme tokens (`$background`, `$text-primary`) by default. Carbon's UIShell is the closest analogue to our header bar and uses essentially the schema we propose.

### Conclusion

Material 3, Carbon, Atlassian, Adobe Spectrum all do the same thing: **the header (top app bar / UIShell / page header) gets its own small token group, defaulted to brand/system tokens.** That is the convention to follow. Radix's "scale only" approach is interesting but doesn't fit our `--color-on-X` pairing convention or our existing role tokens.

---

## 2. How many tokens does the header actually need?

Working from the current markup (`partials/header_bar.html`, `partials/header_bar_user_menu.html`) and the desired `first_class` design.

### Confirmed — add now

| Token | Used for | Justification |
| --- | --- | --- |
| `--color-header` | `<header>` background | Currently `bg-primary`. Needed to flip to white in `first_class`. |
| `--color-on-header` | Site title, dropdown trigger label, dropdown caret, mobile user icon | Currently `text-on-primary`. Needed to flip to black in `first_class`. |
| `--color-header-action` | Profile pill / dropdown trigger background | New surface. In default it can stay transparent (no chip). In `first_class` it becomes `--color-primary`. |
| `--color-on-header-action` | Profile pill text + icon | Pairs with the action token. In `first_class` it's white; in default it inherits `--color-on-header`. |

That's four tokens — the minimum to express both designs.

### Deliberately not adding

- `--color-header-hover` — the dropdown trigger hover today is "lighter mix of `--color-on-primary` background". The existing `color-mix` machinery (`--fls-hover-mix-color`, `--fls-hover-mix-amount`) already produces a coherent hover for any solid colour, and we don't have evidence the brand needs a non-standard mix. Add later if QA finds the auto-mix wrong.
- `--color-header-focus-ring` — focus is already centralised on `--color-focus-ring`. The header is just another focusable surface; no need to special-case unless the chosen ring is illegible against `--color-header` (testable per-theme; fix with an `@theme inline` override of `--color-focus-ring` if it ever happens).
- `--color-header-border` — current header has `shadow-md` not a border. Adding a border token now is speculative. If the new design adds a hairline (`border-b`) we can introduce it, but YAGNI for the moment.
- `--color-header-scrolled` / `--color-header-bg-scrolled` — see §5.
- Separate "icon" vs "text" foreground tokens — Material 3 splits `headline-color` and `leading-icon-color`, but in our header the icons inherit `currentColor` from the parent's text utility, so a single `--color-on-header` is enough. Split later if we need a brand to colour the icons differently from the text.

### Why four (not two)

We could stop at `--color-header` / `--color-on-header` and re-use `--color-primary` / `--color-on-primary` for the profile pill. That works for `first_class` but couples the pill colour to the brand role globally — any later theme that wants `bg-primary` ≠ "header action colour" (e.g. a theme where primary is a pale pastel that wouldn't read as a button) has no override surface. Splitting gives us that surface for the price of two extra default-aliases.

---

## 3. Default values: "alias by default, override when needed"

### Standard pattern

Every system listed in §1 ships **component tokens that alias semantic tokens by default**. The override surface is the component token; the *value* defaults via the alias. In CSS custom properties this is simply:

```css
@theme inline {
    --color-header: var(--color-primary);
    --color-on-header: var(--color-on-primary);
    --color-header-action: transparent;            /* no pill in default */
    --color-on-header-action: var(--color-on-header);
}
```

Notes:

- **`@theme inline` is the right block** for these, not bare `@theme`. `@theme inline` keeps the alias dynamic — overriding `--color-primary` later still propagates to `--color-header`. A bare `@theme` block freezes the value at parse time. This matches how the existing file already aliases `--radius-*` and `--font-*`.
- **`--color-header-action: transparent`** means the default theme renders no pill background, matching today's look. `first_class` overrides to `var(--color-primary)`.
- **Sparse-theme principle preserved.** `first_class/theme.css` only redeclares the four `--color-header*` tokens plus its existing brand overrides. Themes that don't care about the header continue to inherit the default's primary-coloured bar.

### Don't

- Don't put the aliases in the bare `@theme` block — they would not re-resolve when a sub-theme overrides `--color-primary`.
- Don't hard-code a hex value for the alias (e.g. `--color-header: #2B6CB0`). That's a copy of `--color-primary` and silently desyncs the moment someone tweaks the brand.
- Don't define the alias inside a `:root` selector outside `@theme`. Tailwind v4's utility generator only sees variables declared inside `@theme` blocks — a bare `:root` declaration won't produce `bg-header`.

---

## 4. Tailwind v4 specifics

### Utility generation

Tailwind v4 generates colour utilities from any variable named `--color-<name>` declared in a `@theme` (or `@theme inline`) block. So:

| Token | Generated utilities |
| --- | --- |
| `--color-header` | `bg-header`, `text-header`, `border-header`, `ring-header`, `outline-header`, `fill-header`, `stroke-header`, `from-header` / `to-header` / `via-header`, `shadow-header`, `accent-header`, `caret-header`, `decoration-header`, `divide-header`, `placeholder-header` |
| `--color-on-header` | same list with `on-header` |
| `--color-header-action` | same list with `header-action` |
| `--color-on-header-action` | same list with `on-header-action` |

That's why we **don't suffix `-bg`**: `bg-header-bg` is redundant. Tailwind already knows the property from the utility prefix; the variable just supplies the value.

### Opacity modifiers

Tailwind v4's `bg-header/85` syntax works on any `--color-*` variable provided the value is itself a colour Tailwind can mix (hex, rgb, oklch, named). It does **not** work transparently when the variable's value is `transparent`. That's fine for us because:

- `bg-header/85` operates on `--color-header`, which always resolves to a real colour.
- The transparent default for `--color-header-action` is consumed via `bg-header-action` directly, no opacity modifier needed.

### Ordering & cascade gotchas

- **Themes after default.** `tailwind.input.css` already loads default tokens → components → active theme. New header tokens follow that order automatically.
- **`@theme inline` ordering.** All `@theme inline` aliases must come *after* the variables they reference are declared (or in the same block — Tailwind resolves within the merged `@theme` graph). Putting `--color-header: var(--color-primary)` in the same `@theme inline` block as the existing radius/font aliases is correct.
- **`@theme` blocks merge across files.** Defining `--color-header` in `default/theme.css` and overriding in `first_class/theme.css` works because Tailwind merges all `@theme` blocks before generating utilities.
- **Don't shadow with `@layer base { :root { … } }`.** If a theme tries to redeclare `--color-header` in `:root` rather than `@theme`, Tailwind will still emit the *original* `bg-header` utility but the cascade will override the *value* at runtime. That works for runtime colour but is inconsistent and breaks any code that introspects the theme. Keep all overrides inside `@theme` blocks.
- **Naming collision.** `--color-on-header` collides with nothing in the existing token list. `--color-header` does not collide with `--color-header-bg` or similar. Verified against both `theme.css` files.

### Tailwind config

No JS config file is involved — this is Tailwind v4 CSS-first. No `tailwind.config.js` change required.

---

## 5. Sticky / scroll-state interactions

`research_scroll_header.md` argues we should *not* commit to translucency in this phase. If/when we do:

### Option A — opacity utility (preferred)

Use the existing token plus a Tailwind opacity modifier:

```html
<header class="bg-header [&[data-stuck]]:bg-header/80 [&[data-stuck]]:backdrop-blur-md">
```

No new token. Works for any theme that defines `--color-header`. The blur amount and opacity are visual decisions, not brand decisions, so they don't need to be tokenised.

### Option B — separate `--color-header-scrolled` token

Add a token only if the brand needs a *different hue* when scrolled — e.g. default stays `bg-primary` solid, but `first_class` wants white-translucent that becomes a subtle indigo wash when content scrolls under it. That's a real but narrow case.

If we get there, add:

```css
@theme inline {
    --color-header-scrolled: var(--color-header);   /* same hue by default */
}
```

…and consume via `[&[data-stuck]]:bg-header-scrolled/80`.

### Recommendation

**Defer.** Don't add `--color-header-scrolled` until a brand asks for it. Material 3 *does* tokenise this (`md.comp.top-app-bar.on-scroll.container-color`) but they have many app-bar variants; we have one. YAGNI now, easy to add later because the rest of the schema is already in place.

---

## 6. Reference implementations

### Material Design 3 — Top App Bar

- Tokens (selected): `md.comp.top-app-bar.small.container-color`, `md.comp.top-app-bar.small.headline-color`, `md.comp.top-app-bar.small.leading-icon-color`, `md.comp.top-app-bar.small.trailing-icon-color`, `md.comp.top-app-bar.small.on-scroll.container-color`.
- Each component token resolves to a system token (`container-color → md.sys.color.surface`, `headline-color → md.sys.color.on-surface`).
- Multiple variants (small / center-aligned / medium / large) reuse the same role names with different defaults — exactly the pattern we'd extend to e.g. an admin sub-header later.
- Docs: <https://m3.material.io/components/top-app-bar/specs>

### IBM Carbon — UI Shell

- Header tokens: `header-background`, `header-text`, `header-icon`, `header-hover`, `header-menu-item-hover`, `header-border`. Each defaults to a global theme token.
- Carbon themes (`white`, `g10`, `g90`, `g100`) override these tokens to flip the shell from light to dark — same problem we're solving with `default` vs `first_class`.
- Docs: <https://carbondesignsystem.com/elements/color/tokens/> (search "header-").

### Atlassian Design System — Page Header / Banner

- Tokens like `elevation.surface`, `color.text`, `color.background.brand.bold` are consumed by the page header. Atlassian publishes per-component token mappings showing which foundational token each surface uses.
- Useful as a counter-example: Atlassian *minimises* component-specific tokens and pushes designers toward foundational tokens. Their header doesn't have its own `header-bg` — it consumes `elevation.surface` directly. Works for them because their visual language is more uniform than ours; not a model we should follow, but worth knowing.
- Docs: <https://atlassian.design/foundations/color-new/color-tokens>

### Adobe Spectrum

- Per-component CSS custom properties such as `--spectrum-headerbar-background-color`. Defaults alias `--spectrum-alias-background-color-primary`. Themes override at the alias layer or the component layer depending on scope of change.
- Docs: <https://spectrum.adobe.com/page/design-tokens/>

### Radix Themes

- No header-specific tokens; the app-bar consumes the 12-step `gray` / `accent` scale directly. Listed for contrast — this is the architectural alternative we're explicitly not adopting because it doesn't compose with our `--color-on-X` pairing.
- Docs: <https://www.radix-ui.com/themes/docs/theme/color>

---

## Reference URLs

- Material 3 — Top App Bar specs: <https://m3.material.io/components/top-app-bar/specs>
- Material 3 — Token system overview: <https://m3.material.io/foundations/design-tokens/overview>
- IBM Carbon — Color tokens: <https://carbondesignsystem.com/elements/color/tokens/>
- IBM Carbon — UI Shell theming: <https://carbondesignsystem.com/components/UI-shell-header/usage/>
- Atlassian Design — Color tokens: <https://atlassian.design/foundations/color-new/color-tokens>
- Adobe Spectrum — Design tokens: <https://spectrum.adobe.com/page/design-tokens/>
- Radix Themes — Color: <https://www.radix-ui.com/themes/docs/theme/color>
- Tailwind v4 — Theme variables: <https://tailwindcss.com/docs/theme>
- Tailwind v4 — `@theme` directive and `@theme inline`: <https://tailwindcss.com/docs/functions-and-directives#theme-directive>
- W3C Design Tokens Community Group spec (token tiering vocabulary): <https://tr.designtokens.org/format/>
