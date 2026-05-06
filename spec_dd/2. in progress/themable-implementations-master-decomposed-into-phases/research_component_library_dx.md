# Component-library DX research: lessons for Freedom LS theming

Freedom LS is a Django 6 + Tailwind v4 + HTMX + django-cotton library that gets installed into other Django projects. Downstream sites (e.g. "Bloom" — soft, purple, rounded; "FirstClass" — corporate, polished) need to rebrand without forking templates. This is a survey of how mature component libraries handle that, what their consumers complain about, and what FLS should steal.

## Per-system findings

### 1. shadcn/ui — copy-paste + CSS variables
- **Theming surface:** semantic CSS variables (`--background`, `--foreground`, `--primary`, `--primary-foreground`, `--radius`) plus *the actual component source code in your repo*. Variants come from `class-variance-authority`. There is no template hook layer because *the template is the hook* — you own it.
- **What people love:** trivial palette swap; `--radius` instantly re-shapes everything; no fight with library specificity; the "background/foreground" pairing makes contrast obvious.
- **Common complaints:** ownership cost. "It becomes YOUR component, and if there's a problem, it's YOUR problem." No `npm update` for upstream fixes; improvements have to be re-applied by hand. Bundle/codebase grows; forks fragment.
- **Lesson for FLS:** the *variable layer* (semantic colour pairs + radius + spacing scale) is mandatory. The "copy the whole template into your project" model is the escape hatch — but FLS should resist *requiring* it for routine rebranding.

### 2. daisyUI — themes as CSS-variable bundles, `data-theme` switching
- **Theming surface:** named themes are just blocks of CSS variables. `data-theme="bloom"` on `<html>` swaps everything. Multiple themes can coexist on one page (nested `data-theme`).
- **Strengths:** dark/light/brand themes are symmetric — none is privileged. Adding a theme is "a few lines of CSS variables." Fits Tailwind v4 perfectly.
- **Weakness:** the variable surface is fixed. If a downstream wants to change *structure* (e.g. card padding, button icon position), variables can't help.
- **Lesson for FLS:** model brands as named token bundles. `data-theme` switching is a cheap multi-tenant win — Freedom LS is already site-aware, so each `Site` can declare a theme name.

### 3. Bootstrap / Bootswatch — the limits of "just override variables"
- **Theming surface:** SCSS variable overrides, plus a second `_bootswatch.scss` for "more extensive structural changes." That second file exists *because* variables alone weren't enough.
- **Complaints:** strict import order; you can't change a component's markup without forking; "I needed to change the gap inside the card and there was no way without custom CSS" is a chronic pattern.
- **Lesson for FLS:** plan for the case variables can't cover. Bootstrap's two-file split (`_variables` + `_bootswatch`) is essentially Tier 1 + Tier 2. Don't pretend Tier 2 isn't needed.

### 4. Material Design 3 — semantic token naming
- **Theming surface:** three layers — *reference* (raw palette like `palette.blue.40`), *system/semantic* (`md.sys.color.surface`, `md.sys.color.on-surface`, `on-primary-container`), *component* (`md.comp.button.container.color` -> points at a system token).
- **The big idea:** the `on-X` convention encodes contrast pairing into the name. Components reference *roles* ("surface", "primary"), never raw colours. Re-themes cascade automatically because component tokens are aliases, not values.
- **Lesson for FLS:** name tokens by *role* (`--fls-color-surface`, `--fls-color-on-surface`, `--fls-color-accent`, `--fls-color-on-accent`, `--fls-color-danger`), never by hue. Pair every fill with its `on-*` for text/icons to kill contrast bugs.

### 5. Radix UI — headless primitives, behaviour split from style
- **Theming surface:** *none, by design*. Radix ships ARIA, focus management, keyboard nav, state — zero visuals. You wire your own classes.
- **Why this matters even for a non-React stack:** the architectural split — "logic and accessibility from the library, visuals from you" — is what shadcn, React Aria, Ark UI all copy. It eliminates specificity wars.
- **Lesson for FLS:** cotton components should expose *slots*, not baked-in chrome. A `<c-card>` should provide structure + ARIA + HTMX wiring; downstreams decorate it via tokens (Tier 1) and overridable inner classes (Tier 2). Don't bury behaviour inside heavily-styled markup that consumers then have to fork to restyle.

