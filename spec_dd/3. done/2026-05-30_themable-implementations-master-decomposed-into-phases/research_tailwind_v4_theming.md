# Research: Tailwind v4 theming for downstream overrides

Context: Freedom LS ships `tailwind.input.css` (imports `tailwindcss` + `tailwind.components.css`) with a `@theme` block of semantic colour tokens (`--color-primary`, `--color-surface`, `--color-on-primary`, etc.) and component classes in `@layer components` (`btn-primary`, `chip-success`). We want a downstream Django project to override the theme without forking the input file.

## 1. `@theme` is partially overridable

Tailwind v4's `@theme` is additive across imports. Redeclaring a single token (`--color-primary: #...`) replaces only that variable; the rest of the upstream `@theme` survives. To wipe a whole namespace use the explicit reset: `--color-*: initial;` then redeclare. So a downstream `tailwind.input.css` can import the FLS bundle and add its own `@theme { --color-primary: ... }` block — that is the cleanest pattern.

Layer ordering is fixed: `@layer theme, base, components, utilities;`. `@theme` declarations land in the `theme` layer (before everything), so utilities that reference the tokens pick up downstream overrides without specificity gymnastics.

## 2. Multiple themes in one build

The maintainer-endorsed pattern (Adam Wathan, GH #15600 / #15199) is **not** to put runtime-swappable values inside `@theme`. Instead:

```css
@theme inline {
  --color-primary: var(--primary);   /* utility refers to a CSS var */
}

@layer base {
  :root              { --primary: oklch(60% 0.15 250); }
  [data-theme=bloom] { --primary: oklch(72% 0.18 350); }
  .dark              { --primary: oklch(70% 0.14 250); }
}
```

`@theme inline` is critical: without `inline`, Tailwind inlines the *resolved* token value at build time and downstream `data-theme` swaps do nothing. With `inline`, the utility class compiles to `color: var(--primary)` and follows the cascade at runtime. This is the v4-recommended approach and replaces v3 plugin-based theming.

Caveat (GH #15222, #16292): a `data-theme` attribute does *not* scope `@theme` itself — only regular CSS variables inside `@layer base`. Keep `@theme inline` thin and put real values behind plain CSS vars in `:root` / `[data-theme=…]`.

## 3. OKLCH palette derivation

Tailwind v4 does **not** auto-derive shades. Each step (`--color-primary-50` … `-950`) must be explicitly declared. v4's defaults are hand-tuned OKLCH values; if FLS wants `bg-primary-100` etc., we must ship 11 tokens per ramp. Practical options:

- Define only the semantic single-stop tokens we already use (`--color-primary`, `--color-primary-bold`) — current FLS approach, recommended for now.
- If a full ramp is wanted, generate it offline (uicolors.app, tints.dev, or a small build script using `culori`) and paste the 11 OKLCH values into `@theme`. Evil Martians' "OKLCH magic" article shows a runtime `oklch(var(--lightness) var(--chroma) var(--hue))` trick, but it is DIY and not v4 native.

## 4. Packaging Tailwind for a reusable Django package

Recommended consumer file (replaces "copy and edit"):

```css
/* downstream project's tailwind.input.css */
@import "tailwindcss";

/* Pull in FLS sources + components. Path resolves via the Python wheel
   site-packages location, or a symlink/asset-pipeline copy. */
@source "../../.venv/lib/python*/site-packages/freedom_ls/**/templates/**/*.html";
@import "../../.venv/lib/python*/site-packages/freedom_ls/tailwind.components.css";

/* Brand override */
@theme {
  --color-primary: #7C3AED;
  --color-primary-bold: #6D28D9;
}
```

Notes:
- `@source` accepts globs and is the v3 `content` replacement. It must be reachable from the build CWD; Django package paths under `site-packages` work but are awkward — many projects symlink into `node_modules/` or use an asset-pipeline copy. Document the resolved path in the install guide.
- Ship `tailwind.components.css` and the FLS template tree as Python package data (`MANIFEST.in` / `package-data`). No npm package required.
- Current FLS `@source "./freedom_ls/**/templates/**/*.html"` should stay (so internal dev still works) — downstream just adds its own `@source` lines.

## 5. Extending component classes downstream

`@layer components` cascades before `@layer utilities`, so utilities applied in HTML already win over FLS components. To *augment* a component class without rewriting it, the downstream `tailwind.input.css` simply re-opens it inside its own `@layer components`:

```css
@layer components {
  .btn-primary { @apply rounded-2xl shadow-sm; }
}
```

Both rules survive; later-declared properties win per the cascade. Avoid `@utility` here — that creates a Tailwind utility (with variant support) and is overkill for component tweaks. Reserve `@utility` for things downstream wants as `hover:`/`md:` variants.

Gotcha (GH #17082, #15139): `@apply` of project-defined utilities from inside `@layer components` is more restrictive in v4 — keep `@apply` to vanilla Tailwind utilities and theme tokens. The current FLS components file at `tailwind.components.css` is already compliant.

## 6. Pitfalls to plan around

- **`@source` and `.gitignore`** (GH #15452): v4 honours `.gitignore`. If FLS is installed under a path that any ancestor `.gitignore` excludes (`.venv/`, `node_modules/`), `@source` silently skips it. Use explicit `@source` globs.
- **Build-time only**: Tailwind v4 still scans at build. Runtime CSS-variable swaps work, but a new utility class name not present at build time is not generated.
- **`@theme inline` is the foot-gun**: forgetting `inline` is the #1 cause of "my dark mode doesn't switch" reports.
- **Load order**: `[data-theme=…]` beats `:root`, but a downstream stylesheet loaded *before* FLS will lose. Document order: `@import "tailwindcss"` → FLS components → downstream overrides last.
- **OKLCH browser support**: fine in evergreens; older browsers need a fallback ramp.

## Recommendation for the spec

1. Keep `@theme` in `tailwind.components.css` minimal and semantic (current shape is good).
2. Switch the FLS theme tokens to `@theme inline` referencing plain CSS vars in `:root`, so downstream gets both static override (redeclare `@theme`) **and** runtime swap (set a `data-theme` or override the underlying var) for free.
3. Replace the "copy `tailwind.input.css`" instruction with a documented 4-line consumer file: `@import "tailwindcss"; @source <fls templates>; @import <fls components>; @theme { ...overrides }`.
4. Defer full 50–950 ramps until a concrete need arises; ship the semantic two-stop palette only.

## Key findings vs. the six questions (TL;DR)

1. Yes, `@theme` is partially overridable; the `theme` layer comes first.
2. Use `@theme inline` + `[data-theme=…]` overrides in `@layer base`. Plugin themes are gone.
3. No automatic 50–950 derivation; declare each shade or generate offline.
4. Consumer composes their own `tailwind.input.css` that `@import`s FLS components and `@source`s FLS templates from `site-packages`; no npm package needed.
5. Re-open the class inside `@layer components` in the downstream file; do not switch to `@utility`.
6. Watch `.gitignore` swallowing `@source`, missing `inline`, and load order.

## References

- Tailwind v4 — Theme variables: https://tailwindcss.com/docs/theme
- Tailwind v4 — Functions & directives: https://tailwindcss.com/docs/functions-and-directives
- Tailwind v4 — Adding custom styles: https://tailwindcss.com/docs/adding-custom-styles
- Tailwind v4 — Colors: https://tailwindcss.com/docs/colors
- GH Discussion #15600 — CSS variables for multiple themes: https://github.com/tailwindlabs/tailwindcss/discussions/15600
- GH Discussion #15199 — data-theme CSS configuration: https://github.com/tailwindlabs/tailwindcss/discussions/15199
- GH Discussion #15222 — Multi-theme with v4: https://github.com/tailwindlabs/tailwindcss/discussions/15222
- GH Discussion #16215 — Several themes in one project: https://github.com/tailwindlabs/tailwindcss/discussions/16215
- GH Discussion #16292 — @theme via data-theme: https://github.com/tailwindlabs/tailwindcss/discussions/16292
- GH Discussion #17082 — @apply with @layer base/components in v4: https://github.com/tailwindlabs/tailwindcss/discussions/17082
- GH Issue #15452 — @source ignores .gitignore subdirectories: https://github.com/tailwindlabs/tailwindcss/issues/15452
- Simon Vrachliotis — Tailwind v4 Multi-Theme Strategy: https://simonswiss.com/posts/tailwind-v4-multi-theme
- Jake Bukuts — Theming with Tailwind v4: https://www.jbukuts.com/posts/theming-tailwind-v4
- Evil Martians — Dynamic themes with OKLCH: https://evilmartians.com/chronicles/better-dynamic-themes-in-tailwind-with-oklch-color-magic
- shadcn/ui — Tailwind v4 guide: https://ui.shadcn.com/docs/tailwind-v4
- Tailkits — @source directive guide: https://tailkits.com/blog/tailwind-at-source-directive/
- tints.dev — palette generator: https://www.tints.dev/
- uicolors.app — OKLCH Tailwind palette tool: https://uicolors.app/tailwind-colors
