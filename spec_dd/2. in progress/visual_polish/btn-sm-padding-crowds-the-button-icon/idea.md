# Idea: `.btn-sm` padding is too tight for a full-size button icon, so the course player's Next arrow crowds the edge

## The bug

Source: visual QA of the course-player navigation on the `first_class` theme.

Every control in the player nav passes `size="small"` (`course_topic.html:15-57`). The Next button's
trailing arrow reads as jammed against the button's right edge, and the whole row looks cramped.

Two mechanics combine.

`.btn.btn-sm` at `tailwind.components.css:211` is a compound selector, two classes. A theme reopening
`.btn` writes a single-class rule. Two classes beat one whatever the import order, so
`.btn.btn-sm`'s `px-2 py-1.5` always wins over a theme's `.btn` padding. `first_class`'s `px-6 py-3`
at `themes/first_class/static/themes/first_class/theme.css:95` never reaches a small button, and
neither would any other theme's. Effective padding on these controls is 8px horizontal, 6px vertical.

The icon is a fixed `size-5`, 20px, at `cotton/button.html:32,47,50`, and does not scale down for
`btn-sm`. It is spaced with `mr-2`/`ml-2` on the icon itself, while `.btn` sets `inline-flex
items-center justify-center` and no `gap`. Label-to-icon and icon-to-edge both measure 8px, so the
CSS is symmetric, but an arrow glyph carries less ink near its box edge than a text label does, so
the trailing arrow optically crowds the edge in a way the leading arrow on Previous does not.

`.btn-secondary`'s `border-2` at `themes/first_class/static/themes/first_class/theme.css:101` is a
smaller third contributor. With border-box sizing the outlined Previous button puts 10px between
outer edge and content against Next's 8px, which is part of why Previous reads better than Next.

## Expected fix

Three changes to the shared button contract.

Restore `.btn-sm` to a single class, ordered after `.btn`, and take it to `px-3 py-2`. The compound
form was never a design decision: it arrived as working-tree drift in `c56766b8`, and before that the
rule was `.btn-sm { @apply px-4 py-1.5 text-sm }`. Restoring the single class hands small-button
padding back to the theming contract, which carries a consequence. At equal specificity the active
theme wins on source order, so a theme reopening `.btn` padding now swamps `.btn-sm` unless it
reopens that too. `first_class` must therefore declare `.btn-sm` alongside its `.btn`, and the Tier 2
section of `docs/how tos/theme-fls.md` must state that rule. `px-3 py-2` also lifts these controls
from roughly 32px tall to nearer 40px. 32px already clears WCAG 2.2 SC 2.5.8's 24px floor, so this is comfort rather than compliance,
and it stops short of the 44px Apple HIG figure. A hard 44px floor for every small button in the
codebase is a much larger visual change and should be decided on its own.

Move icon spacing from `mr-2`/`ml-2` on the icon to a `gap` on the `.btn` container, and drop the
margins. This is the idiom Tailwind UI and Shadcn both use, and it fixes two cases the margins get
wrong today: an icon with no label still reserves its margin, and a button carrying both a leading
and a trailing icon only gets one of them spaced correctly.

Drop the icon to `size-4`, 16px, under `btn-sm`, so a small button reads as small.

The margin removal and the `gap` have to land in the same change, since removing the margins alone
leaves icon and label touching. Two of the three occurrences sit inside `.btn`, which is already
`inline-flex`, so a container `gap` covers them: `:47` is the loading state and `:50` the ordinary
path. The third, `:32`, is the dropdown variant, and its container is `block w-full text-left ...`
rather than a flex box, so a `gap` there would silently do nothing. That variant keeps its icon
margins; only the `.btn` path moves to `gap`. Converting the dropdown item to flex would change
menu-item layout for no gain here. The template ends up carrying two spacing idioms, so it needs a
comment saying why.

Leave `.btn-secondary`'s `border-2` alone. The 2px is real but not worth separate action.

## Sources

- `tailwind.components.css:163`, the base `.btn`, and `:211`, the `.btn.btn-sm` compound selector
  that outranks every theme.
- `freedom_ls/base/templates/cotton/button.html:32,47,50`, the three places the icon carries its own
  margin and a hardcoded `size-5`.
- `freedom_ls/themes/first_class/static/themes/first_class/theme.css:95`, the theme `.btn` padding
  that `btn-sm` overrides, and `:101`, `.btn-secondary`'s border.
- `freedom_ls/learner_interface/templates/learner_interface/course_topic.html:15-57`, the player nav
  block where every control is `size="small"`.
- W3C WAI, Understanding SC 2.5.8 Target Size (Minimum).
