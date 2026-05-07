# Tier-2 component class usage audit

Source-of-truth scan of `freedom_ls/**/templates/**/*.html` for every component
class declared in `tailwind.components.css`. Counts are line-count of matches
under a class attribute with strict word boundaries (`(?<![\w-])CLASS(?![\w-])`)
so e.g. `chip` does not match `chip-xs`.

`btn` and `btn-{variant}` are also produced dynamically by the `c-button` cotton
component (`base/templates/cotton/button.html`); `chip` and `chip-{variant}` are
produced dynamically by `c-chip` (`base/templates/cotton/chip.html`). The
indirect counts are reported alongside the direct ones.

## Defined classes (in tailwind.components.css)

### `@layer base` — element styling (no class names, applies globally)

Element selectors styled at `@layer base`: `body`, `h1`, `h2`, `h3`, `h4`,
`h1[id]`–`h6[id]` (scroll-margin), `p`, `a`, `blockquote`, `ul`, `ol`, `li`,
`table`, `thead`, `th`, `td`, `tbody tr`, `tbody tr:last-child`, `label`,
`input[type=text|email|password|number|url|tel|search|date|time|datetime-local]`,
`textarea`, `select`, `input[type=checkbox|radio]`, `fieldset`, `legend`,
`form`. Plus the utility selector `[x-cloak]`.

These are not opt-in classes — every matching element on every page picks them
up. Out of scope for the "is the class actually used" question.

### `@layer components` — Tier-2 public API

| Class | Direct hits (class=) | Indirect via cotton | Status | Example templates |
| --- | --- | --- | --- | --- |
| `.btn` | 13 | +59 (every `<c-button>`) | Used | `base/templates/cotton/button.html`, `base/templates/cotton/data-table.html`, `base/templates/cotton/pagination.html` |
| `.btn-primary` | 1 | +48 (default variant of `<c-button>`: 46 omit `variant=`, 2 set `variant="primary"`) | Used | `base/templates/cotton/pagination.html`, plus every `<c-button>` without a variant |
| `.btn-outline` | 10 | +5 (`<c-button variant="outline">`) | Used | `base/templates/cotton/data-table.html`, `base/templates/cotton/pagination.html`, `student_interface/templates/student_interface/partials/course_list.html` |
| `.btn-success` | 0 | 0 (no `<c-button variant="success">` in repo) | **Defined but unused** | — |
| `.btn-error` | 1 | +4 (`<c-button variant="error">`) | Used | `base/templates/cotton/data-table.html`, `panel_framework/templates/panel_framework/partials/delete_confirmation.html`, `base/templates/cotton/button.html` (docstring example) |
| `.surface` | 9 | 0 | Used | `student_interface/templates/student_interface/course_form_page.html`, `student_interface/templates/student_interface/partials/course_list.html`, `panel_framework/templates/panel_framework/partials/panel_container.html`, `educator_interface/templates/educator_interface/partials/panel_container.html` |
| `.chip` | 4 | +0 (`<c-chip>` is only referenced inside its own docstring; no production callers) | Used (direct only) | `educator_interface/templates/educator_interface/partials/course_progress_panel.html` |
| `.chip-primary` | 0 | 0 (no production `<c-chip>` callers) | **Defined but unused** | — |
| `.chip-warning` | 1 | 0 | Used | `educator_interface/templates/educator_interface/partials/course_progress_panel.html` |
| `.chip-success` | 1 | 0 | Used | `educator_interface/templates/educator_interface/partials/course_progress_panel.html` |
| `.chip-error` | 2 | 0 | Used | `educator_interface/templates/educator_interface/partials/course_progress_panel.html` |
| `.chip-xs` | 4 | 0 | Used | `educator_interface/templates/educator_interface/partials/course_progress_panel.html` |
| `.htmx-hide-on-request` | 1 | +59 (rendered for every `<c-button loading="…">`; gated by `{% if loading %}`) | Used | `base/templates/cotton/button.html` |
| `.htmx-show-on-request` | 1 | +59 (same as above) | Used | `base/templates/cotton/button.html` |
| `.htmx-request` (selector prefix only — applied by HTMX itself, never authored in templates) | 0 | n/a | n/a (HTMX-driven, not a template authoring concern) | — |

Spec cross-reference (`spec_dd/2. in progress/themable-implementations-master-decomposed-into-phases/1. spec.md`,
section "Component class names — public API now"): the spec lists `btn`,
`btn-primary`, `btn-outline`, `btn-success`, `btn-error`, `chip`, `chip-primary`,
`chip-warning`, `chip-success`, `chip-error`, `chip-xs`, `surface` as the public
Tier-2 API. **All twelve are defined; ten are used; two (`btn-success`,
`chip-primary`) are defined but unused in templates.** The HTMX state utilities
in `tailwind.components.css` are not in the spec's public-API list — they are
internal plumbing for the loading-spinner pattern in `c-button`.

## Mockup classes not yet defined

From `spec_dd/1. next/first-class-theme-implement-tier-1-and-2/design-system/`,
classes that appear in the mockups but are **not** declared in
`tailwind.components.css` and **not** present in any template:

