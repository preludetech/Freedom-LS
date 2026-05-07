# Tier-2 override design for first_class

This research designs the concrete `@layer components` overrides that the
first_class theme's `theme.css` should ship to land the visual treatment
shown in `design-system/*.html`. **Only classes that already exist in
`tailwind.components.css` are in scope.** New classes (e.g. `.btn-secondary`,
`.alert`) are listed under "Mockup-only treatments to defer" with a
recommendation, since per the user constraint they require a separate phase
that adds them to *both* the FLS default contract and the first_class theme.

Source files referenced:

- Current first_class tokens — `freedom_ls/themes/first_class/static/themes/first_class/theme.css`
- Default tier-2 component definitions — `tailwind.components.css`
- Brand reference — `spec_dd/2. in progress/themable-implementations-master-decomposed-into-phases/first-class-theme.md`
- Mockups — `spec_dd/1. next/first-class-theme-implement-tier-1-and-2/design-system/*.html`

Cascade: `default theme.css (tokens)` → `tailwind.components.css (defaults)`
→ `first_class theme.css (Tier-1 tokens + Tier-2 component overrides)`. The
later declaration wins, so Tier-2 overrides do not need `!important`.

---

## Per-class proposed overrides

For every class below: the first paragraph names the *default* behaviour from
`tailwind.components.css`, the second names the *mockup* target, and the code
block is the proposed override to land in
`freedom_ls/themes/first_class/static/themes/first_class/theme.css` inside one
shared `@layer components { ... }` block.

All overrides assume the Tier-1 token bundle from
`research_first_class_token_gaps.md` is in place — in particular
`--fls-radius-sm: 0.5rem` (8px) and `--fls-radius-lg: 1rem` (16px) — so the
default `rounded-md` already maps to the brand's "12px / lg" card radius via
`--fls-radius-md: 0.75rem`.

### `.btn`

Default: `inline-block text-center px-6 py-2 font-medium rounded-md ...`
(font-weight 500, py-2 ≈ 8px vertical).

Mockup: `padding:12px 24px; border-radius:8px; font-weight:600; font-size:14px;`
plus a longer ease-out transition (`200ms cubic-bezier(.22,1,.36,1)`).

```css
@layer components {
    .btn {
        @apply px-6 py-3 text-sm font-semibold rounded-sm;
        transition: background-color 200ms cubic-bezier(0.22, 1, 0.36, 1),
                    color 200ms cubic-bezier(0.22, 1, 0.36, 1);
    }
}
```

Why it differs: brand wants chunkier 12/24 padding, semibold weight, and a
springier easing. `rounded-sm` resolves to `--fls-radius-sm` = 0.5rem (8px),
matching the mockup's `8px · default · buttons, inputs` stop in `radii.html`.
Replacing `transition-colors` is necessary because Tailwind's preset uses a
linear/ease curve.

### `.btn-primary`

Default: `bg-primary text-on-primary hover:bg-primary-hover focus:ring-primary`.

Mockup: `background:var(--color-primary); color:white;` — semantically
identical, no override needed beyond what `.btn` already changes.

```css
/* No first_class override required.
   The default already resolves to bg #283593 / text #FFFFFF via Tier-1
   tokens, and inherits the new padding/weight/radius from `.btn`. */
```

Why it differs: it doesn't. Listing explicitly so reviewers know this was
checked, not forgotten.

### `.btn-outline`

Default: `bg-surface text-muted border border-border hover:bg-surface-2
focus:ring-primary` — neutral grey outline button intended as a "secondary
action" affordance.

Mockup `btn-secondary` (the closest analogue): `background:transparent;
color:var(--color-primary); border:1px solid var(--color-primary);` — outline
in primary indigo, not neutral grey.

```css
@layer components {
    .btn-outline {
        @apply bg-transparent text-primary border border-primary
               hover:bg-primary/10 focus:ring-primary;
    }
}
```

Why it differs: brand uses primary-indigo outlines for secondary CTAs, not
neutral borders. `bg-primary/10` gives a soft hover wash that matches the
"electric" feel without flipping to the saturated primary swatch.

### `.btn-success`

Default: `bg-success text-on-success hover:bg-success-hover focus:ring-success`.

Mockup: solid success green; no bespoke success button shown, but the
component contract should remain consistent with `.btn-primary`.

```css
/* No first_class override required.
   Inherits chunkier padding/weight/radius from `.btn`; success colours are
   already brand-correct via Tier-1 (#38A169). */
```

Why it differs: it doesn't.

### `.btn-error`

Default: `bg-error text-on-error hover:bg-error-hover focus:ring-error`.

Mockup `btn-danger`: `background:var(--color-error); color:white;` — same
semantics.

```css
/* No first_class override required.
   Tier-1 already supplies #E53E3E for --color-error and #FFFFFF for
   --color-on-error. */
```

