# Course colour token simplification

## What we want

In `freedom_ls/themes/first_class/static/themes/first_class/theme.css` the course accent
colours are defined as sets of three hand-picked tokens per accent:

- `--fls-course-accent-N-from`
- `--fls-course-accent-N-to`
- `--fls-course-accent-N-icon`

We want to stop hand-picking the `-to` value and instead **calculate it automatically
from the `-from` value** using CSS relative colour syntax (e.g. derive `-to` by adjusting
the lightness of `-from`). The result should look the same as the current gradients.

Goal: only the `-from` token needs to be authored; `-to` is derived.

## Hard requirement

The derived gradients should use a **single consistent rule** across all five accents.
The current `-to` values are hand-picked and inconsistent:

- accents 1 & 2: `-to` is ~+20% lightness vs `-from`
- accent 3: only ~+8% lighter
- accent 4: a hue shift (orange → amber), not just lightening
- accent 5: `-to` is *darker* than `-from`, not lighter

We do **not** need to reproduce these per-accent quirks exactly. Instead, apply one
consistent lightening formula to every accent — about **+20% lightness** vs `-from`
is fine. The gradients should still look good, just no longer pixel-match the old
hand-picked values.

## Icon colour — also derive it

Derive the `-icon` colour automatically too, so the `-icon` tokens go away. Don't try to
match the current hand-picked icons — prioritise simple code and a good-looking result.

Approach: take a **complementary hue** from `-from` (`h + 180°`) but **force a fixed,
bright lightness and saturation** rather than inheriting them. The icon always sits on the
dark gradient, so the real requirement is luminance contrast, not a true colour-wheel
complement. Pinning lightness/saturation guarantees a bright, vivid icon regardless of the
base hue, and avoids two failure modes:

- a naive `hue + 180°` at the base lightness can land too dark → invisible on the gradient
- a near-greyscale base (accent 5) has no meaningful hue to rotate → would produce a dull
  grey icon; a fixed saturation gives it colour anyway

So a single formula like
`hsl(from var(--fls-course-accent-N-from) calc(h + 180) <fixed-s> <fixed-l>)` should
cover all five. Tune the fixed saturation/lightness once so every icon reads well; no
per-accent `-icon` tokens needed.

## Notes

- CSS relative colour syntax (`hsl(from var(--x) ...)`) is the enabling tech, Baseline
  2024, supported in all current browsers.
- Don't change the visible look of any course card.