| Mockup class | Origin file | Suggested handling |
| --- | --- | --- |
| `.btn-secondary` | `components-buttons.html` | Add to base + first_class — `secondary` is one of the seven token roles in the spec, parallel to existing `btn-primary` / `btn-error`. (Out of scope for this idea — flag only.) |
| `.btn-ghost` | `components-buttons.html` | Skip for now. Not a token role; introduces a new shape variant ("transparent / no border / no fill") not yet justified by templates. Revisit if the cancel-action pattern recurs. |
| `.btn-accent` | `components-buttons.html` | Add to base + first_class — `accent` is one of the seven token roles in the spec. Same reasoning as `btn-secondary`. (Out of scope for this idea — flag only.) |
| `.btn-danger` | `components-buttons.html` | Skip — name conflicts with the `danger → error` rename decided in the master spec. Treat as the mockup's pre-rename label for `btn-error` (already defined). |
| `.btn-disabled` | `components-buttons.html` | Skip. The base `.btn` already applies `disabled:opacity-50 disabled:cursor-not-allowed` via the native `disabled` attribute. A separate class would duplicate that. |
| `.alert` | `components-feedback.html` | Out of scope for this idea. No `.alert` class exists in FLS today and no template references one (the single `alert` hit in `partials/messages.html` is an ARIA `role="alert"`, not a CSS class). The mockup's four feedback variants (success/error/info/upcoming) would map to a future `.alert` + `.alert-success/-error/-info` family aligned with the chip token roles, but the design has no FLS-template analogue yet. Flag only. |
| `chip-info` (implied — info-tinted chip in mockup, "Awaiting review") | `components-chips.html` | Add to base + first_class — `info` is one of the seven token roles in the master spec but no `chip-info` class exists. Aligns with the role-parity argument for the chip family. (Out of scope for this idea — flag only.) |
| `.dot` (small status dot inside chips) | `components-chips.html` | Skip. Decorative-only; can be expressed inline with Tailwind utilities where needed. Don't promote to Tier-2 until repeated. |

The mockup chip styles also use bespoke hex backgrounds (e.g.
`background:#F0FFF4;color:#22543D`) rather than role-token classes. Not a class
gap — those are tokens to be supplied by the first_class theme's `theme.css`
once the chip variants exist.

## Recommendations

### First-priority Tier-2 first_class overrides (used in templates AND visually called out in mockups)

Order by template footprint × design-system prominence:

1. **`.btn-primary`** — every default `<c-button>` (≈ 48 sites) + 1 direct hit. Mockup shows a clear branded "Start module" button. Highest visual surface.
2. **`.btn-outline`** — 10 direct + 5 indirect. Mockup shows the secondary-outline shape ("View syllabus") and the spec's first_class canary calls out "bolder border".
3. **`.btn`** — base shape (radius/padding/font-weight). Re-opening it in first_class lets the canary's "softer card / rounder" theme propagate to every variant in one place.
4. **`.chip`** — base chip (radius/padding/typography). Mockup uses the pill-shaped chip throughout the dashboard. Spec's first_class canary calls out "flatter (no shadow)".
5. **`.chip-success`, `.chip-warning`, `.chip-error`** — all three appear in `course_progress_panel.html`, the most data-dense educator view, and all three are explicitly tinted in the mockup ("Complete" / "In progress" / "Failed"). Tight token alignment; cheap win.
6. **`.surface`** — 9 direct uses across the most-visible student-facing pages (course list, course form, recommendations, learning history) and the panel framework. Not in the buttons/chips mockups but a high-leverage shape primitive worth Tier-2 styling under first_class.
7. **`.btn-error`** — 1 direct + 4 indirect (delete-confirmation flows). Lower prominence but worth covering for visual consistency with the rest of the button family.

### "Extra" classes to consider adding to base + first_class — flag only, do NOT implement here

The user has explicitly asked for these to be flagged, not implemented:

- **`.btn-secondary`, `.btn-accent`, `.chip-info`** — close the role-parity gap so every spec token role (`primary`, `secondary`, `accent`, `success`, `warning`, `error`, `info`) has a button and a chip variant in `tailwind.components.css`. Currently only primary / outline (≈ secondary-shaped) / success / error / warning are covered for buttons, and only primary / success / warning / error for chips. Adding these would let mockup designs land without invented one-off classes.
- **`.alert`** + role-coloured variants — feedback panel is a recognisable design-system primitive. Mockup defines four variants (success / error / info / upcoming-tinted-primary). Today's templates don't use one, but Django messages partial (`base/templates/partials/messages.html`) is the natural first home.
- **`.btn-ghost`, `.btn-disabled`, `.dot`** — mockup-only; do not promote to Tier-2 until a real template need recurs.

### Defined-but-unused classes (decide before Phase 3 ships)

- **`.btn-success`** — 0 hits. Either remove from `tailwind.components.css`, or keep on the basis that the spec lists it as public API and dropping it would itself be a breaking change. Recommend **keep** for role-parity (matches the seven roles) and document it as available API.
- **`.chip-primary`** — 0 direct hits and `<c-chip>` has no production callers either, so the cotton component's `variant="primary"` default has zero render sites. Recommend **keep** (same role-parity argument); the `c-chip` cotton component is the obvious caller and is likely to be wired into more places.