Why it differs: it doesn't.

### `.chip`

Default: `inline-flex items-center gap-1.5 px-3 py-1 text-sm font-medium
rounded-lg`.

Mockup: `padding:6px 12px; border-radius:999px; font-weight:600; font-size:12px;
gap:6px`. Pill-shaped, smaller text, semibold.

```css
@layer components {
    .chip {
        @apply gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-pill;
    }
}
```

Why it differs: brand chips are full pills (`rounded-pill` →
`--fls-radius-pill: 9999px`), one weight step heavier, and use `text-xs`
(12px) per the mockup. `py-1.5` lifts the vertical padding from 4px → 6px to
hit the mockup's 6/12 box. Note: chip "dot" leading marker shown in the
mockup is opt-in markup (`<span class="dot">`), not a class concern, so the
`gap-1.5` already accommodates it without needing a chip-specific dot rule.

### `.chip-primary`

Default: `bg-primary/15 text-primary`.

Mockup "Practical" chip: `background:rgba(40,53,147,.08); color:#283593` —
softer 8% wash, same primary text.

```css
@layer components {
    .chip-primary {
        @apply bg-primary/10 text-primary;
    }
}
```

Why it differs: brand prefers a lighter primary wash (≈10%) so the chip reads
as "tag" rather than "filled badge". Sticking with the shared `/15` default
makes it look heavier than the mockup intends.

### `.chip-warning`

Default: `bg-warning/30 text-on-warning` — yellow wash + dark cockpit text.

Mockup "In progress": `background:#FFFFF0; color:#744210; dot #D69E2E` —
near-white warning surface and a much darker amber text, not the
`--color-on-warning` Cockpit Dark.

```css
@layer components {
    .chip-warning {
        @apply bg-warning/10 text-warning;
    }
}
```

Why it differs: the mockup's `#FFFFF0` is effectively warning at ~5–10%
opacity; using `text-warning` keeps the dark amber readable on it (#D69E2E
on a near-white wash passes WCAG AA at chip text sizes). Keeping the default
`bg-warning/30 text-on-warning` would render as filled-yellow with dark text,
too heavy for the brand. The "Locked" neutral chip in the mockup is *not*
covered here — see deferred list.

### `.chip-success`

Default: `bg-success/15 text-success`.

Mockup "Complete": `background:#F0FFF4; color:#22543D` — green-50 surface,
deep green text.

```css
@layer components {
    .chip-success {
        @apply bg-success/10 text-success;
    }
}
```

