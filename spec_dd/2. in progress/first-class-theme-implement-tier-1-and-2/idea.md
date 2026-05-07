# first_class theme — implement Tier 1 + Tier 2

Refine the `first_class` canary so its Tailwind theme matches the
design-system mockups in `./design-system/`. This idea **supersedes** the
existing `themable-implementations-phase-3-component-class-overrides` spec
(which only covered three demo classes); when this work picks up, that older
in-progress folder gets archived.

The brand reference is
`spec_dd/2. in progress/themable-implementations-master-decomposed-into-phases/first-class-theme.md`
("Modern Altitude"). The current first_class Tier-1 token bundle lives at
`freedom_ls/themes/first_class/static/themes/first_class/theme.css`.

## Guardrail

> Any new component class lands in **both** `tailwind.components.css`
> (default contract) **and** `first_class/theme.css` (override). Never quietly
> add a class to first_class alone — it must be a public API on every theme.

## Tier 1 — token additions (default + first_class)

The Tier-1 surface stays narrow. Bounded additions only:

- **`--fls-font-mono` + `font-mono` Tailwind alias.** Mockups
  (`type-mono.html`) need a mono font for technical specs / timestamps.
  Add `--fls-font-mono` to default theme tokens, alias it in
  `@theme inline` (alongside `--font-sans` / `--font-display`), then have
  first_class redeclare it as `"IBM Plex Mono", Menlo, monospace`.
- **Status-light tokens** — `success-light`, `warning-light`, `error-light`,
  `info-light` for chip/alert backgrounds (replacing today's
  ad-hoc `bg-success/15` opacity modifiers). Brand-canonical hexes
  (`#F0FFF4`, `#FFFFF0`, `#FFF5F5`, `#EBF8FF`) are reasonable defaults
  in both themes.
- **`on-*-light` foreground tokens** — paired darker text colours for the
  Light surfaces (e.g. `#22543D` on success-light). Without these the chips
  and alerts have no legible foreground token and templates would fall back
  to ad-hoc `text-*` classes.

Out of Tier-1 scope:
- Neutral 50–900 ramp (master spec defers ramps).
- A `secondary-light` token. `.chip-secondary` reaches for `bg-secondary/15`
  opacity instead, matching how `.chip-primary` works today.
- Any other token-surface widening.

## Tier 1 — corrections to current first_class theme.css

- **Radii realignment** to match `radii.html`: `--fls-radius-sm`
  `0.375rem` (6px), `-md` `0.5rem` (8px), `-lg` `0.75rem` (12px).
  (Currently shipping 8/12/16 — one step too round.)
- All other colour tokens already match the brand doc hex-for-hex; no
  drift to fix.

## Tier 2 — base contract additions in `tailwind.components.css`

These classes do not exist today. Each gets a default-theme definition in
`tailwind.components.css` so the contract is universal, plus a first_class
override below where the look diverges.

Buttons:
- `.btn-secondary` — transparent background, primary border, primary text;
  hover fills with `bg-primary/10`. The "secondary CTA" affordance.
  **Note:** `.btn-outline` keeps its current neutral-grey "cancel"
  semantics in both themes — it is **not** flipped to indigo. The two
  classes coexist with distinct meanings.
- `.btn-ghost` — transparent background, no border, primary text;
  hover fills with `bg-primary/10`. Lower-emphasis text-button affordance.
- `.btn-accent` — solid `bg-accent text-on-accent` with `hover:bg-accent-hover`.
  Mirrors `.btn-primary`/`.btn-success`/`.btn-error` naming for the
  remaining brand role.

Chips:
- `.chip-info` — `bg-info/15 text-info` (default); first_class uses
  `bg-info-light text-on-info-light` once the light tokens land.
- `.chip-secondary` — `bg-secondary/15 text-secondary`. Used for
  brand-secondary tags (e.g. "72% scored").
- `.chip-muted` — `bg-surface-2 text-muted`. Neutral / locked /
  not-started state. Reuses existing tokens; no new tokens required.

Alerts (the whole class is new — zero callers today, but the canary
demonstrates the role contract and templates can adopt incrementally):
- `.alert` — base layout: padding, rounded, border, body type. Variant
  classes layer in colour.
- `.alert-success` — `bg-success/10 border-success/30 text-on-surface`
  in default; first_class uses the new `*-light` token pair.
- `.alert-error` — same shape, error palette.
- `.alert-info` — same shape, info palette.

Out of Tier-2 scope (deferred until a real call site):
- `alert-warning`, `alert-cta` ("Up next" prescriptive layout from the
  mockup) — add when needed.
- `.btn-disabled` — `:disabled` already handled by base `.btn` rules.

## Tier 2 — `@layer components` overrides in first_class theme.css

Override classes already in (or just-added to) `tailwind.components.css`
where the first_class look differs from the default. Concrete `@apply`
rules are drafted in `research_tier2_overrides.md`.

Existing classes:
- `.btn` — chunkier padding, `text-sm font-semibold`, springier transition.
- `.chip` — full pill, `text-xs font-semibold`, slightly more vertical padding.
- `.chip-primary` / `.chip-warning` / `.chip-success` / `.chip-error` —
  flatter Light-tint look using the new `*-light` / `on-*-light` tokens.
  Warning text flips to `text-warning` (was `text-on-warning`).
- `.surface` — explicit `bg-surface` so cards lift off the page.

Newly-added classes (overrides where first_class diverges):
- `.btn-secondary` — strengthen border to `border-2` to match the brand's
  "thicker outline" rationale.
- `.chip-info` / `.chip-secondary` / `.chip-muted` — match the flatter
  pill treatment of the other first_class chips. `.chip-info` switches to
  the new `info-light` / `on-info-light` token pair.
- `.alert-success` / `.alert-error` / `.alert-info` — switch backgrounds
  and text to the `*-light` / `on-*-light` token pairs for the brand-correct
  pastel feel; tighten border colour.

Tier-1-only classes (no Tier-2 override needed — token swap alone is
enough): `.btn-primary`, `.btn-success`, `.btn-error`, `.btn-accent`,
`.btn-ghost`, `.btn-outline`, `.chip-xs`, `.alert` (base shape).

## Tier 2 — `@layer base` override in first_class theme.css

Match the design-system type scale where it diverges from the FLS default
base layer:

- H2–H4 use `font-semibold` (not `font-bold`).
- H1 + H2 use `tracking-tight`.

Body, mono, and the responsive size scale stay as-is.

## References

- `./research_component_class_usage.md` — Tier-2 class usage audit.
- `./research_first_class_token_gaps.md` — Tier-1 drift + additions.
- `./research_tier2_overrides.md` — concrete `@apply` blocks per class.
- `./design-system/` — visual targets.
- `../../2. in progress/themable-implementations-master-decomposed-into-phases/`
  — master spec + brand reference.