### 6. Stripe / Primer / Atlassian — three-tier token convention
Cross-system consensus: *primitive -> semantic (alias) -> component*. Primer explicitly forbids raw hex/px in components — semantic only. Atlassian publishes tokens as JSON, versioned, with a deprecation lifecycle. Two clear pitfalls everyone warns about: **over-tokenising** (tokens for every property of every component -> "token bloat", unfindable, unmaintained) and **leaky primitive names** (calling a token `blue-500` breaks the moment Bloom's brand stops being blue).

## Recommended layered theming surface for FLS

**Tier 1 — Design tokens (CSS custom properties on `:root` / `[data-theme="..."]`).** Small, semantic, paired. Suggested set:
- Colour roles: `surface`, `on-surface`, `surface-muted`, `accent`, `on-accent`, `accent-muted`, `danger`, `on-danger`, `success`, `on-success`, `border`, `focus-ring`.
- Shape: `--fls-radius-sm/md/lg`, `--fls-radius-pill`.
- Density: `--fls-space-1..6`, `--fls-control-height`.
- Type: `--fls-font-sans`, `--fls-font-display`, `--fls-text-scale`.

Brands ship as a single CSS file: `bloom.css` defines `[data-theme="bloom"] { ... }`. Tailwind v4's `@theme` maps these into utilities.

**Tier 2 — Component-level semantic classes consumers can extend.** Every cotton component exposes a stable, *documented*, namespaced root class (`fls-card`, `fls-card__body`, `fls-btn`, `fls-btn--primary`, `fls-chip`, `fls-chip--success`). Variants are class modifiers, not template branches. Downstreams add a sibling stylesheet that targets these to tweak shape, density, icon position — without copying the template. Treat these classnames as **public API** with deprecation rules.

**Tier 3 — Template overrides for genuine restructure.** django-cotton + Django's template loader already give us this for free: a downstream project drops `templates/cotton/card.html` to fully replace it. Document *which* templates are intended override points (top-level layout shells, dashboard header, empty states) and which are internal (form rows, validation chips). Provide named slots in overridable templates so consumers re-skin without reimplementing logic.

## Pitfalls to avoid explicitly

- **Over-tokenising.** Don't ship `--fls-card-header-icon-margin-right`. If three components don't share a value, it's not a token — it's a class.
- **Primitive-named tokens.** No `--fls-blue-500` in component code. Components see roles only. Keep raw palettes private to brand files.
- **Leaky internal classes.** If `fls-card__inner-flex-2` ends up in user CSS, refactors break consumers. Mark internal classes with a `_` prefix or `data-fls-internal` and exclude from the public contract.
- **Forcing forks.** If a common rebrand need (button radius, card density, accent hue, logo, sidebar order) requires copying a template, Tier 1/2 has failed — add a token or a variant instead.
- **Behaviour baked into chrome.** Keep HTMX attributes, ARIA, and form wiring in the *outer* component; let inner presentation be overridable. Radix's lesson.
- **Theme as the only switch.** Allow `Site` -> theme mapping (multi-tenant), but also allow per-deployment static override via env/settings, so devs can iterate without DB writes.

## References

- shadcn/ui theming: https://ui.shadcn.com/docs/theming
- "What I DON'T like about shadcn/ui": https://leonardomontini.dev/shadcn-ui-use-with-caution/
- daisyUI themes: https://daisyui.com/docs/themes/
- daisyUI colours: https://daisyui.com/docs/colors/
- Bootswatch help (variable + `_bootswatch.scss` split): https://bootswatch.com/help/
- MD3 design tokens overview: https://m3.material.io/foundations/design-tokens/overview
- MD3 colour roles and on-* naming: https://developer.android.com/design/ui/wear/guides/styles/color/roles-tokens
- Radix Primitives intro: https://www.radix-ui.com/primitives/docs/overview/introduction
- How Radix changed how we think of components: https://blog.rad-ui.com/blog/frontend-architecture/how-radix-changed-way-we-think-of-components
- Primer design tokens guide: https://github.com/primer/primitives/blob/main/DESIGN_TOKENS_GUIDE.md
- Atlassian design tokens: https://atlassian.design/foundations/design-tokens/
- Token bloat / over-tokenising: https://designtokens.substack.com/p/common-mistakes-in-design-tokens
- Token naming best practices: https://www.netguru.com/blog/design-token-naming-best-practices