Why it differs: 10% wash matches the mockup's near-white green surface more
closely than 15%. `text-success` (#38A169) is slightly brighter than the
mockup's `#22543D`, but it is the brand-contract success colour and stays
readable; introducing a `--color-on-success-soft` token to chase the darker
text is over-engineering for a single chip.

### `.chip-error`

Default: `bg-error/15 text-error`.

Mockup "Failed": `background:#FFF5F5; color:#742A2A` — same pattern as
success: very pale wash, deep red text.

```css
@layer components {
    .chip-error {
        @apply bg-error/10 text-error;
    }
}
```

Why it differs: same logic as `.chip-success` — drops opacity from 15% → 10%
for a closer match to the mockup wash; `text-error` is the brand-contract red.

### `.chip-xs`

Default: `text-xs px-2 py-0.5` — modifier that shrinks the base chip.

Mockup: no explicit `chip-xs` example. The base chip is already 12px text
with 6/12 padding; `chip-xs` would step down further to caption-size status
markers (e.g. inline status next to a row label).

```css
/* No first_class override required.
   The default modifier still works — base `.chip` font-size is now `text-xs`
   so callers using `.chip-xs` get a slightly tighter px-2 / py-0.5 box at
   the same 12px font. If a sub-12px size is ever needed, revisit. */
```

Why it differs: it doesn't, but the relationship to the new base size is
worth flagging in review.

### `.surface`

Default: `border border-border rounded-md py-4 px-4 sm:py-6 sm:px-8`.

Mockup `radii.html` "lg · 12px · cards, modals": surfaces should sit at the
12px stop. With `--fls-radius-md: 0.75rem` (12px), the default
`rounded-md` already lands on 12px in first_class. So the only adjustment is
optional: the brand reference repeatedly shows surfaces on the
`--color-surface` (#F8F9FC Stratosphere) wash rather than the page
background, to give cards a visible lift.

```css
@layer components {
    .surface {
        @apply bg-surface;
    }
}
```

Why it differs: adding an explicit `bg-surface` makes cards pop against the
slightly-darker page background a downstream might choose. Radius already
matches via Tier-1 token override; padding stays the same.

---

## Mockup-only treatments to defer (and why)

Each item below appears in a mockup but has **no current matching class** in
`tailwind.components.css`. Per the user constraint, these are *not* added in
this iteration — they require a follow-on phase that adds the class to the
default contract first, then to first_class as a Tier-2 override.

### `.btn-secondary` (transparent + primary border)

Mockup: `background:transparent; color:var(--color-primary); border:1px solid
var(--color-primary);`.

**Recommendation: defer, but useful follow-on.** Today first_class folds the
"outline / secondary" affordance into `.btn-outline` (see above), which
matches the visual treatment of `btn-secondary` in the mockup. So the brand
look is achievable using existing markup. Splitting into a separate
`.btn-secondary` class only helps if a future spec wants a *neutral* outline
button distinct from a *primary-coloured* outline button — at that point it
should land in the default contract first.

### `.btn-ghost` (transparent text-only, no border)

Mockup: `background:transparent; color:var(--color-primary);`.

**Recommendation: good follow-on candidate.** Currently used in the wild as
ad-hoc `<a class="text-primary underline">…</a>` markup, which is
inconsistent with the button contract for affordances like "Cancel". A real
`.btn-ghost` belongs in `tailwind.components.css` (default theme: muted text,
underline-on-hover) so themes can reopen it.

### `.btn-accent` (Altitude Orange CTA)

Mockup: `background:var(--color-accent); color:white;` — used for celebration
moments ("Get certified").

**Recommendation: defer.** No current usage exercises an accent button —
adding it would be speculative. The Tier-1 `--color-accent` token is in
place, so when a real CTA need appears the class can be added to the default
contract and immediately styled here.

### `.btn-disabled` style

Mockup: explicit `.btn-disabled` class with `background:var(--grey-200);
color:var(--grey-400); cursor:not-allowed;`.

**Recommendation: skip.** The default `.btn` already includes
`disabled:opacity-50 disabled:cursor-not-allowed`, which the mockup's
explicit class is just hand-rolling for static demos. The pseudo-class
approach is correct; no work needed.

### `chip-info` / "Awaiting review" chip

Mockup: `background:#EBF8FF; color:#2A4365; dot #3182CE` — clearly the info
role.

**Recommendation: good follow-on candidate.** `--color-info` exists in
Tier-1 but no `.chip-info` class is defined in
`tailwind.components.css`. Add to the default contract (mirroring
`.chip-success` / `.chip-error`), then first_class can apply the
`bg-info/10 text-info` treatment in the same phase.

### `chip-secondary` / `chip-accent` ("Practical" / "72% scored")

Mockup: indigo-wash chip ("Practical") and teal-wash chip ("72% scored").

**Recommendation: defer for `chip-secondary`; skip for `chip-accent`.** The
indigo "Practical" treatment is what `.chip-primary` already gives in
first_class with the override above (primary = indigo). The teal "72%
scored" chip is genuinely accent / secondary — no class today and no
templates demand it. Wait until a real template needs to communicate "score
percentage" with brand differentiation before adding `.chip-secondary`.

### "Locked" neutral chip

Mockup: `background:#EDF2F7; color:#4A5568; dot #A0AEC0`.

**Recommendation: defer.** This is essentially a `chip-muted` /
`chip-neutral` variant. No current class. Worth adding alongside `chip-info`
in the same follow-on phase if templates need a locked / disabled chip
distinct from `chip-warning`.

### `.alert` / `.alert-success` / `.alert-error` / `.alert-info` / `.alert-up-next`

Mockup `components-feedback.html`: padded boxes with a coloured background,
matching coloured border, and a bold heading line, used for "Correct.",
"Not quite.", "Hint.", and "Up next."

**Recommendation: strong candidate for a dedicated follow-on phase.** This is
a real cross-cutting feedback affordance for the LMS (quiz feedback, hints,
"up next" callouts) that is not currently expressed as a component class —
templates either inline the styling or use `<blockquote>`. Because the
treatment is genuinely new (border + background + bold heading +
optional trailing action), the `.alert` family deserves its own spec/phase
that:

1. Adds `.alert`, `.alert-success`, `.alert-error`, `.alert-info`, and a
   neutral `.alert` variant for "Up next" to `tailwind.components.css`.
2. Decides the heading affordance (a `.alert-title` child class vs styling
   the first child).
3. Lands first_class Tier-2 overrides in the same phase.

Out of scope for this iteration — none of the existing templates use
`.alert*`.

---

## Type / radii notes

### Radii

The `radii.html` mockup specifies four stops: `6px · sm` (chips/badges),
`8px · default` (buttons/inputs), `12px · lg` (cards/modals), and `999px ·
pill`. The first_class Tier-1 bundle currently sets:

- `--fls-radius-sm: 0.5rem` (**8px**, intended for buttons/inputs)
- `--fls-radius-md: 0.75rem` (**12px**, intended for cards/modals — already
  the default `rounded-md` for `.surface`)
- `--fls-radius-lg: 1rem` (**16px**, larger card emphasis)
- `--fls-radius-pill: 9999px` (inherited from default)

This means the mockup's `6px chip stop` is **not** represented — but the
brand also explicitly puts chips at `999px` (full pill) per
`components-chips.html`, so the 6px row in `radii.html` is a generic stop the
brand doesn't actually use for chips. **No Tier-1 token change needed**;
chips become pills via `rounded-pill` in the `.chip` Tier-2 override above.
Buttons go to `rounded-sm` (= 8px in first_class) via the `.btn` override.
Cards remain at `rounded-md` (= 12px). All three mockup stops covered.

### Headings (type-headings.html)

The mockup specifies a heavier, tighter type scale than the FLS base layer
provides:

| Element | Mockup | FLS base layer (`tailwind.components.css`)            |
| ------- | ------ | ------------------------------------------------------ |
| H1      | 40 / 1.2, bold, tracking-tight   | `text-xl sm:text-2xl lg:text-4xl font-bold font-display` |
| H2      | 32 / 1.25, semibold, tracking-tight | `text-lg sm:text-xl lg:text-3xl font-bold font-display` |
| H3      | 24 / 1.3, semibold               | `text-base sm:text-lg lg:text-2xl font-bold font-display` |
| H4      | 20 / 1.4, semibold               | `text-sm sm:text-base lg:text-xl font-bold font-display` |

At the `lg:` breakpoint the FLS base already lands on 36/30/24/20px (close to
the mockup) and uses `font-display`, which first_class re-points at Outfit
via `--fls-font-display`. Two real differences:

1. **Weight.** Mockup uses `font-semibold` for H2–H4; FLS base uses
   `font-bold` for everything. This is a genuine brand divergence.
2. **Tracking.** Mockup uses `tracking-tight` on H1/H2 and
   `letter-spacing:-0.02em` on display.

These translate to **base-layer overrides**, not component overrides. They
*could* live in first_class `theme.css` inside an `@layer base { h2 { @apply
font-semibold tracking-tight; } ... }` block, but doing so re-opens a base
layer that the master spec calls out as shared FLS contract. **Recommendation:
defer heading weight/tracking to a separate spec** — either as a Phase-3
bundle ("first_class type tweaks") or by adding tracking/weight tokens to
the base-layer rules in `tailwind.components.css`. Out of scope here.

### Mono (type-mono.html)

The `type-mono.html` mockup exercises `var(--font-mono)` heavily (flight
data, code blocks, status pills). The Tier-1 gap analysis already calls out
that `--fls-font-mono` is missing from both default and first_class — this
needs to be addressed in Tier-1, not Tier-2 (no component class is involved).
The existing `research_first_class_token_gaps.md` covers this.

---

## Suggested ordering / risk notes

**Order to land Tier-2 overrides in first_class:**

1. **Tier-1 prerequisites** (already specified in
   `research_first_class_token_gaps.md`): land `--fls-font-mono` and the
   `--fls-radius-pill` alias in default `theme.css` first. Without
   `rounded-pill` resolving to `--fls-radius-pill`, the `.chip` override is a
   no-op visually.
2. **`.chip` family** (low risk): pure visual swap, used in many places but
   only for status indication. Easy to spot-check.
3. **`.surface`** (low risk): single-property addition (`bg-surface`).
4. **`.btn` + `.btn-outline`** (medium risk): changes padding and
   font-weight, which alters layout. Visual regression sweep needed on the
   student dashboard, course views, and educator cohort screens.

**Risks worth flagging:**

- `.btn` padding bump (py-2 → py-3, ~8px taller) may push tight nav rows
  onto a second line. Walk dashboards before committing.
- `.btn-outline` flips from neutral grey to primary indigo — this is a
  *semantic* change of the affordance, not just a colour swap. Anywhere
  `.btn-outline` is currently used as "tertiary cancel" will start reading
  as "secondary CTA". Check usage with a quick grep before merging:
  `rg "btn-outline" --type=html`.
- `.chip` going to pills changes shape, not size — should be safe, but
  worth eyeballing wherever chips appear next to tight icon-and-label rows.
- Cascade ordering relies on the first_class `theme.css` being `@import`-ed
  *after* `tailwind.components.css` — already established by Phase 3 spec
  per the master spec, but worth verifying with a single browser-devtools
  inspection of `.btn-primary` after first deploy.

**Out-of-scope items intentionally not included** (require new contract
classes, see "Mockup-only treatments to defer"): `.btn-ghost`, `.btn-accent`,
`.chip-info`, `.chip-muted` / locked chip, `.chip-secondary`,
`.alert*` family, base-layer heading weight/tracking changes.
