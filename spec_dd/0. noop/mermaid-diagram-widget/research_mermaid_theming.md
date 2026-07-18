# Research: theming Mermaid.js diagrams to FLS design tokens

Scope: how to make a `c-mermaid` cotton component render diagrams that visually match
the active FLS theme (CSS-custom-property token bundle), proportional to an
idea-refinement pass, not a full spec.

## 0. Grounding in FLS's existing patterns

- FLS themes are `@theme { --color-*: ... }` blocks (Tailwind v4), one fixed palette
  per site, no runtime light/dark toggle, no `.dark`/`data-theme` rules today
  (`freedom_ls/themes/default/static/themes/default/theme.css`). Role tokens:
  `--color-primary/-on-primary`, `--color-secondary/-on-secondary`,
  `--color-accent/-on-accent`, `--color-surface`, `--color-surface-2`,
  `--color-on-surface`, `--color-border`, `--color-muted`,
  `--color-success/warning/error/info` (+ `-on-*`), plus `--fls-font-sans` /
  `--fls-font-mono` (aliased to Tailwind's `--font-sans` / `--font-mono` via
  `@theme inline`).
- The nearest sibling widgets are `cotton/equation.html` (KaTeX, client-side render via
  an Alpine component, vendored library at
  `freedom_ls/content_engine/static/content_engine/vendor/katex/`, `overflow-x-auto` on
  a focusable wrapper) and `cotton/code-block.html` (same `overflow-x-auto` +
  `focus:outline-none focus:ring-2 focus:ring-focus-ring` pattern). A `c-mermaid`
  component should follow the same shape: vendored JS (no CDN — matches KaTeX and the
  project's CSP posture), an Alpine component that renders client-side from a raw-text
  slot, `overflow-x-auto` for wide diagrams, and the same accessible-wrapper
  conventions.
- Course content is author-supplied markdown, sanitised before reaching the slot (see
  the sanitiser comments in `equation.html`/`code-block.html`). This matters directly
  for mermaid's init-time security options (§1, §4).

## 1. Mermaid's theming mechanisms

Mermaid ships five built-in themes settable via `mermaid.initialize({ theme })`:
`default`, `neutral` (built for black/white print), `dark`, `forest`, and `base`. Of
these, **only `base` is meant to be customized** — it's the "blank canvas" theme whose
colors are driven entirely by the `themeVariables` object passed alongside it. The
other four are fixed palettes; you can nudge them with `themeCSS` but you can't cleanly
retarget their whole palette to arbitrary tokens.
[Mermaid theme config docs](https://mermaid.js.org/config/theming.html)

```js
mermaid.initialize({
  theme: "base",
  themeVariables: {
    primaryColor: "#2B6CB0",
    primaryTextColor: "#FFFFFF",
    // ...
  },
});
```

Two other mechanisms exist and are complementary, not alternatives to `base` +
`themeVariables`:

- **`themeCSS`** — a raw CSS string injected into the rendered SVG's `<style>`, applied
  with the highest specificity (overrides `themeVariables`-derived rules and
  `classDef`s). Useful for the handful of things `themeVariables` doesn't expose
  (e.g. a hover pseudo-class, a `stroke-dasharray`), not for bulk palette mapping.
  [Mermaid theme config docs](https://mermaid.js.org/config/theming.html)
- **Diagram frontmatter** (`%%{init: {...}}%%` at the top of the diagram source) can
  set `theme`/`themeVariables`/`themeCSS` *per diagram*. **Do not honour this from
  author content** — see the security note below.

**Security note (directly relevant since diagram source is author-supplied markdown):**
`fontFamily`, `themeCSS` and `altFontFamily` were the subject of a CSS-injection
advisory — a crafted value could escape the diagram's scoping (via stylis `&`
handling) and deface the page or exfiltrate DOM attributes through CSS `:has()`
selectors. Fixed in **mermaid 11.15.0 / 10.9.6**. Mitigation: pin to a patched version
*and* set `secure: true` (the default list includes `themeCSS`, `fontFamily`) or
`securityLevel: 'sandbox'` so that if a diagram's own frontmatter tries to set these
keys, the init-time (trusted, server/JS-controlled) values win instead.
[GHSA-87f9-hvmw-gh4p](https://github.com/mermaid-js/mermaid/security/advisories/GHSA-87f9-hvmw-gh4p)
Given course markdown already goes through a sanitiser before reaching the widget's
slot, this is a second, independent belt-and-braces control worth keeping — pin
`>=11.15.0` and set `secure: true` when the mermaid init call is wired up.

**Version floor:** the idea note calls out wanting "herringbone" (fishbone/Ishikawa)
diagrams — these landed in **mermaid v11.12.3**. Current npm `mermaid` is **11.16.0**
(≥ both the Ishikawa floor and the CSS-injection fix), so pin to `^11.15.0` at minimum,
ideally latest 11.x.
[Ishikawa diagram docs](https://mermaid.js.org/syntax/ishikawa.html) ·
[npm mermaid](https://www.npmjs.com/package/mermaid)

## 2. Driving mermaid colors from FLS's CSS custom properties

**`themeVariables` values must be resolved colors (hex/rgb), not `var(--...)`
strings.** This is not yet supported and is explicitly an open, "Status: Approved but
unimplemented" feature request:
[#6677 "Accept CSS variables for theme"](https://github.com/mermaid-js/mermaid/issues/6677),
[#6860 "Allow CSS Variables in themeVariables"](https://github.com/mermaid-js/mermaid/issues/6860)
(a draft PR, [#6775](https://github.com/mermaid-js/mermaid/pull/6775), exists but is
unmerged/WIP). The reason is structural, not incidental: mermaid derives most
`themeVariables` (borders, hover/secondary/tertiary shades, text-on-color contrast)
from a small set of base colors using a colour-math library (khroma-style
lighten/darken/invert/adjust-hue operations) **at `initialize()` time**. That math
needs a real color value to operate on; a `var(--color-primary)` string is opaque to
it and only hex colors are recognized by the parser.

**Reliable approach:** resolve FLS tokens via `getComputedStyle` on the document (or
the widget's own element, to respect any scoped overrides) *before* calling
`mermaid.initialize()` (or before `mermaid.run()`/`render()` for a per-widget init),
and feed the resolved strings into `themeVariables`:

```js
const cssVar = (name, fallback) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

mermaid.initialize({
  startOnLoad: false,
  theme: "base",
  themeVariables: {
    primaryColor: cssVar("--color-primary", "#2B6CB0"),
    primaryTextColor: cssVar("--color-on-primary", "#FFFFFF"),
    lineColor: cssVar("--color-border", "#D1D5DB"),
    // ...
  },
});
```

This is the pattern the community has converged on for CSS-variable-driven mermaid
theming (mkdocs-material and others use exactly this `getComputedStyle` helper).
[mkdocs-material discussion #4582 "How to modify Mermaid CSS"](https://github.com/squidfunk/mkdocs-material/discussions/4582)

Practical consequence for FLS: because tokens are resolved once at init, a
single page-level `mermaid.initialize()` call (run once, e.g. from a small init script
loaded alongside the vendored bundle) is sufficient for a static, single-theme-per-site
page — there's no need to re-resolve per-diagram unless a diagram is rendered before
the stylesheet is applied (unlikely; theme CSS is a `<link>` in `<head>`).

## 3. Key `themeVariables` and a suggested FLS mapping

Only mapping the variables that matter for a flat, single-palette theme (skipping
diagram-type-specific extras like `pie1..pie12`, gantt bar colors, etc. — leave those
at their `base`-derived defaults unless a later pass needs them).

| mermaid `themeVariables` key | Purpose | Suggested FLS token |
|---|---|---|
| `primaryColor` | Node fill; other colors derive from this | `--color-primary` |
| `primaryTextColor` | Text on primary-filled nodes | `--color-on-primary` |
| `primaryBorderColor` | Border on primary nodes | `--color-primary` (or a slightly darker mix if it reads too flat) |
| `secondaryColor` | Alternate node fill (derived by default) | `--color-secondary` |
| `secondaryTextColor` | Text on secondary fill | `--color-on-secondary` |
| `tertiaryColor` | Third node fill, also backs cluster/error boxes by default | `--color-surface-2` |
| `tertiaryTextColor` | Text on tertiary fill | `--color-on-surface` |
| `background` | Base mermaid derives contrast off of | `--color-surface` |
| `mainBkg` | Flowchart/class/sequence object background | `--color-surface` |
| `nodeBorder` | Node perimeter color (defaults to `primaryBorderColor`) | `--color-border` |
| `lineColor` | Edges/arrows | `--color-muted` or `--color-border` (test both — `border` often reads too faint for arrows) |
| `clusterBkg` | Subgraph background | `--color-surface-2` |
| `clusterBorder` | Subgraph border | `--color-border` |
| `edgeLabelBackground` | Background chip behind edge labels | `--color-surface` |
| `titleColor` | Diagram/sequence title text | `--color-on-surface` |
| `noteBkgColor` / `noteTextColor` / `noteBorderColor` | Sequence-diagram notes | `--color-info-light` / `--color-on-info-light` / `--color-info` (FLS already has this exact role pairing for admonition-style tints) |
| `errorBkgColor` / `errorTextColor` | Syntax-error rendering (mermaid's own parse-error box) | `--color-error-light` / `--color-on-error-light` |
| `fontFamily` | All diagram text | `--fls-font-sans` (resolved value) |

Reference for the variable list and defaults:
[Mermaid theme config docs](https://mermaid.js.org/config/theming.html)

Note `primaryColor` in particular drives a lot of *derived* defaults (secondary/
tertiary/border shades) if you don't set those keys explicitly — so the table above is
a "set explicitly" list; anything left out will still get a mermaid-computed value
based on `primaryColor`/`background`, which may or may not land close enough to FLS's
actual secondary/tertiary tokens. Recommend explicitly setting all rows above rather
than relying on derivation, since FLS's tokens aren't necessarily monochromatic
derivatives of `--color-primary` (e.g. `--color-accent` is amber against a blue
primary).

## 4. Light/dark & the "fixed theme" reality

FLS ships no runtime light/dark toggle today and the shipped themes are single fixed
palettes. Given that: **resolving tokens via `getComputedStyle` once at page-load
init (§2) is sufficient** — there is no "current mode" to track, so no
`MutationObserver`/`prefers-color-scheme` listener is needed for the base case. Keep
it to a single init call.

**If a downstream theme is dark** (a project author ships their own dark palette as a
static theme, per the CLAUDE.md-referenced extensibility model): the resolved-token
approach in §2 still works unchanged, *because it derives from whatever the active
theme's `--color-surface`/`--color-on-surface`/etc. actually resolve to* — you don't
need to detect "is this theme dark" and branch to `theme: 'dark'`. The one thing worth
flagging (not building) for that case: mermaid's `darkMode` themeVariable flag changes
the *direction* some derived-but-unset colors compute in (lighten vs. darken). If a
downstream dark theme's diagrams look a bit off using only the mapping in §3, the fix
is a one-line addition — derive `darkMode: true` from the same surface token's
lightness (e.g. compare resolved `--color-surface` luminance) rather than adding a
separate dark-mode code path. Don't build this now; note it as a follow-up trigger if/
when a real dark theme ships.

## 5. Font & typography

`fontFamily` is a first-class `themeVariables` key (default
`"trebuchet ms, verdana, arial"`) and accepts any CSS font-family string, so mermaid
diagram text can inherit the theme's type stack directly:

```js
fontFamily: cssVar("--fls-font-sans", "ui-sans-serif, system-ui, sans-serif"),
```

`fontSize` is also settable (default `16px`) — leave at default or scale it down
slightly (mermaid diagrams tend to look cramped at full body-text size; ~14px reads
better) rather than trying to bind it to a token; FLS doesn't currently have a
type-scale token for this. [Mermaid theme config docs](https://mermaid.js.org/config/theming.html)

## 6. Responsiveness / overflow

Mermaid renders an inline `<svg>`. With `useMaxWidth: true` (mermaid's default for most
diagram types), the SVG gets `width="100%"` plus an inline `style="max-width: <natural
diagram width>px"` — i.e. it *shrinks* to fit a narrower container but won't grow past
its natural size, and on genuinely wide diagrams (long sequence diagrams, wide
flowcharts) it will still overflow a narrow content column once at max-width.
[Mermaid config schema — `useMaxWidth`](https://mermaid.js.org/config/schema-docs/config-defs-base-diagram-config-properties-usemaxwidth.html)

This is exactly the situation `code-block.html` and `equation.html` already solve:
wrap the rendered SVG in a `overflow-x-auto` container (with the same
`focus:outline-none focus:ring-2 focus:ring-focus-ring` treatment for keyboard focus,
and a `tabindex="0"` + `role`/`aria-label` since the SVG itself isn't natively
focusable/labelled). Concretely:

```html
<div tabindex="0" role="img" aria-label="..."
     class="my-6 overflow-x-auto focus:outline-none focus:ring-2 focus:ring-focus-ring rounded-md"
     x-data="mermaidDiagram">
  ...
</div>
```

No extra CSS-in-JS sizing logic needed beyond mermaid's own `useMaxWidth: true`
default plus the existing `overflow-x-auto` idiom — this keeps the widget consistent
with the two sibling widgets rather than inventing a new responsive strategy.

## Summary / recommended approach

1. Vendor mermaid (like KaTeX) at `^11.15.0` or later (11.16.0 current) — satisfies
   both the Ishikawa/"herringbone" diagram requirement (≥11.12.3) and the CSS-injection
   fix (≥11.15.0).
2. `mermaid.initialize({ theme: 'base', secure: true, themeVariables: {...} })`, called
   once (page-level init script, not per-diagram), with `themeVariables` built by
   resolving FLS's `--color-*`/`--fls-font-sans` tokens via `getComputedStyle` at call
   time — never pass raw `var(...)` strings, they're not supported.
3. Map the table in §3 explicitly (don't rely on mermaid's own derivation from
   `primaryColor` alone, since FLS's palette isn't a monochromatic derivative).
4. No dark-mode branching needed today (FLS has no runtime toggle); note the
   `darkMode` flag as a one-line follow-up trigger only if a downstream dark theme
   ships and diagrams look wrong.
5. Wrap rendered SVGs in the same `overflow-x-auto` + focus-ring pattern already used
   by `cotton/code-block.html` / `cotton/equation.html`; rely on mermaid's
   `useMaxWidth: true` default rather than custom sizing CSS.

## References

- [Mermaid Theme Configuration docs](https://mermaid.js.org/config/theming.html)
- [Mermaid Config Schema — `useMaxWidth`](https://mermaid.js.org/config/schema-docs/config-defs-base-diagram-config-properties-usemaxwidth.html)
- [Ishikawa (fishbone/"herringbone") diagram docs, v11.12.3+](https://mermaid.js.org/syntax/ishikawa.html)
- [GitHub issue #6677 — "Accept CSS variables for theme" (open)](https://github.com/mermaid-js/mermaid/issues/6677)
- [GitHub issue #6860 — "Allow CSS Variables in themeVariables" (open)](https://github.com/mermaid-js/mermaid/issues/6860)
- [GitHub PR #6775 — WIP CSS variable support (unmerged)](https://github.com/mermaid-js/mermaid/pull/6775)
- [GHSA-87f9-hvmw-gh4p — CSS injection via `themeCSS`/`fontFamily`, fixed in 11.15.0/10.9.6](https://github.com/mermaid-js/mermaid/security/advisories/GHSA-87f9-hvmw-gh4p)
- [mkdocs-material discussion #4582 — `getComputedStyle`-based dynamic theming pattern](https://github.com/squidfunk/mkdocs-material/discussions/4582)
- [npm: mermaid package (current 11.16.0)](https://www.npmjs.com/package/mermaid)
- FLS code: `freedom_ls/themes/default/static/themes/default/theme.css`,
  `freedom_ls/content_engine/templates/cotton/equation.html`,
  `freedom_ls/content_engine/templates/cotton/code-block.html`,
  `freedom_ls/content_engine/static/content_engine/vendor/katex/`

status: ok
